"""
FastAPI Server — Integrated v2 with Backward-Compatible v1 Routes

The v2 architecture layers:
- Auth middleware (API key + rate limiting, localhost bypass for dev)
- Risk management with circuit breakers and stop losses
- Multi-wallet orchestration with encrypted keystore
- Wyckoff phase detection for automated buy/sell signals
- Jupiter DEX integration for real Solana swaps
- Order management with retry logic
- Profit-taking schedules (TWAP, price targets)
- SQLite persistence + audit trail
- WebSocket for real-time status

v1 endpoints (/api/status, /api/marketmaker/start, etc.) still work for the existing frontend.
"""

import os
import json
import asyncio
import logging
from pathlib import Path
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional

from dotenv import load_dotenv
load_dotenv()

# Import all v2 layers
from backend.auth import AuthMiddleware, load_api_key_from_env, get_bind_host
from backend.risk_manager import RiskManager, RiskRules, TradeIntent
from backend.order_manager import OrderManager
from backend.database import (
    init_database, get_recent_orders, get_open_positions,
    get_audit_log, get_trade_stats, get_daily_pnl,
)
from backend.wallet_manager import (
    EncryptedKeyStore, WalletOrchestrator, WalletRole, SelectionStrategy,
)
from backend.strategy.wyckoff import WyckoffDetector
from backend.profit_taker import ProfitTaker
from backend.dex.jupiter import JupiterAdapter
from backend.market_maker_v2 import MarketMakerV2, TradingConfig
from backend.config import settings

# ── Logging Setup ───────────────────────────────────────────────────

os.makedirs("data", exist_ok=True)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(name)s] %(levelname)s: %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler("data/market_maker.log"),
    ],
)
logger = logging.getLogger("main")

# ── Global State ────────────────────────────────────────────────────

market_maker: Optional[MarketMakerV2] = None
mm_task: Optional[asyncio.Task] = None
risk_manager = RiskManager()
wallet_orchestrator: Optional[WalletOrchestrator] = None
profit_taker = ProfitTaker()

# Take profit targets: wallet_address -> {token_mint, profit_percentage, initial_price, auto_sell}
take_profit_targets: dict[str, dict] = {}


# ── App Lifecycle ───────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup
    os.makedirs("data", exist_ok=True)
    init_database()
    load_api_key_from_env()

    # Initialize encrypted keystore
    passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "change-this-in-production")
    keystore = EncryptedKeyStore(passphrase)
    global wallet_orchestrator
    wallet_orchestrator = WalletOrchestrator(keystore)

    # Auto-import existing wallet.json if it exists (v1 compatibility)
    _auto_import_legacy_wallet(keystore, wallet_orchestrator)

    # Re-register wallets already in the encrypted keystore
    _restore_keystore_wallets(keystore, wallet_orchestrator)

    logger.info("Server starting — all layers initialized")
    yield

    # Shutdown
    if market_maker:
        market_maker.stop()
    logger.info("Server shutting down")


def _auto_import_legacy_wallet(keystore: EncryptedKeyStore, orchestrator: WalletOrchestrator):
    """If a wallet.json exists from v1, import it into the encrypted keystore."""
    wallet_path = Path(settings.wallet_path)
    if not wallet_path.exists():
        return

    try:
        with open(wallet_path, 'r') as f:
            key_data = json.load(f)

        if isinstance(key_data, list):
            key_bytes = bytes(key_data)
        else:
            secret_key = key_data.get('secretKey') or key_data.get('privateKey')
            if secret_key:
                if isinstance(secret_key, str):
                    import base58
                    key_bytes = base58.b58decode(secret_key)
                else:
                    key_bytes = bytes(secret_key)
            else:
                return

        # Derive public key from the keypair bytes
        from solders.keypair import Keypair
        if len(key_bytes) == 64:
            keypair = Keypair.from_bytes(key_bytes)
        elif len(key_bytes) == 32:
            keypair = Keypair.from_seed(key_bytes)
        else:
            logger.warning(f"Unexpected key length in wallet.json: {len(key_bytes)}")
            return

        address = str(keypair.pubkey())

        # Check if already in keystore
        existing = keystore.list_addresses()
        if address not in existing:
            keystore.store_key(address, bytes(keypair), label="legacy_v1_wallet")
            orchestrator.register_wallet(address, role=WalletRole.TRADING, label="v1 imported")
            logger.info(f"Auto-imported legacy wallet.json → {address[:8]}...")
        else:
            # Still register in pool if not already
            if not orchestrator.get_wallet_info(address):
                orchestrator.register_wallet(address, role=WalletRole.TRADING, label="v1 imported")

    except Exception as e:
        logger.warning(f"Could not auto-import wallet.json: {e}")


