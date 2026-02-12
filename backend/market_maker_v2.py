"""
Market Maker V2 — Percentage-Based Capital Allocation with Capital Brain

Flow per cycle:
1. Refresh Capital Brain (SOL/USD price + wallet balances)
2. Fetch market data (price via Jupiter)
3. Feed to Wyckoff detector -> get phase + signal
4. Check stop losses on open positions (phase-aware)
5. If signal suggests trade -> create TradeIntent with dynamic sizing
6. Risk Manager evaluates -> APPROVED / REJECTED / HALTED
7. If approved -> Order Manager executes via Jupiter (sign & send)
8. Record everything to database
9. Check profit-taking schedule
10. Sleep and repeat

Trading Strategy:
- BUY token with SOL when Wyckoff signals accumulation + phase allows buying
- SELL token for SOL when Wyckoff signals distribution + phase allows selling
- Trade sizes are percentages of phase capital allocation, NOT fixed SOL amounts
- Phase 1 (Stealth Accumulation): force buy mode, block sells
- All trades gated by percentage-based risk manager
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
    record_capital_snapshot,
)
from backend.strategy.wyckoff import (
    WyckoffDetector, MarketSnapshot, WyckoffPhase, TradeSignal,
)
from backend.profit_taker import ProfitTaker
from backend.dex.jupiter import JupiterAdapter
from backend.wallet_manager import WalletOrchestrator, SelectionStrategy
from backend.capital_brain import CapitalBrain
from backend.trade_size_calculator import TradeSizeCalculator
from backend.phase_config import (
    BondingCurvePhase, PhaseConfig, DEFAULT_PHASE_CONFIGS, get_phase_config,
)

logger = logging.getLogger("market_maker_v2")


@dataclass
class TradingConfig:
    """
    Configurable trading parameters — percentage-based via Capital Brain.
    Phase-specific settings (trade sizes, multipliers) come from PhaseConfig.
    These are global overrides that apply across all phases.
    """
    # Signal filtering
    min_confidence: float = 0.5

    @classmethod
    def from_env(cls) -> "TradingConfig":
        """Load config from environment variables with sensible defaults."""
        return cls(
            min_confidence=float(os.getenv("MIN_CONFIDENCE", "0.5")),
        )


class MarketMakerV2:
    """
    Production market maker with percentage-based capital allocation.

    Automated strategy:
    - Capital Brain tracks USD budget and converts percentages to SOL
    - Bonding curve phases control capital allocation and trade sizing
    - Wyckoff signals control when to buy/sell within each phase
    - All risk limits are percentages of total budget
    """

    def __init__(
        self,
        wallet_orchestrator: WalletOrchestrator,
        token_mint: str,
        capital_brain: CapitalBrain,
        trade_calculator: TradeSizeCalculator,
        risk_manager: RiskManager = None,
        order_manager: OrderManager = None,
        wyckoff_detector: WyckoffDetector = None,
        profit_taker: ProfitTaker = None,
        jupiter: JupiterAdapter = None,
        trading_config: TradingConfig = None,
        initial_phase: BondingCurvePhase = BondingCurvePhase.STEALTH_ACCUMULATION,
    ):
        self.wallet_orchestrator = wallet_orchestrator
        self.token_mint = token_mint
        self.capital_brain = capital_brain
        self.trade_calculator = trade_calculator

        self.risk_manager = risk_manager or RiskManager(capital_brain=capital_brain)
        self.order_manager = order_manager or OrderManager()
        self.wyckoff = wyckoff_detector or WyckoffDetector()
        self.profit_taker = profit_taker or ProfitTaker()
        self.jupiter = jupiter or JupiterAdapter()
        self.trading_config = trading_config or TradingConfig.from_env()

        # Phase management
        self.current_phase = initial_phase
        self.phase_config = get_phase_config(initial_phase)

        # Apply phase config to risk manager
        self.risk_manager.update_from_phase_config(self.phase_config)

        # State
        self._running = False
        self._cycle_count = 0
        self._last_price = 0.0
        self._cycle_interval_s = self.phase_config.cycle_interval_s
        self._capital_snapshot_interval = 50  # Record capital snapshot every N cycles

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
                        f"token:{self.token_mint}", "success",
                        {"phase": self.current_phase.value,
                         "budget_usd": self.capital_brain.total_budget_usd})

        logger.info(f"Market Maker V2 started for token {self.token_mint[:12]}...")
        logger.info(f"Phase: {self.phase_config.phase_name}")
        logger.info(f"Budget: ${self.capital_brain.total_budget_usd:.0f} USD")
        logger.info(f"Cycle interval: {self._cycle_interval_s}s")

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

    # ── Phase Management ─────────────────────────────────────────────

    def set_phase(self, phase: BondingCurvePhase):
        """Manually set the bonding curve phase."""
        old_phase = self.current_phase
        self.current_phase = phase
        self.phase_config = get_phase_config(phase)

        # Update cycle interval
        self._cycle_interval_s = self.phase_config.cycle_interval_s

        # Update risk manager limits
        self.risk_manager.update_from_phase_config(self.phase_config)

        log_audit_event("system", "operator", "phase_transition",
                        f"token:{self.token_mint}", "success",
                        {"from": old_phase.value, "to": phase.value})

        logger.info(
            f"Phase transition: {old_phase.value} -> {phase.value} "
            f"({self.phase_config.phase_name})"
        )

    # ── Main Cycle ──────────────────────────────────────────────────

    async def _run_cycle(self):
        """One complete market making cycle — all layers working together."""
        self._cycle_count += 1
        cycle_start = time.time()

        try:
            # ── Capital Brain Refresh ────────────────────────────────
            await self.capital_brain.refresh(self.wallet_orchestrator)

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
                    f"confidence={analysis.confidence:.0%} "
                    f"bonding_phase={self.current_phase.value} "
                    f"capital_util={self.capital_brain.capital_utilization_pct:.1f}%"
                )

            # ── Stop Loss Check ─────────────────────────────────────
            await self._check_stop_losses(price)

            # ── Layer 7: Check Profit-Taking Schedule ───────────────
            await self._check_profit_taking(price, analysis)

            # ── Generate Trade Intent from Signal ───────────────────
            trade_intent = await self._signal_to_intent(analysis, price)
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

            # ── Capital Snapshot ─────────────────────────────────────
            if self._cycle_count % self._capital_snapshot_interval == 0:
                self._record_capital_snapshot()

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
        Respects phase config: stop loss can be disabled (e.g., during accumulation).
        """
        if not self.phase_config.stop_loss_enabled:
            return  # Stop loss disabled for this phase

        stop_loss_pct = self.phase_config.stop_loss_pct
        if stop_loss_pct <= 0:
            return

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

            if loss_pct >= stop_loss_pct:
                wallet_addr = pos["wallet_address"]
                logger.warning(
                    f"STOP LOSS triggered: wallet {wallet_addr[:8]}... "
                    f"loss={loss_pct:.1f}% (threshold: {stop_loss_pct}%)"
                )
                self._stats["stop_losses_triggered"] += 1

                # Calculate max sell size from phase config
                phase_alloc_usd = self.capital_brain.get_phase_allocation_usd(
                    self.phase_config.phase_capital_allocation_pct
                )
                max_trade_usd = (self.phase_config.max_trade_size_pct / 100) * phase_alloc_usd
                max_trade_sol = self.capital_brain.usd_to_sol(max_trade_usd)

                # Create forced sell intent
                intent = TradeIntent(
                    wallet_address=wallet_addr,
                    token_mint=self.token_mint,
                    side="sell",
                    amount_sol=min(pos["quantity"], max_trade_sol),
                    expected_price=current_price,
                    max_slippage_percent=self.phase_config.max_slippage_pct,
                    strategy_reason=f"STOP_LOSS: {loss_pct:.1f}% loss (threshold: {stop_loss_pct}%)",
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

    async def _signal_to_intent(self, analysis, price: float) -> Optional[TradeIntent]:
        """
        Convert a Wyckoff signal into a TradeIntent with dynamic sizing.

        The bonding curve phase controls:
        - Whether buy/sell signals are allowed (force_buy_mode blocks sells)
        - Trade size as percentage of phase capital allocation
        - Slippage tolerance

        Wyckoff signals control:
        - Whether to trade at all (signal + confidence)
        - Trade direction (buy vs sell)
        - Signal strength multiplier (STRONG signals get larger trades)
        """
        # Only act on signals with sufficient confidence
        if analysis.confidence < self.trading_config.min_confidence:
            return None

        # Phase-level signal filtering
        if self.phase_config.force_buy_mode:
            # In force_buy_mode, block all sell signals
            if analysis.signal in (TradeSignal.SELL, TradeSignal.STRONG_SELL):
                logger.debug(
                    f"Phase '{self.phase_config.phase_name}' blocks sell signals (force_buy_mode)"
                )
                return None
            # In force_buy_mode, convert HOLD to BUY if confidence is high enough
            if analysis.signal == TradeSignal.HOLD:
                return None

        # Skip HOLD signals
        if analysis.signal == TradeSignal.HOLD:
            return None

        # Calculate trade size dynamically from phase config
        trade_sol = await self.trade_calculator.calculate(
            signal=analysis.signal,
            phase_config=self.phase_config,
        )

        if trade_sol <= 0:
            return None  # Unaffordable or zero size

        # Select wallet for this trade
        wallet = self.wallet_orchestrator.get_wallet(
            strategy=SelectionStrategy.HEALTH_BASED,
            min_balance=trade_sol if analysis.signal in (TradeSignal.BUY, TradeSignal.STRONG_BUY) else 0.01,
        )
        if not wallet:
            logger.warning("No wallet available for trade")
            return None

        # Determine side
        if analysis.signal in (TradeSignal.BUY, TradeSignal.STRONG_BUY):
            side = "buy"
        else:
            side = "sell"

        trade_usd = self.capital_brain.sol_to_usd(trade_sol)
        logger.info(
            f"Trade intent: {side} {trade_sol:.4f} SOL (${trade_usd:.2f}) "
            f"[{self.phase_config.phase_name}, {analysis.signal.value}]"
        )

        return TradeIntent(
            wallet_address=wallet.address,
            token_mint=self.token_mint,
            side=side,
            amount_sol=trade_sol,
            expected_price=price,
            max_slippage_percent=self.phase_config.max_slippage_pct,
            strategy_reason=(
                f"{self.phase_config.phase_name} | {analysis.reason} | "
                f"${trade_usd:.2f} ({self.phase_config.base_trade_size_pct}% of phase)"
            ),
        )

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
                    max_slippage_percent=self.phase_config.max_slippage_pct,
                    strategy_reason=f"profit_taking: {step.reason}",
                )

                decision = self.risk_manager.evaluate_trade(intent)
                if decision.action == RiskAction.APPROVED:
                    await self._execute_trade(intent, price)

    # ── Capital Snapshots ───────────────────────────────────────────

    def _record_capital_snapshot(self):
        """Record current capital state to database."""
        try:
            record_capital_snapshot(
                total_budget_usd=self.capital_brain.total_budget_usd,
                deployed_capital_usd=self.capital_brain.deployed_capital_usd,
                available_capital_usd=self.capital_brain.available_capital_usd,
                sol_usd_price=self.capital_brain.sol_price_usd,
                bonding_curve_phase=self.current_phase.value,
                capital_utilization_pct=self.capital_brain.capital_utilization_pct,
            )
        except Exception as e:
            logger.debug(f"Failed to record capital snapshot: {e}")

    # ── Status & Config ─────────────────────────────────────────────

    def get_status(self) -> dict:
        return {
            "running": self._running,
            "token_mint": self.token_mint,
            "cycle_count": self._cycle_count,
            "cycle_interval_s": self._cycle_interval_s,
            "last_price": self._last_price,
            "current_wyckoff_phase": self.wyckoff.get_current_phase().value,
            "stats": self._stats,
            "risk": self.risk_manager.get_status(),
            "wallet_pool": self.wallet_orchestrator.get_pool_status(),
            "profit_taking": self.profit_taker.get_status(),
            "order_fill_rate": self.order_manager.get_fill_rate(),
            "active_orders": self.order_manager.get_active_orders(),
            "recent_orders": self.order_manager.get_completed_orders(10),
            # Capital Brain status
            "capital": self.capital_brain.get_status(),
            # Bonding curve phase info
            "bonding_phase": {
                "current": self.current_phase.value,
                "config": self.phase_config.to_dict(),
                "effective_sizes": self.trade_calculator.get_effective_sizes(self.phase_config),
            },
            "trading_config": {
                "min_confidence": self.trading_config.min_confidence,
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
