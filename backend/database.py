"""
Persistence & Audit Layer

Schema: Orders, Positions, Transactions, AuditLog, PriceHistory, WalletSnapshots.
SQLite for dev, PostgreSQL-ready schema.
"""

import sqlite3
import json
import time
import uuid
import logging
from pathlib import Path
from contextlib import contextmanager
from typing import Optional
from dataclasses import dataclass, asdict

logger = logging.getLogger("database")

# Default database path
DB_PATH = Path("data/trading.db")


def get_db_path() -> Path:
    """Get the database path, creating directory if needed."""
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    return DB_PATH


@contextmanager
def get_connection():
    """Thread-safe database connection context manager."""
    conn = sqlite3.connect(str(get_db_path()), timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_database():
    """Create all tables. Safe to call multiple times (IF NOT EXISTS)."""
    with get_connection() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS orders (
                order_id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                token_mint TEXT NOT NULL,
                order_type TEXT NOT NULL DEFAULT 'market',
                side TEXT NOT NULL CHECK (side IN ('buy', 'sell')),
                quantity_sol REAL NOT NULL,
                expected_price REAL,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'submitted', 'partially_filled',
                                      'filled', 'cancelled', 'rejected', 'expired')),
                created_at REAL NOT NULL,
                updated_at REAL NOT NULL,
                filled_quantity REAL DEFAULT 0,
                average_fill_price REAL,
                slippage_percent REAL,
                strategy_reason TEXT,
                risk_decision TEXT,
                error_message TEXT
            );

            CREATE TABLE IF NOT EXISTS positions (
                position_id TEXT PRIMARY KEY,
                wallet_address TEXT NOT NULL,
                token_mint TEXT NOT NULL,
                quantity REAL NOT NULL DEFAULT 0,
                average_entry_price REAL,
                current_price REAL,
                unrealized_pnl REAL DEFAULT 0,
                realized_pnl REAL DEFAULT 0,
                opened_at REAL NOT NULL,
                closed_at REAL,
                UNIQUE(wallet_address, token_mint)
            );

            CREATE TABLE IF NOT EXISTS transactions (
                tx_signature TEXT PRIMARY KEY,
                order_id TEXT,
                wallet_address TEXT NOT NULL,
                transaction_type TEXT NOT NULL,
                amount_sol REAL NOT NULL,
                fee_sol REAL DEFAULT 0,
                status TEXT NOT NULL DEFAULT 'pending'
                    CHECK (status IN ('pending', 'confirmed', 'failed', 'expired')),
                block_slot INTEGER,
                timestamp REAL NOT NULL,
                raw_response TEXT,
                FOREIGN KEY (order_id) REFERENCES orders(order_id)
            );

            CREATE TABLE IF NOT EXISTS audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                timestamp REAL NOT NULL,
                event_type TEXT NOT NULL,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                resource TEXT,
                outcome TEXT NOT NULL,
                metadata TEXT,
                correlation_id TEXT
            );

            CREATE TABLE IF NOT EXISTS price_history (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                token_mint TEXT NOT NULL,
                price REAL NOT NULL,
                volume_24h REAL,
                liquidity REAL,
                timestamp REAL NOT NULL
            );

            CREATE TABLE IF NOT EXISTS wallet_snapshots (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                wallet_address TEXT NOT NULL,
                balance_sol REAL NOT NULL,
                token_balances TEXT,
                total_value_sol REAL,
                timestamp REAL NOT NULL
            );

            CREATE INDEX IF NOT EXISTS idx_orders_wallet ON orders(wallet_address);
            CREATE INDEX IF NOT EXISTS idx_orders_status ON orders(status);
            CREATE INDEX IF NOT EXISTS idx_orders_created ON orders(created_at);
            CREATE INDEX IF NOT EXISTS idx_transactions_order ON transactions(order_id);
            CREATE INDEX IF NOT EXISTS idx_audit_type ON audit_log(event_type);
            CREATE INDEX IF NOT EXISTS idx_audit_time ON audit_log(timestamp);
            CREATE INDEX IF NOT EXISTS idx_price_token_time ON price_history(token_mint, timestamp);
            CREATE INDEX IF NOT EXISTS idx_wallet_snap_time ON wallet_snapshots(wallet_address, timestamp);
        """)
        logger.info("Database initialized successfully")


# ── Order Operations ────────────────────────────────────────────────

def create_order(
    wallet_address: str,
    token_mint: str,
    side: str,
    quantity_sol: float,
    expected_price: float = None,
    order_type: str = "market",
    strategy_reason: str = "",
    risk_decision: str = "",
) -> str:
    """Create a new order record. Returns order_id."""
    order_id = str(uuid.uuid4())
    now = time.time()

    with get_connection() as conn:
        conn.execute(
            """INSERT INTO orders
               (order_id, wallet_address, token_mint, order_type, side,
                quantity_sol, expected_price, status, created_at, updated_at,
                strategy_reason, risk_decision)
               VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?, ?, ?)""",
            (order_id, wallet_address, token_mint, order_type, side,
             quantity_sol, expected_price, now, now,
             strategy_reason, risk_decision),
        )

    log_audit_event("order", "system", "create_order", f"order:{order_id}",
                    "success", {"side": side, "amount": quantity_sol, "token": token_mint})
    return order_id


def update_order_status(
    order_id: str,
    status: str,
    filled_quantity: float = None,
    average_fill_price: float = None,
    slippage_percent: float = None,
    error_message: str = None,
):
    """Update order lifecycle status."""
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """UPDATE orders SET
               status = ?, updated_at = ?,
               filled_quantity = COALESCE(?, filled_quantity),
               average_fill_price = COALESCE(?, average_fill_price),
               slippage_percent = COALESCE(?, slippage_percent),
               error_message = COALESCE(?, error_message)
               WHERE order_id = ?""",
            (status, now, filled_quantity, average_fill_price,
             slippage_percent, error_message, order_id),
        )

    log_audit_event("order", "system", "update_status", f"order:{order_id}",
                    status, {"new_status": status})


def get_recent_orders(limit: int = 50) -> list:
    """Get recent orders for the dashboard."""
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM orders ORDER BY created_at DESC LIMIT ?", (limit,)
        ).fetchall()
        return [dict(row) for row in rows]


def get_orders_by_wallet(wallet_address: str, limit: int = 50) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM orders WHERE wallet_address = ? ORDER BY created_at DESC LIMIT ?",
            (wallet_address, limit),
        ).fetchall()
        return [dict(row) for row in rows]


# ── Position Operations ─────────────────────────────────────────────

def upsert_position(
    wallet_address: str,
    token_mint: str,
    quantity_delta: float,
    price: float,
):
    """Update or create position. Handles average entry price calculation."""
    now = time.time()
    with get_connection() as conn:
        existing = conn.execute(
            "SELECT * FROM positions WHERE wallet_address = ? AND token_mint = ?",
            (wallet_address, token_mint),
        ).fetchone()

        if existing:
            old_qty = existing["quantity"]
            old_avg = existing["average_entry_price"] or 0

            new_qty = old_qty + quantity_delta

            if quantity_delta > 0 and old_qty >= 0:
                total_cost = (old_qty * old_avg) + (quantity_delta * price)
                new_avg = total_cost / new_qty if new_qty > 0 else 0
            elif quantity_delta < 0:
                realized = abs(quantity_delta) * (price - old_avg)
                conn.execute(
                    "UPDATE positions SET realized_pnl = realized_pnl + ? WHERE position_id = ?",
                    (realized, existing["position_id"]),
                )
                new_avg = old_avg
            else:
                new_avg = old_avg

            if new_qty <= 0:
                conn.execute(
                    "UPDATE positions SET quantity = 0, closed_at = ?, current_price = ? WHERE position_id = ?",
                    (now, price, existing["position_id"]),
                )
            else:
                conn.execute(
                    """UPDATE positions SET
                       quantity = ?, average_entry_price = ?, current_price = ?
                       WHERE position_id = ?""",
                    (new_qty, new_avg, price, existing["position_id"]),
                )
        else:
            position_id = str(uuid.uuid4())
            conn.execute(
                """INSERT INTO positions
                   (position_id, wallet_address, token_mint, quantity,
                    average_entry_price, current_price, opened_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?)""",
                (position_id, wallet_address, token_mint,
                 max(0, quantity_delta), price, price, now),
            )


def get_open_positions() -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM positions WHERE quantity > 0 ORDER BY opened_at DESC"
        ).fetchall()
        return [dict(row) for row in rows]


def get_positions_by_wallet(wallet_address: str) -> list:
    with get_connection() as conn:
        rows = conn.execute(
            "SELECT * FROM positions WHERE wallet_address = ? AND quantity > 0",
            (wallet_address,),
        ).fetchall()
        return [dict(row) for row in rows]


# ── Transaction Operations ──────────────────────────────────────────

def record_transaction(
    tx_signature: str,
    wallet_address: str,
    transaction_type: str,
    amount_sol: float,
    order_id: str = None,
    fee_sol: float = 0,
    status: str = "pending",
    block_slot: int = None,
    raw_response: str = None,
):
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO transactions
               (tx_signature, order_id, wallet_address, transaction_type,
                amount_sol, fee_sol, status, block_slot, timestamp, raw_response)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (tx_signature, order_id, wallet_address, transaction_type,
             amount_sol, fee_sol, status, block_slot, now, raw_response),
        )


def update_transaction_status(tx_signature: str, status: str, block_slot: int = None):
    with get_connection() as conn:
        conn.execute(
            "UPDATE transactions SET status = ?, block_slot = COALESCE(?, block_slot) WHERE tx_signature = ?",
            (status, block_slot, tx_signature),
        )


# ── Audit Log ───────────────────────────────────────────────────────

def log_audit_event(
    event_type: str,
    actor: str,
    action: str,
    resource: str,
    outcome: str,
    metadata: dict = None,
    correlation_id: str = None,
):
    """Immutable audit trail. Log everything."""
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO audit_log
               (timestamp, event_type, actor, action, resource, outcome, metadata, correlation_id)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (now, event_type, actor, action, resource, outcome,
             json.dumps(metadata) if metadata else None, correlation_id),
        )


def get_audit_log(event_type: str = None, limit: int = 100) -> list:
    with get_connection() as conn:
        if event_type:
            rows = conn.execute(
                "SELECT * FROM audit_log WHERE event_type = ? ORDER BY timestamp DESC LIMIT ?",
                (event_type, limit),
            ).fetchall()
        else:
            rows = conn.execute(
                "SELECT * FROM audit_log ORDER BY timestamp DESC LIMIT ?", (limit,)
            ).fetchall()
        return [dict(row) for row in rows]


# ── Price History ───────────────────────────────────────────────────

def record_price(token_mint: str, price: float, volume_24h: float = None, liquidity: float = None):
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO price_history (token_mint, price, volume_24h, liquidity, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (token_mint, price, volume_24h, liquidity, now),
        )


def get_price_history(token_mint: str, hours: int = 24) -> list:
    cutoff = time.time() - (hours * 3600)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT * FROM price_history
               WHERE token_mint = ? AND timestamp >= ?
               ORDER BY timestamp ASC""",
            (token_mint, cutoff),
        ).fetchall()
        return [dict(row) for row in rows]