def _restore_keystore_wallets(keystore: EncryptedKeyStore, orchestrator: WalletOrchestrator):
    """Re-register wallets that are in the keystore but not in the pool (e.g., after restart)."""
    for address in keystore.list_addresses():
        if not orchestrator.get_wallet_info(address):
            orchestrator.register_wallet(address, role=WalletRole.TRADING, label="keystore")
            logger.info(f"Restored wallet from keystore: {address[:8]}...")


app = FastAPI(
    title="Solana Market Maker",
    description="Automated market maker with Wyckoff strategy, risk management, and Jupiter DEX integration",
    version="2.0.0",
    lifespan=lifespan,
)

# Middleware — order matters: CORSMiddleware is outer (processes first), AuthMiddleware is inner
app.add_middleware(AuthMiddleware)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000",
        "http://localhost:5173",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:5173",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


# ══════════════════════════════════════════════════════════════════════
# v2 Pydantic Models
# ══════════════════════════════════════════════════════════════════════

class StartRequest(BaseModel):
    token_mint: str
    cycle_interval_s: float = 15.0


class WalletRegisterRequest(BaseModel):
    address: str
    private_key_hex: str  # Encrypted immediately on receipt
    role: str = "trading"
    label: str = ""


class RiskRulesUpdate(BaseModel):
    max_drawdown_percent: Optional[float] = None
    max_daily_volume: Optional[float] = None
    total_max_exposure: Optional[float] = None
    max_trades_per_minute: Optional[int] = None
    max_consecutive_losses: Optional[int] = None
    stop_loss_percent: Optional[float] = None


class TradingConfigUpdate(BaseModel):
    base_trade_size_sol: Optional[float] = None
    strong_signal_multiplier: Optional[float] = None
    stop_loss_percent: Optional[float] = None
    min_confidence: Optional[float] = None
    max_slippage_percent: Optional[float] = None


class ProfitTargetRequest(BaseModel):
    targets: list[dict]


class TWAPRequest(BaseModel):
    total_amount: float
    duration_hours: float
    num_steps: Optional[int] = None


# Legacy v1 models
class MarketMakerConfig(BaseModel):
    spread_percentage: Optional[float] = None
    order_size: Optional[float] = None
    min_balance: Optional[float] = None

class WalletImportRequest(BaseModel):
    private_key: str


class ActiveWalletsRequest(BaseModel):
    addresses: list[str]


class WalletTradeRequest(BaseModel):
    token_mint: str
    side: str  # "buy" or "sell"
    percentage: float = 5.0  # Percentage of wallet balance to use
    max_slippage: float = 2.0


class TakeProfitRequest(BaseModel):
    wallet_address: str
    token_mint: str
    profit_percentage: float  # Take profit when token value increases by this %
    auto_sell: bool = True  # Automatically sell when target is reached


# ══════════════════════════════════════════════════════════════════════
# HEALTH CHECK (no auth)
# ══════════════════════════════════════════════════════════════════════

@app.get("/health")
async def health():
    return {"status": "ok", "version": "2.0.0"}


# ══════════════════════════════════════════════════════════════════════
# v2 ENDPOINTS — Full architecture
# ══════════════════════════════════════════════════════════════════════

# ── Market Maker Control ────────────────────────────────────────────

@app.post("/api/v2/start")
async def start_market_maker_v2(req: StartRequest):
    global market_maker, mm_task

    if market_maker and market_maker._running:
        raise HTTPException(400, "Market maker already running")

    if not wallet_orchestrator:
        raise HTTPException(400, "Wallet orchestrator not initialized")

    pool_status = wallet_orchestrator.get_pool_status()
    if pool_status["total_wallets"] == 0:
        raise HTTPException(400, "No wallets registered. Add wallets first.")

    market_maker = MarketMakerV2(
        wallet_orchestrator=wallet_orchestrator,
        token_mint=req.token_mint,
        risk_manager=risk_manager,
        profit_taker=profit_taker,
    )
    market_maker.set_cycle_interval(req.cycle_interval_s)

    mm_task = asyncio.create_task(market_maker.start())
    return {"status": "started", "token_mint": req.token_mint}


