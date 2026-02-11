"""
Market Maker V2 — Full Layer Integration with Transaction Signing

Flow per cycle:
1. Fetch market data (price via Jupiter)
2. Feed to Wyckoff detector → get phase + signal
3. Check stop losses on open positions
4. If signal suggests trade → create TradeIntent
5. Risk Manager evaluates → APPROVED / REJECTED / HALTED
6. If approved → Order Manager executes via Jupiter (sign & send)
7. Record everything to database
8. Check profit-taking schedule
9. Sleep and repeat

Trading Strategy (automated after parameters set):
- BUY token with SOL when price is low (Accumulation phase / good value)
- SELL token for SOL when demand increases (Distribution phase / high price)
- STOP LOSS: auto-sell if any position drops below stop_loss_percent from entry
- All trades gated by risk manager (position limits, drawdown, circuit breakers)
"""

import os
import time
import uuid
import asyncio
import logging
from dataclasses import dataclass
from typing import Optional

from backend.config import settings
from backend.risk_manager import RiskManager, TradeIntent, RiskAction
from backend.order_manager import OrderManager, Order, OrderSide
from backend.database import (
    init_database, create_order, update_order_status,
    record_transaction, upsert_position, record_price,
    log_audit_event, record_wallet_snapshot, get_open_positions,
)
from backend.strategy.wyckoff import (
    WyckoffDetector, MarketSnapshot, WyckoffPhase, TradeSignal,
)
from backend.profit_taker import ProfitTaker
from backend.dex.jupiter import JupiterAdapter
from backend.wallet_manager import WalletOrchestrator, SelectionStrategy

logger = logging.getLogger("market_maker_v2")