# ── Wallet Snapshots ────────────────────────────────────────────────

def record_wallet_snapshot(wallet_address: str, balance_sol: float,
                           token_balances: dict = None, total_value_sol: float = None):
    now = time.time()
    with get_connection() as conn:
        conn.execute(
            """INSERT INTO wallet_snapshots
               (wallet_address, balance_sol, token_balances, total_value_sol, timestamp)
               VALUES (?, ?, ?, ?, ?)""",
            (wallet_address, balance_sol,
             json.dumps(token_balances) if token_balances else None,
             total_value_sol, now),
        )


# ── Analytics Queries ───────────────────────────────────────────────

def get_daily_pnl(days: int = 7) -> list:
    """Get daily PnL summary."""
    cutoff = time.time() - (days * 86400)
    with get_connection() as conn:
        rows = conn.execute(
            """SELECT
                 date(created_at, 'unixepoch') as date,
                 SUM(CASE WHEN side = 'buy' THEN quantity_sol ELSE 0 END) as total_buys,
                 SUM(CASE WHEN side = 'sell' THEN quantity_sol ELSE 0 END) as total_sells,
                 COUNT(*) as trade_count
               FROM orders
               WHERE status = 'filled' AND created_at >= ?
               GROUP BY date(created_at, 'unixepoch')
               ORDER BY date DESC""",
            (cutoff,),
        ).fetchall()
        return [dict(row) for row in rows]


def get_trade_stats() -> dict:
    """Overall trading statistics."""
    with get_connection() as conn:
        row = conn.execute(
            """SELECT
                 COUNT(*) as total_orders,
                 SUM(CASE WHEN status = 'filled' THEN 1 ELSE 0 END) as filled_orders,
                 SUM(CASE WHEN status = 'rejected' THEN 1 ELSE 0 END) as rejected_orders,
                 SUM(CASE WHEN status IN ('rejected','expired') THEN 1 ELSE 0 END) as failed_orders,
                 SUM(CASE WHEN status = 'filled' THEN quantity_sol ELSE 0 END) as total_volume,
                 AVG(CASE WHEN status = 'filled' THEN slippage_percent END) as avg_slippage
               FROM orders"""
        ).fetchone()
        return dict(row) if row else {}