@app.post("/api/v2/stop")
async def stop_market_maker_v2():
    global market_maker, mm_task
    if market_maker:
        market_maker.stop()
        if mm_task:
            mm_task.cancel()
        return {"status": "stopped"}
    raise HTTPException(400, "Market maker not running")


@app.get("/api/v2/status")
async def get_status_v2():
    if market_maker:
        return market_maker.get_status()
    return {
        "running": False,
        "risk": risk_manager.get_status(),
        "wallet_pool": wallet_orchestrator.get_pool_status() if wallet_orchestrator else {},
        "profit_taking": profit_taker.get_status(),
    }


# ── Wallet Management ──────────────────────────────────────────────

@app.post("/api/v2/wallets/register")
async def register_wallet(req: WalletRegisterRequest):
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")

    try:
        key_bytes = bytes.fromhex(req.private_key_hex)
        wallet_orchestrator.keystore.store_key(
            req.address, key_bytes, label=req.label
        )

        role = WalletRole(req.role) if req.role in [r.value for r in WalletRole] else WalletRole.TRADING
        info = wallet_orchestrator.register_wallet(req.address, role=role, label=req.label)

        return {"status": "registered", "wallet": info.to_dict()}
    except Exception as e:
        raise HTTPException(400, f"Failed to register wallet: {e}")


@app.get("/api/v2/wallets")
async def list_wallets():
    if not wallet_orchestrator:
        return {"wallets": []}
    return wallet_orchestrator.get_pool_status()


@app.post("/api/v2/wallets/{address}/disable")
async def disable_wallet(address: str):
    if wallet_orchestrator:
        wallet_orchestrator.disable_wallet(address)
    return {"status": "disabled"}


@app.post("/api/v2/wallets/{address}/enable")
async def enable_wallet(address: str):
    if wallet_orchestrator:
        wallet_orchestrator.enable_wallet(address)
    return {"status": "enabled"}


@app.post("/api/v2/wallets/active")
async def set_active_wallets(req: ActiveWalletsRequest):
    """Set which wallets are active for display and manual trading."""
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")
    wallet_orchestrator.set_active_wallets(req.addresses)
    return {"status": "updated", "active_wallets": wallet_orchestrator.get_active_wallets()}


@app.get("/api/v2/wallets/active")
async def get_active_wallets():
    """Get list of active wallet addresses."""
    if not wallet_orchestrator:
        return {"active_wallets": []}
    return {"active_wallets": wallet_orchestrator.get_active_wallets()}


@app.post("/api/v2/wallets/{address}/active")
async def toggle_active_wallet(address: str):
    """Add or remove a wallet from the active set."""
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")
    
    active = wallet_orchestrator.get_active_wallets()
    if address in active:
        wallet_orchestrator.remove_active_wallet(address)
        return {"status": "removed", "active": False}
    else:
        wallet_orchestrator.add_active_wallet(address)
        return {"status": "added", "active": True}