@dataclass
class TradingConfig:
    """
    Configurable trading parameters — set these once and the bot runs automated.
    Adjust via API at /api/v2/trading/config or environment variables.
    """
    # Trade sizing
    base_trade_size_sol: float = 0.1       # Default SOL per trade
    strong_signal_multiplier: float = 2.0  # 2x size for STRONG_BUY/STRONG_SELL
    min_trade_size_sol: float = 0.01       # Minimum trade (avoid dust)
    max_trade_size_sol: float = 1.0        # Cap per single trade

    # Stop loss (per-position, % below entry price)
    stop_loss_percent: float = 10.0

    # Signal filtering
    min_confidence: float = 0.5            # Minimum Wyckoff confidence to act

    # Slippage
    max_slippage_percent: float = 2.0      # Max acceptable slippage

    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Load config from environment variables with sensible defaults."""
        return cls(
            base_trade_size_sol=float(os.getenv("BASE_TRADE_SIZE_SOL", "0.1")),
            strong_signal_multiplier=float(os.getenv("STRONG_SIGNAL_MULTIPLIER", "2.0")),
            min_trade_size_sol=float(os.getenv("MIN_TRADE_SIZE_SOL", "0.01")),
            max_trade_size_sol=float(os.getenv("MAX_TRADE_SIZE_SOL", "1.0")),
            stop_loss_percent=float(os.getenv("STOP_LOSS_PERCENT", "10.0")),
            min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.5")),
            max_slippage_percent=float(os.getenv("MAX_SLIPPAGE_PERCENT", "2.0")),
        )


class MarketMakerV2:
    """
    Production market maker integrating all 7 architecture layers.

    Automated strategy:
    - Buys token (sells SOL) when Wyckoff detects Accumulation (price is low/good value)
    - Sells token (gets SOL) when Wyckoff detects Distribution (demand is high)
    - Enforces per-position stop losses
    - All trades pass through risk management
    """

    def __init__(
        self,
        wallet_orchestrator: WalletOrchestrator,
        token_mint: str,
        risk_manager: RiskManager = None,
        order_manager: OrderManager = None,
        wyckoff_detector: WyckoffDetector = None,
        profit_taker: ProfitTaker = None,
        jupiter: JupiterAdapter = None,
        trading_config: TradingConfig = None,
    ):
        self.wallet_orchestrator = wallet_orchestrator
        self.token_mint = token_mint

        self.risk_manager = risk_manager or RiskManager()
        self.order_manager = order_manager or OrderManager()
        self.wyckoff = wyckoff_detector or WyckoffDetector()
        self.profit_taker = profit_taker or ProfitTaker()
        self.jupiter = jupiter or JupiterAdapter()
        self.trading_config = trading_config or TradingConfig.from_env()

        # State
        self._running = False
        self._cycle_count = 0
        self._last_price = 0.0
        self._cycle_interval_s = float(os.getenv("CYCLE_INTERVAL_S", "15.0"))

        # Stats
        self._stats = {
            "started_at": 0,
            "cycles": 0,
            "trades_attempted": 0,
            "trades_filled": 0,
            "trades_rejected_risk": 0,
            "trades_failed": 0,
            "stop_losses_triggered": 0,
            "total_volume_sol": 0,
            "uptime_s": 0,
        }

    # ── Lifecycle ───────────────────────────────────────────────────

    async def start(self):
        """Start the market maker loop."""
        if self._running:
            logger.warning("Market maker already running")
            return

        init_database()
        self._running = True
        self._stats["started_at"] = time.time()

        log_audit_event("system", "operator", "start_market_maker",
                        f"token:{self.token_mint}", "success")

        logger.info(f"Market Maker V2 started for token {self.token_mint[:12]}...")
        logger.info(f"Cycle interval: {self._cycle_interval_s}s")
        logger.info(f"Trade size: {self.trading_config.base_trade_size_sol} SOL")
        logger.info(f"Stop loss: {self.trading_config.stop_loss_percent}%")

        try:
            while self._running:
                await self._run_cycle()
                await asyncio.sleep(self._cycle_interval_s)
        except asyncio.CancelledError:
            logger.info("Market maker cancelled")
        except Exception as e:
            logger.critical(f"Market maker crashed: {e}", exc_info=True)
            self.risk_manager.emergency_shutdown()
        finally:
            self._running = False
            await self.jupiter.close()

    def stop(self):
        """Gracefully stop the market maker."""
        self._running = False
        log_audit_event("system", "operator", "stop_market_maker",
                        f"token:{self.token_mint}", "success")
        logger.info("Market maker stopping...")

    # ── Main Cycle ──────────────────────────────────────────────────

    async def _run_cycle(self):
        """One complete market making cycle — all 7 layers working together."""
        self._cycle_count += 1
        cycle_start = time.time()

        try:
            # ── Layer 1: Market Data ────────────────────────────────
            price = await self._fetch_market_data()
            if price is None or price <= 0:
                logger.debug("No valid price data — skipping cycle")
                return

            # ── Layer 2: Strategy / Wyckoff ─────────────────────────
            analysis = self.wyckoff.analyze()

            if self._cycle_count % 10 == 0:
                logger.info(
                    f"Cycle {self._cycle_count}: "
                    f"price={price:.8f} "
                    f"phase={analysis.phase.value} "
                    f"signal={analysis.signal.value} "
                    f"confidence={analysis.confidence:.0%}"
                )

            # ── Stop Loss Check ─────────────────────────────────────
            await self._check_stop_losses(price)

            # ── Layer 7: Check Profit-Taking Schedule ───────────────
            await self._check_profit_taking(price, analysis)

            # ── Generate Trade Intent from Signal ───────────────────
            trade_intent = self._signal_to_intent(analysis, price)
            if trade_intent is None:
                return  # No action for this signal

            # ── Layer 3: Risk Check ─────────────────────────────────
            risk_decision = self.risk_manager.evaluate_trade(trade_intent)

            if risk_decision.action != RiskAction.APPROVED:
                self._stats["trades_rejected_risk"] += 1
                log_audit_event("risk", "system", "trade_rejected",
                                f"token:{self.token_mint}",
                                risk_decision.action.value,
                                {"reason": risk_decision.reason})
                return

            # ── Layer 4+5: Execution ────────────────────────────────
            await self._execute_trade(trade_intent, price)

        except Exception as e:
            logger.error(f"Cycle {self._cycle_count} error: {e}", exc_info=True)

        self._stats["cycles"] = self._cycle_count
        self._stats["uptime_s"] = time.time() - self._stats["started_at"]

    # ── Market Data Fetching ────────────────────────────────────────

    async def _fetch_market_data(self) -> Optional[float]:
        """Fetch current price and feed to strategy + risk layers."""
        try:
            price = await self.jupiter.get_price(self.token_mint)
            if price and price > 0:
                self._last_price = price

                # Feed to Wyckoff detector
                self.wyckoff.add_data(MarketSnapshot(
                    price=price,
                    volume=0,  # Jupiter doesn't provide volume; could add Birdeye later
                    timestamp=time.time(),
                ))

                # Feed to risk manager for rapid change detection
                self.risk_manager.record_price(price)

                # Persist to database
                record_price(self.token_mint, price)

                return price
        except Exception as e:
            logger.warning(f"Failed to fetch market data: {e}")

        return self._last_price if self._last_price > 0 else None

    # ── Stop Loss Enforcement ───────────────────────────────────────

    async def _check_stop_losses(self, current_price: float):
        """
        Check all open positions for stop-loss triggers.
        If a position has dropped below stop_loss_percent from entry, force sell.
        """
        try:
            positions = get_open_positions()
        except Exception:
            return

        for pos in positions:
            if pos.get("token_mint") != self.token_mint:
                continue
            if pos.get("quantity", 0) <= 0:
                continue

            entry_price = pos.get("average_entry_price", 0)
            if entry_price <= 0:
                continue

            # Calculate loss percentage
            loss_pct = ((entry_price - current_price) / entry_price) * 100

            if loss_pct >= self.trading_config.stop_loss_percent:
                wallet_addr = pos["wallet_address"]
                logger.warning(
                    f"STOP LOSS triggered: wallet {wallet_addr[:8]}... "
                    f"loss={loss_pct:.1f}% (threshold: {self.trading_config.stop_loss_percent}%)"
                )
                self._stats["stop_losses_triggered"] += 1

                # Create forced sell intent
                intent = TradeIntent(
                    wallet_address=wallet_addr,
                    token_mint=self.token_mint,
                    side="sell",
                    amount_sol=min(pos["quantity"], self.trading_config.max_trade_size_sol),
                    expected_price=current_price,
                    strategy_reason=f"STOP_LOSS: {loss_pct:.1f}% loss (threshold: {self.trading_config.stop_loss_percent}%)",
                )

                # Stop loss still goes through risk checks (but most will pass for sells)
                decision = self.risk_manager.evaluate_trade(intent)
                if decision.action == RiskAction.APPROVED:
                    await self._execute_trade(intent, current_price)
                else:
                    logger.error(
                        f"Stop loss sell BLOCKED by risk manager: {decision.reason}. "
                        f"Consider manual intervention."
                    )

    # ── Signal to Intent Conversion ─────────────────────────────────

    def _signal_to_intent(self, analysis, price: float) -> Optional[TradeIntent]:
        """
        Convert a Wyckoff signal into a TradeIntent.
        This is the core automated strategy:
        - BUY when price is low (Accumulation) → sell SOL, buy token
        - SELL when demand is high (Distribution) → sell token, get SOL
        """
        # Only act on signals with sufficient confidence
        if analysis.confidence < self.trading_config.min_confidence:
            return None

        # Select wallet for this trade
        wallet = self.wallet_orchestrator.get_wallet(
            strategy=SelectionStrategy.HEALTH_BASED,
            min_balance=self.trading_config.min_trade_size_sol,
        )
        if not wallet:
            logger.warning("No wallet available for trade")
            return None

        # Calculate trade size based on signal strength
        base_size = self.trading_config.base_trade_size_sol
        strong_size = base_size * self.trading_config.strong_signal_multiplier

        # Clamp to configured limits
        def clamp_size(size: float) -> float:
            return max(
                self.trading_config.min_trade_size_sol,
                min(size, self.trading_config.max_trade_size_sol),
            )

        if analysis.signal == TradeSignal.BUY:
            # Accumulation phase — buy token at support (good value)
            return TradeIntent(
                wallet_address=wallet.address,
                token_mint=self.token_mint,
                side="buy",
                amount_sol=clamp_size(base_size),
                expected_price=price,
                max_slippage_percent=self.trading_config.max_slippage_percent,
                strategy_reason=analysis.reason,
            )

        elif analysis.signal == TradeSignal.STRONG_BUY:
            # Strong accumulation signal — larger buy
            return TradeIntent(
                wallet_address=wallet.address,
                token_mint=self.token_mint,
                side="buy",
                amount_sol=clamp_size(strong_size),
                expected_price=price,
                max_slippage_percent=self.trading_config.max_slippage_percent,
                strategy_reason=analysis.reason,
            )

        elif analysis.signal == TradeSignal.SELL:
            # Distribution phase — sell token into demand
            return TradeIntent(
                wallet_address=wallet.address,
                token_mint=self.token_mint,
                side="sell",
                amount_sol=clamp_size(base_size),
                expected_price=price,
                max_slippage_percent=self.trading_config.max_slippage_percent,
                strategy_reason=analysis.reason,
            )

        elif analysis.signal == TradeSignal.STRONG_SELL:
            # Markdown phase — exit positions quickly
            return TradeIntent(
                wallet_address=wallet.address,
                token_mint=self.token_mint,
                side="sell",
                amount_sol=clamp_size(strong_size),
                expected_price=price,
                max_slippage_percent=self.trading_config.max_slippage_percent,
                strategy_reason=analysis.reason,
            )

        return None

    # ── Trade Execution (with real signing) ─────────────────────────

    async def _execute_trade(self, intent: TradeIntent, price: float):
        """Execute an approved trade through the full pipeline."""
        self._stats["trades_attempted"] += 1

        # Create order record in database
        order_id = create_order(
            wallet_address=intent.wallet_address,
            token_mint=intent.token_mint,
            side=intent.side,
            quantity_sol=intent.amount_sol,
            expected_price=price,
            strategy_reason=intent.strategy_reason,
        )

        # Build order object for the order manager
        order = Order(
            order_id=order_id,
            wallet_address=intent.wallet_address,
            token_mint=intent.token_mint,
            side=OrderSide.BUY if intent.side == "buy" else OrderSide.SELL,
            amount_sol=intent.amount_sol,
            expected_price=price,
            max_slippage_percent=intent.max_slippage_percent,
            strategy_reason=intent.strategy_reason,
        )

        self.order_manager.create_order(order)

        # Create the sign-and-send callback for this wallet
        wallet_address = intent.wallet_address
        orchestrator = self.wallet_orchestrator

        async def _sign_and_send(tx_bytes: bytes) -> str:
            """Sign transaction with wallet's encrypted private key and send to Solana."""
            return await self._sign_and_send_transaction(tx_bytes, wallet_address)

        async def _execute_swap(**kwargs):
            return await self.jupiter.execute_swap(
                **kwargs,
                sign_and_send=_sign_and_send,
            )

        # Execute through order manager (handles retries)
        result_order = await self.order_manager.execute_order(
            order=order,
            swap_function=_execute_swap,
        )

        # Update database based on result
        success = result_order.state.value == "filled"

        update_order_status(
            order_id=order_id,
            status=result_order.state.value,
            filled_quantity=result_order.filled_amount,
            average_fill_price=result_order.average_fill_price,
            slippage_percent=result_order.actual_slippage,
            error_message=result_order.error_message,
        )

        if success:
            self._stats["trades_filled"] += 1
            self._stats["total_volume_sol"] += intent.amount_sol

            # Update position
            qty_delta = intent.amount_sol if intent.side == "buy" else -intent.amount_sol
            upsert_position(
                wallet_address=intent.wallet_address,
                token_mint=intent.token_mint,
                quantity_delta=qty_delta,
                price=result_order.average_fill_price or price,
            )

            self.wallet_orchestrator.record_success(intent.wallet_address)

            if result_order.tx_signature:
                record_transaction(
                    tx_signature=result_order.tx_signature,
                    wallet_address=intent.wallet_address,
                    transaction_type=f"swap_{intent.side}",
                    amount_sol=intent.amount_sol,
                    order_id=order_id,
                    status="confirmed",
                )
        else:
            self._stats["trades_failed"] += 1
            self.wallet_orchestrator.record_failure(intent.wallet_address)

        # Update risk manager
        self.risk_manager.record_trade_executed(intent, success)

    # ── Transaction Signing ─────────────────────────────────────────

    async def _sign_and_send_transaction(self, tx_bytes: bytes, wallet_address: str) -> str:
        """
        Sign a Jupiter swap transaction with the wallet's private key and send to Solana.

        Uses solders for transaction deserialization and signing,
        and solana-py async client for RPC submission.
        """
        from solders.keypair import Keypair
        from solders.transaction import VersionedTransaction
        from solana.rpc.async_api import AsyncClient

        # 1. Get the decrypted private key
        key_bytes = self.wallet_orchestrator.get_signing_key(wallet_address)
        if not key_bytes:
            raise Exception("Failed to retrieve signing key from encrypted keystore")

        # 2. Create Keypair (handle both 64-byte full keypair and 32-byte seed)
        if len(key_bytes) == 64:
            keypair = Keypair.from_bytes(key_bytes)
        elif len(key_bytes) == 32:
            keypair = Keypair.from_seed(key_bytes)
        else:
            raise Exception(f"Invalid key length: {len(key_bytes)} (expected 32 or 64)")

        # 3. Deserialize the transaction Jupiter gave us
        unsigned_tx = VersionedTransaction.from_bytes(tx_bytes)

        # 4. Sign it — create new VersionedTransaction with the message and our keypair
        signed_tx = VersionedTransaction(unsigned_tx.message, [keypair])

        # 5. Send to Solana RPC
        rpc_url = os.getenv("RPC_URL", settings.rpc_url)
        async with AsyncClient(rpc_url) as rpc_client:
            # send_raw_transaction expects bytes
            resp = await rpc_client.send_raw_transaction(
                bytes(signed_tx),
                opts={"skip_preflight": False, "preflight_commitment": "confirmed"},
            )

            if hasattr(resp, 'value') and resp.value:
                tx_sig = str(resp.value)
                logger.info(f"Transaction sent: {tx_sig[:20]}...")

                # Wait briefly for confirmation
                await self._wait_for_confirmation(rpc_client, tx_sig)

                return tx_sig
            else:
                error_msg = str(resp) if resp else "No response"
                raise Exception(f"Transaction send failed: {error_msg}")

    async def _wait_for_confirmation(self, rpc_client, tx_sig: str, timeout_s: float = 30.0):
        """Wait for transaction confirmation on-chain."""
        start = time.time()
        while time.time() - start < timeout_s:
            try:
                resp = await rpc_client.get_signature_statuses([tx_sig])
                if resp and hasattr(resp, 'value') and resp.value and resp.value[0]:
                    status = resp.value[0]
                    if hasattr(status, 'err') and status.err:
                        logger.error(f"Transaction failed on-chain: {status.err}")
                        return
                    conf = getattr(status, 'confirmation_status', None)
                    if conf and str(conf) in ("confirmed", "finalized"):
                        logger.info(f"Transaction confirmed: {tx_sig[:16]}...")
                        return
            except Exception as e:
                logger.debug(f"Confirmation check: {e}")

            await asyncio.sleep(1.5)

        logger.warning(f"Transaction confirmation timed out (may still confirm): {tx_sig[:16]}...")

    # ── Profit-Taking ───────────────────────────────────────────────

    async def _check_profit_taking(self, price: float, analysis):
        """Check if profit-taking schedule requires action."""
        step = self.profit_taker.get_next_step(
            current_price=price,
            wyckoff_phase=analysis.phase.value,
        )

        if step and step.amount > 0:
            logger.info(f"Profit-taking step: sell {step.amount} ({step.reason})")

            wallet = self.wallet_orchestrator.get_wallet(
                strategy=SelectionStrategy.WEIGHTED,
                min_balance=0.01,
            )
            if wallet:
                intent = TradeIntent(
                    wallet_address=wallet.address,
                    token_mint=self.token_mint,
                    side="sell",
                    amount_sol=step.amount,
                    expected_price=price,
                    strategy_reason=f"profit_taking: {step.reason}",
                )

                decision = self.risk_manager.evaluate_trade(intent)
                if decision.action == RiskAction.APPROVED:
                    await self._execute_trade(intent, price)

    # ── Status & Config ─────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "token_mint": self.token_mint,
            "cycle_count": self._cycle_count,
            "cycle_interval_s": self._cycle_interval_s,
            "last_price": self._last_price,
            "current_phase": self.wyckoff.get_current_phase().value,
            "stats": self._stats,
            "risk": self.risk_manager.get_status(),
            "wallet_pool": self.wallet_orchestrator.get_pool_status(),
            "profit_taking": self.profit_taker.get_status(),
            "order_fill_rate": self.order_manager.get_fill_rate(),
            "active_orders": self.order_manager.get_active_orders(),
            "recent_orders": self.order_manager.get_completed_orders(10),
            "trading_config": {
                "base_trade_size_sol": self.trading_config.base_trade_size_sol,
                "stop_loss_percent": self.trading_config.stop_loss_percent,
                "min_confidence": self.trading_config.min_confidence,
                "max_slippage_percent": self.trading_config.max_slippage_percent,
            },
        }

    def set_cycle_interval(self, seconds: float):
        self._cycle_interval_s = max(5.0, seconds)
        logger.info(f"Cycle interval set to {self._cycle_interval_s}s")

    def update_trading_config(self, **kwargs):
        """Update trading config at runtime."""
        for key, value in kwargs.items():
            if hasattr(self.trading_config, key):
                setattr(self.trading_config, key, value)
                logger.info(f"Trading config updated: {key} = {value}")