@app.post("/api/v2/wallets/{address}/trade")
async def wallet_trade(address: str, req: WalletTradeRequest):
    """Execute a small buy or sell trade for a specific wallet."""
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")
    
    wallet_info = wallet_orchestrator.get_wallet_info(address)
    if not wallet_info:
        raise HTTPException(404, f"Wallet {address} not found")
    
    if wallet_info["health"] == "disabled":
        raise HTTPException(400, "Wallet is disabled")
    
    # Calculate trade amount (percentage of wallet balance)
    balance_sol = wallet_info["balance_sol"]
    trade_amount_sol = balance_sol * (req.percentage / 100.0)
    
    if trade_amount_sol < 0.01:
        raise HTTPException(400, f"Insufficient balance for {req.percentage}% trade")
    
    # Get signing key
    signing_key = wallet_orchestrator.get_signing_key(address)
    if not signing_key:
        raise HTTPException(500, "Failed to get wallet signing key")
    
    # Initialize Jupiter adapter
    jupiter = JupiterAdapter()
    
    # Execute swap
    try:
        from solana.rpc.async_api import AsyncClient
        from solders.keypair import Keypair
        from solders.transaction import VersionedTransaction
        
        # Create keypair from signing key
        if len(signing_key) == 64:
            keypair = Keypair.from_bytes(signing_key)
        elif len(signing_key) == 32:
            keypair = Keypair.from_seed(signing_key)
        else:
            raise Exception(f"Invalid key length: {len(signing_key)}")
        
        wallet_pubkey = str(keypair.pubkey())
        
        async def sign_and_send(tx_bytes: bytes) -> str:
            """Sign and send transaction."""
            from solana.rpc.async_api import AsyncClient
            from solders.transaction import VersionedTransaction
            
            # Deserialize transaction
            unsigned_tx = VersionedTransaction.from_bytes(tx_bytes)
            # Sign it
            signed_tx = VersionedTransaction(unsigned_tx.message, [keypair])
            
            # Send to Solana
            rpc_url = os.getenv("RPC_URL", settings.rpc_url)
            async with AsyncClient(rpc_url) as client:
                result = await client.send_transaction(signed_tx)
                return str(result.value) if result.value else ""
        
        result = await jupiter.execute_swap(
            wallet_address=wallet_pubkey,
            token_mint=req.token_mint,
            side=req.side,
            amount_sol=trade_amount_sol,
            max_slippage=req.max_slippage,
            sign_and_send=sign_and_send,
        )
        
        # Update wallet balance
        rpc_url = os.getenv("RPC_URL", settings.rpc_url)
        await wallet_orchestrator.refresh_balances(rpc_url)
        
        return {
            "status": "success",
            "wallet": address,
            "side": req.side,
            "amount_sol": trade_amount_sol,
            "percentage": req.percentage,
            "transaction": result.get("signature"),
        }
    except Exception as e:
        logger.error(f"Wallet trade failed: {e}")
        raise HTTPException(500, f"Trade execution failed: {str(e)}")


@app.post("/api/v2/wallets/{address}/take-profit")
async def set_take_profit(address: str, req: TakeProfitRequest):
    """Set a take profit target for a wallet's token position."""
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")
    
    wallet_info = wallet_orchestrator.get_wallet_info(address)
    if not wallet_info:
        raise HTTPException(404, f"Wallet {address} not found")
    
    # Get current token price from Jupiter
    jupiter = JupiterAdapter()
    current_price = await jupiter.get_price_in_sol(req.token_mint)
    
    if current_price is None:
        raise HTTPException(400, "Failed to get token price from Jupiter")
    
    # Store take profit target
    take_profit_targets[address] = {
        "token_mint": req.token_mint,
        "profit_percentage": req.profit_percentage,
        "initial_price": current_price,
        "auto_sell": req.auto_sell,
        "target_price": current_price * (1 + req.profit_percentage / 100.0),
    }
    
    logger.info(f"Take profit set for {address[:8]}...: {req.profit_percentage}% target")
    
    return {
        "status": "set",
        "wallet": address,
        "token_mint": req.token_mint,
        "initial_price": current_price,
        "target_price": take_profit_targets[address]["target_price"],
        "profit_percentage": req.profit_percentage,
    }


@app.get("/api/v2/wallets/{address}/take-profit")
async def get_take_profit(address: str):
    """Get take profit target for a wallet."""
    target = take_profit_targets.get(address)
    if not target:
        return {"status": "not_set"}
    
    # Get current price
    jupiter = JupiterAdapter()
    current_price = await jupiter.get_price_in_sol(target["token_mint"])
    
    if current_price is None:
        current_price = target["initial_price"]
    
    profit_pct = ((current_price - target["initial_price"]) / target["initial_price"]) * 100.0
    
    return {
        "status": "active",
        "wallet": address,
        "token_mint": target["token_mint"],
        "initial_price": target["initial_price"],
        "current_price": current_price,
        "target_price": target["target_price"],
        "profit_percentage": target["profit_percentage"],
        "current_profit_pct": profit_pct,
        "auto_sell": target["auto_sell"],
        "target_reached": current_price >= target["target_price"],
    }


@app.delete("/api/v2/wallets/{address}/take-profit")
async def remove_take_profit(address: str):
    """Remove take profit target for a wallet."""
    if address in take_profit_targets:
        del take_profit_targets[address]
        logger.info(f"Take profit removed for {address[:8]}...")
        return {"status": "removed"}
    return {"status": "not_found"}


# ── Risk Management ─────────────────────────────────────────────────

@app.get("/api/v2/risk")
async def get_risk_status():
    return risk_manager.get_status()


@app.put("/api/v2/risk/rules")
async def update_risk_rules(rules: RiskRulesUpdate):
    updates = {k: v for k, v in rules.model_dump().items() if v is not None}
    risk_manager.update_rules(**updates)
    return {"status": "updated", "rules": updates}


@app.post("/api/v2/risk/emergency-shutdown")
async def emergency_shutdown():
    risk_manager.emergency_shutdown()
    if market_maker:
        market_maker.stop()
    return {"status": "emergency_shutdown_activated"}


@app.post("/api/v2/risk/reset-emergency")
async def reset_emergency():
    risk_manager.reset_emergency()
    return {"status": "emergency_cleared"}


@app.post("/api/v2/risk/reset-circuit-breaker")
async def reset_circuit_breaker():
    risk_manager.circuit_breaker.reset()
    return {"status": "circuit_breaker_reset"}


# ── Trading Config ──────────────────────────────────────────────────

@app.get("/api/v2/trading/config")
async def get_trading_config():
    if market_maker:
        cfg = market_maker.trading_config
        return {
            "base_trade_size_sol": cfg.base_trade_size_sol,
            "strong_signal_multiplier": cfg.strong_signal_multiplier,
            "stop_loss_percent": cfg.stop_loss_percent,
            "min_confidence": cfg.min_confidence,
            "max_slippage_percent": cfg.max_slippage_percent,
            "min_trade_size_sol": cfg.min_trade_size_sol,
            "max_trade_size_sol": cfg.max_trade_size_sol,
        }
    # Return defaults from env
    cfg = TradingConfig.from_env()
    return {
        "base_trade_size_sol": cfg.base_trade_size_sol,
        "stop_loss_percent": cfg.stop_loss_percent,
        "min_confidence": cfg.min_confidence,
        "max_slippage_percent": cfg.max_slippage_percent,
    }


@app.put("/api/v2/trading/config")
async def update_trading_config(cfg: TradingConfigUpdate):
    updates = {k: v for k, v in cfg.model_dump().items() if v is not None}
    if market_maker:
        market_maker.update_trading_config(**updates)
    # Also update risk manager stop loss if provided
    if "stop_loss_percent" in updates:
        risk_manager.update_rules(stop_loss_percent=updates["stop_loss_percent"])
    return {"status": "updated", "config": updates}


# ── Profit-Taking ───────────────────────────────────────────────────

@app.get("/api/v2/profit-taking")
async def get_profit_taking_status():
    return profit_taker.get_status()


@app.post("/api/v2/profit-taking/twap")
async def create_twap_schedule(req: TWAPRequest):
    schedule = profit_taker.create_twap_schedule(
        total_amount=req.total_amount,
        duration_hours=req.duration_hours,
        num_steps=req.num_steps,
    )
    return {"status": "created", "schedule": schedule.to_dict()}


@app.post("/api/v2/profit-taking/targets")
async def set_price_targets(req: ProfitTargetRequest):
    profit_taker.set_price_targets(req.targets)
    return {"status": "targets_set", "count": len(req.targets)}


@app.post("/api/v2/profit-taking/pause")
async def pause_distribution():
    profit_taker.pause_distribution()
    return {"status": "paused"}


@app.post("/api/v2/profit-taking/resume")
async def resume_distribution():
    profit_taker.resume_distribution()
    return {"status": "resumed"}


@app.post("/api/v2/profit-taking/cancel")
async def cancel_distribution():
    profit_taker.cancel_distribution()
    return {"status": "cancelled"}


# ── Trade History ───────────────────────────────────────────────────

@app.get("/api/v2/orders")
async def get_orders(limit: int = 50):
    return {"orders": get_recent_orders(limit)}


@app.get("/api/v2/positions")
async def get_positions():
    return {"positions": get_open_positions()}


@app.get("/api/v2/stats")
async def get_stats_v2():
    return {
        "overall": get_trade_stats(),
        "daily_pnl": get_daily_pnl(7),
    }


@app.get("/api/v2/audit")
async def get_audit(event_type: Optional[str] = None, limit: int = 100):
    return {"events": get_audit_log(event_type, limit)}


# ── Strategy / Wyckoff ──────────────────────────────────────────────

@app.get("/api/v2/strategy/phase")
async def get_wyckoff_phase():
    if market_maker:
        analysis = market_maker.wyckoff.analyze()
        return analysis.to_dict()
    return {"phase": "unknown", "reason": "Market maker not running"}


# ── WebSocket for Real-Time Updates ─────────────────────────────────

connected_clients: list[WebSocket] = []


@app.websocket("/ws/v2/status")
async def websocket_status(ws: WebSocket):
    """Push-based real-time status updates (replaces polling)."""
    await ws.accept()
    connected_clients.append(ws)
    try:
        while True:
            if market_maker:
                status = market_maker.get_status()
            else:
                status = {
                    "running": False,
                    "risk": risk_manager.get_status(),
                    "wallet_pool": wallet_orchestrator.get_pool_status() if wallet_orchestrator else {},
                }
            await ws.send_json(status)
            await asyncio.sleep(5)
    except Exception:
        pass
    finally:
        if ws in connected_clients:
            connected_clients.remove(ws)


# ══════════════════════════════════════════════════════════════════════
# v1 BACKWARD-COMPATIBLE ENDPOINTS (for the existing React frontend)
# ══════════════════════════════════════════════════════════════════════

@app.get("/")
async def root():
    return {"message": "Solana Market Maker API", "version": "2.0.0"}


@app.get("/api/status")
async def legacy_status():
    """
    v1 status endpoint — returns data in the format the existing frontend expects.
    Maps v2 state to v1 response shape.
    """
    # Refresh balances from Solana
    if wallet_orchestrator:
        rpc_url = os.getenv("RPC_URL", settings.rpc_url)
        await wallet_orchestrator.refresh_balances(rpc_url)
    
    pool = wallet_orchestrator.get_pool_status() if wallet_orchestrator else {
        "total_wallets": 0, "wallets": [], "total_balance_sol": 0
    }
    wallets = pool.get("wallets", [])
    
    # Get primary active wallet, or fallback to first enabled wallet
    primary_wallet = None
    if wallet_orchestrator:
        primary_wallet_info = wallet_orchestrator.get_primary_wallet()
        if primary_wallet_info:
            primary_wallet = {"address": primary_wallet_info.address}
    
    # Fallback to first enabled wallet if no active wallet
    if not primary_wallet:
        enabled_wallets = [w for w in wallets if w.get("health") != "disabled"]
        primary_wallet = enabled_wallets[0] if enabled_wallets else None
        if not primary_wallet and wallets:
            primary_wallet = wallets[0]

    running = market_maker._running if market_maker else False
    stats = market_maker._stats if market_maker else {}

    # Count enabled wallets
    enabled_wallets = [w for w in wallets if w.get("health") != "disabled"]
    enabled_count = len(enabled_wallets)

    return {
        "is_running": running,
        "account": {
            "wallet_loaded": pool["total_wallets"] > 0,
            "public_key": primary_wallet["address"] if primary_wallet else None,
            "balance": pool.get("total_balance_sol", 0),
            "network": os.getenv("SOLANA_NETWORK", settings.solana_network),
            "total_wallets": pool["total_wallets"],
            "enabled_wallets": enabled_count,
            "all_wallets": wallets,  # Include all wallets for reference
        },
        "stats": {
            "total_trades": stats.get("trades_filled", 0),
            "total_profit": 0.0,
            "last_trade_time": None,
            "start_time": stats.get("started_at"),
        },
        "config": {
            "spread_percentage": settings.spread_percentage,
            "order_size": float(os.getenv("BASE_TRADE_SIZE_SOL", str(settings.order_size))),
            "min_balance": settings.min_balance,
            "network": os.getenv("SOLANA_NETWORK", settings.solana_network),
        },
    }


@app.get("/api/account")
async def legacy_account():
    """v1 account endpoint — wallet info from the pool."""
    # Refresh balances from Solana
    if wallet_orchestrator:
        rpc_url = os.getenv("RPC_URL", settings.rpc_url)
        await wallet_orchestrator.refresh_balances(rpc_url)
    
    pool = wallet_orchestrator.get_pool_status() if wallet_orchestrator else {
        "total_wallets": 0, "wallets": [], "total_balance_sol": 0
    }
    wallets = pool.get("wallets", [])
    
    # Get primary active wallet, or fallback to first enabled wallet
    primary_wallet = None
    if wallet_orchestrator:
        primary_wallet_info = wallet_orchestrator.get_primary_wallet()
        if primary_wallet_info:
            primary_wallet = {"address": primary_wallet_info.address}
    
    # Fallback to first enabled wallet if no active wallet
    if not primary_wallet:
        enabled_wallets = [w for w in wallets if w.get("health") != "disabled"]
        primary_wallet = enabled_wallets[0] if enabled_wallets else None
        if not primary_wallet and wallets:
            primary_wallet = wallets[0]
    
    # Count enabled wallets
    enabled_wallets = [w for w in wallets if w.get("health") != "disabled"]
    enabled_count = len(enabled_wallets)

    return {
        "wallet_loaded": pool["total_wallets"] > 0,
        "public_key": primary_wallet["address"] if primary_wallet else None,
        "balance": pool.get("total_balance_sol", 0),
        "network": os.getenv("SOLANA_NETWORK", settings.solana_network),
        "total_wallets": pool["total_wallets"],
        "enabled_wallets": enabled_count,
        "all_wallets": wallets,  # Include all wallets for reference
    }


@app.post("/api/wallet/create")
async def legacy_create_wallet():
    """v1 wallet create — generates new keypair, encrypts and registers it."""
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")

    from solders.keypair import Keypair

    new_keypair = Keypair()
    address = str(new_keypair.pubkey())
    key_bytes = bytes(new_keypair)  # 64-byte keypair

    wallet_orchestrator.keystore.store_key(address, key_bytes, label="created_via_ui")
    wallet_orchestrator.register_wallet(address, role=WalletRole.TRADING, label="created via UI")

    logger.info(f"New wallet created via UI: {address[:8]}...")

    return {
        "public_key": address,
        "message": "Wallet created and registered (encrypted storage)",
    }


@app.post("/api/wallet/refresh-balance")
async def refresh_wallet_balance():
    """Refresh wallet balances from Solana blockchain."""
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")
    
    rpc_url = os.getenv("RPC_URL", settings.rpc_url)
    await wallet_orchestrator.refresh_balances(rpc_url)
    
    pool = wallet_orchestrator.get_pool_status()
    return {
        "success": True,
        "total_balance_sol": pool.get("total_balance_sol", 0),
        "wallets": pool.get("wallets", [])
    }


@app.get("/api/wallet/export/{address}")
async def export_wallet_key(address: str, passphrase: str = None):
    """
    Export wallet private key (requires keystore passphrase for security).
    WARNING: This exposes the private key. Use with extreme caution.
    """
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")
    
    # Verify passphrase matches
    env_passphrase = os.getenv("MM_KEYSTORE_PASSPHRASE", "change-this-in-production")
    if passphrase != env_passphrase:
        raise HTTPException(401, "Invalid passphrase")
    
    # Get the key
    try:
        key_bytes = wallet_orchestrator.get_signing_key(address)
    except Exception as e:
        raise HTTPException(500, f"Error retrieving wallet key: {str(e)}")
    
    if not key_bytes:
        raise HTTPException(404, "Wallet not found")
    
    try:
        import base58
        from solders.keypair import Keypair
        
        # Convert to different formats - handle both 64-byte and 32-byte keys
        if len(key_bytes) == 64:
            keypair = Keypair.from_bytes(key_bytes)
        elif len(key_bytes) == 32:
            keypair = Keypair.from_seed(key_bytes)
        else:
            raise ValueError(f"Invalid key length: {len(key_bytes)}. Expected 32 or 64 bytes.")
    except Exception as e:
        raise HTTPException(500, f"Error converting key: {str(e)}")
    
    # Return in multiple formats for compatibility
    private_key_base58 = base58.b58encode(bytes(keypair)).decode()
    private_key_hex = bytes(keypair).hex()
    private_key_array = list(bytes(keypair))
    
    return {
        "address": address,
        "private_key_base58": private_key_base58,
        "private_key_hex": private_key_hex,
        "private_key_array": private_key_array,
        "warning": "KEEP THIS PRIVATE KEY SECURE! Never share it with anyone."
    }


@app.post("/api/wallet/import")
async def legacy_import_wallet(request: WalletImportRequest):
    """v1 import wallet — accepts private key in various formats."""
    if not wallet_orchestrator:
        raise HTTPException(500, "Wallet orchestrator not initialized")
    
    private_key = request.private_key
    if not private_key:
        raise HTTPException(400, "private_key is required")
    
    try:
        import base58
        from solders.keypair import Keypair
        
        # Handle different input formats
        key_bytes = None
        if isinstance(private_key, str):
            # Try base58 decode first
            try:
                key_bytes = base58.b58decode(private_key)
            except:
                # Try hex
                try:
                    key_bytes = bytes.fromhex(private_key.replace("0x", ""))
                except:
                    # Try as array string
                    try:
                        import json
                        key_array = json.loads(private_key)
                        key_bytes = bytes(key_array)
                    except:
                        raise HTTPException(400, "Invalid private key format")
        elif isinstance(private_key, list):
            key_bytes = bytes(private_key)
        else:
            raise HTTPException(400, "Invalid private key format")
        
        # Create keypair and get address
        if len(key_bytes) == 64:
            keypair = Keypair.from_bytes(key_bytes)
        elif len(key_bytes) == 32:
            keypair = Keypair.from_seed(key_bytes)
        else:
            raise HTTPException(400, f"Invalid key length: {len(key_bytes)}. Expected 32 or 64 bytes.")
        
        address = str(keypair.pubkey())
        
        # Store encrypted and register
        wallet_orchestrator.keystore.store_key(address, bytes(keypair), label="imported_via_ui")
        wallet_orchestrator.register_wallet(address, role=WalletRole.TRADING, label="imported via UI")
        
        logger.info(f"Wallet imported via UI: {address[:8]}...")
        
        return {
            "success": True,
            "public_key": address,
            "message": "Wallet imported and registered (encrypted storage)",
        }
    except Exception as e:
        logger.error(f"Failed to import wallet: {e}")
        raise HTTPException(400, f"Failed to import wallet: {str(e)}")


@app.post("/api/marketmaker/start")
async def legacy_start():
    """v1 start — uses TOKEN_MINT from environment or request."""
    global market_maker, mm_task

    if market_maker and market_maker._running:
        raise HTTPException(400, detail="Market maker already running")

    token_mint = os.getenv("TOKEN_MINT", "")
    if not token_mint:
        raise HTTPException(
            400,
            detail="TOKEN_MINT not set. Set it in .env or use /api/v2/start with token_mint in body.",
        )

    if not wallet_orchestrator or wallet_orchestrator.get_pool_status()["total_wallets"] == 0:
        raise HTTPException(400, detail="No wallets registered. Create or import a wallet first.")

    market_maker = MarketMakerV2(
        wallet_orchestrator=wallet_orchestrator,
        token_mint=token_mint,
        risk_manager=risk_manager,
        profit_taker=profit_taker,
    )

    cycle_interval = float(os.getenv("CYCLE_INTERVAL_S", "15.0"))
    market_maker.set_cycle_interval(cycle_interval)

    mm_task = asyncio.create_task(market_maker.start())

    return {
        "success": True,
        "message": "Market maker started",
        "token_mint": token_mint,
    }


@app.post("/api/marketmaker/stop")
async def legacy_stop():
    """v1 stop."""
    global market_maker, mm_task

    if not market_maker:
        raise HTTPException(400, detail="Market maker not running")

    market_maker.stop()
    if mm_task:
        mm_task.cancel()
        try:
            await mm_task
        except asyncio.CancelledError:
            pass
        mm_task = None

    stats = market_maker._stats if market_maker else {}
    return {
        "success": True,
        "message": "Market maker stopped",
        "stats": stats,
    }


@app.get("/api/marketmaker/stats")
async def legacy_stats():
    """v1 stats endpoint."""
    return await legacy_status()


@app.put("/api/marketmaker/config")
async def legacy_update_config(config: MarketMakerConfig):
    """v1 config update — maps to v2 risk rules and trading config."""
    updates = {}
    if config.order_size is not None:
        if market_maker:
            market_maker.update_trading_config(base_trade_size_sol=config.order_size)
        updates["order_size"] = config.order_size
    if config.min_balance is not None:
        updates["min_balance"] = config.min_balance

    return {
        "success": True,
        "config": {
            "spread_percentage": config.spread_percentage or settings.spread_percentage,
            "order_size": config.order_size or float(os.getenv("BASE_TRADE_SIZE_SOL", str(settings.order_size))),
            "min_balance": config.min_balance or settings.min_balance,
        },
    }


@app.post("/api/transaction/send")
async def legacy_send_transaction():
    """v1 transaction send — deprecated in v2 (trades happen via the bot)."""
    raise HTTPException(
        400,
        detail="Direct transactions are managed by the market maker. Use /api/v2/start to begin automated trading.",
    )


# ══════════════════════════════════════════════════════════════════════
# Entry Point
# ══════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    import uvicorn

    host = get_bind_host()
    port = int(os.getenv("MM_PORT", str(settings.api_port)))

    logger.info(f"Starting server on {host}:{port}")
    uvicorn.run(app, host=host, port=port)
