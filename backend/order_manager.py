"""
Execution & Order Management Layer

Order lifecycle: PENDING → SUBMITTED → FILLED/REJECTED/EXPIRED
Handles retry logic with exponential backoff for Solana-specific errors.
"""

import time
import asyncio
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional, Callable, Any

logger = logging.getLogger("order_manager")


class OrderState(Enum):
    PENDING = "pending"
    SUBMITTED = "submitted"
    PARTIALLY_FILLED = "partially_filled"
    FILLED = "filled"
    CANCELLED = "cancelled"
    REJECTED = "rejected"
    EXPIRED = "expired"


class OrderSide(Enum):
    BUY = "buy"
    SELL = "sell"


@dataclass
class Order:
    order_id: str
    wallet_address: str
    token_mint: str
    side: OrderSide
    amount_sol: float
    expected_price: float = 0.0
    max_slippage_percent: float = 2.0
    state: OrderState = OrderState.PENDING
    created_at: float = field(default_factory=time.time)
    submitted_at: float = 0.0
    filled_at: float = 0.0
    filled_amount: float = 0.0
    average_fill_price: float = 0.0
    actual_slippage: float = 0.0
    tx_signature: str = ""
    error_message: str = ""
    retry_count: int = 0
    strategy_reason: str = ""


@dataclass
class RetryConfig:
    """Exponential backoff retry configuration."""
    max_attempts: int = 3
    initial_delay_s: float = 1.0
    max_delay_s: float = 15.0
    backoff_multiplier: float = 2.0

    retryable_errors: tuple = (
        "BlockhashNotFound",
        "TransactionExpiredBlockheightExceededError",
        "Node is behind",
        "Service temporarily unavailable",
        "Too many requests",
    )

    def should_retry(self, error: Exception, attempt: int) -> bool:
        if attempt >= self.max_attempts:
            return False
        error_str = str(error)
        return any(e in error_str for e in self.retryable_errors)

    def get_delay(self, attempt: int) -> float:
        delay = self.initial_delay_s * (self.backoff_multiplier ** attempt)
        return min(delay, self.max_delay_s)


class OrderManager:
    """
    Manages the lifecycle of orders from creation through execution.
    Coordinates with the DEX layer for actual swap execution.
    """

    def __init__(self, retry_config: RetryConfig = None):
        self.retry_config = retry_config or RetryConfig()
        self._active_orders: dict[str, Order] = {}
        self._completed_orders: list[Order] = []

    def create_order(self, order: Order) -> Order:
        """Register a new order. Does NOT execute it."""
        order.state = OrderState.PENDING
        order.created_at = time.time()
        self._active_orders[order.order_id] = order
        logger.info(
            f"Order created: {order.order_id[:8]} "
            f"{order.side.value} {order.amount_sol} SOL "
            f"via wallet {order.wallet_address[:8]}..."
        )
        return order

    async def execute_order(
        self,
        order: Order,
        swap_function: Callable,
    ) -> Order:
        """
        Execute an order with retry logic.

        swap_function: async callable(wallet_address, token_mint, side, amount_sol, max_slippage)
        Returns dict with: tx_signature, filled_amount, fill_price, fee
        """
        order.state = OrderState.SUBMITTED
        order.submitted_at = time.time()

        for attempt in range(self.retry_config.max_attempts):
            try:
                logger.info(
                    f"Executing order {order.order_id[:8]} "
                    f"(attempt {attempt + 1}/{self.retry_config.max_attempts})"
                )

                result = await swap_function(
                    wallet_address=order.wallet_address,
                    token_mint=order.token_mint,
                    side=order.side.value,
                    amount_sol=order.amount_sol,
                    max_slippage=order.max_slippage_percent,
                )

                # Success
                order.state = OrderState.FILLED
                order.filled_at = time.time()
                order.tx_signature = result.get("tx_signature", "")
                order.filled_amount = result.get("filled_amount", order.amount_sol)
                order.average_fill_price = result.get("fill_price", 0)
                order.retry_count = attempt

                if order.expected_price > 0 and order.average_fill_price > 0:
                    if order.side == OrderSide.BUY:
                        order.actual_slippage = (
                            (order.average_fill_price - order.expected_price)
                            / order.expected_price * 100
                        )
                    else:
                        order.actual_slippage = (
                            (order.expected_price - order.average_fill_price)
                            / order.expected_price * 100
                        )

                self._complete_order(order)
                logger.info(
                    f"Order FILLED: {order.order_id[:8]} "
                    f"tx={order.tx_signature[:16] if order.tx_signature else 'N/A'}... "
                    f"slippage={order.actual_slippage:.2f}%"
                )
                return order

            except Exception as e:
                order.retry_count = attempt + 1
                order.error_message = str(e)

                if self.retry_config.should_retry(e, attempt + 1):
                    delay = self.retry_config.get_delay(attempt)
                    logger.warning(
                        f"Order {order.order_id[:8]} failed (attempt {attempt + 1}): "
                        f"{e}. Retrying in {delay:.1f}s..."
                    )
                    await asyncio.sleep(delay)
                else:
                    order.state = OrderState.REJECTED
                    self._complete_order(order)
                    logger.error(
                        f"Order REJECTED: {order.order_id[:8]} "
                        f"after {attempt + 1} attempts: {e}"
                    )
                    return order

        order.state = OrderState.EXPIRED
        self._complete_order(order)
        return order

    def cancel_order(self, order_id: str) -> bool:
        """Cancel a pending order."""
        if order_id in self._active_orders:
            order = self._active_orders[order_id]
            if order.state == OrderState.PENDING:
                order.state = OrderState.CANCELLED
                self._complete_order(order)
                logger.info(f"Order cancelled: {order_id[:8]}")
                return True
        return False

    def _complete_order(self, order: Order):
        """Move order from active to completed."""
        if order.order_id in self._active_orders:
            del self._active_orders[order.order_id]
        self._completed_orders.append(order)
        if len(self._completed_orders) > 1000:
            self._completed_orders = self._completed_orders[-500:]

    def get_active_orders(self) -> list:
        return [
            {
                "order_id": o.order_id,
                "side": o.side.value,
                "amount_sol": o.amount_sol,
                "state": o.state.value,
                "wallet": o.wallet_address[:8] + "...",
                "created_at": o.created_at,
            }
            for o in self._active_orders.values()
        ]

    def get_completed_orders(self, limit: int = 50) -> list:
        return [
            {
                "order_id": o.order_id,
                "side": o.side.value,
                "amount_sol": o.amount_sol,
                "filled_amount": o.filled_amount,
                "fill_price": o.average_fill_price,
                "slippage": o.actual_slippage,
                "state": o.state.value,
                "tx_signature": o.tx_signature,
                "retries": o.retry_count,
                "wallet": o.wallet_address[:8] + "...",
            }
            for o in self._completed_orders[-limit:]
        ]

    def get_fill_rate(self) -> float:
        """Percentage of orders that filled successfully."""
        if not self._completed_orders:
            return 0.0
        filled = sum(1 for o in self._completed_orders if o.state == OrderState.FILLED)
        return (filled / len(self._completed_orders)) * 100


# ── Solana Transaction Helpers ──────────────────────────────────────

async def confirm_transaction(
    connection,
    tx_signature: str,
    timeout_s: float = 30.0,
    poll_interval_s: float = 1.0,
) -> bool:
    """Wait for Solana transaction confirmation."""
    start = time.time()
    while time.time() - start < timeout_s:
        try:
            result = await connection.get_signature_statuses([tx_signature])
            if result and result.value and result.value[0]:
                status = result.value[0]
                if status.err:
                    logger.error(f"Transaction failed on-chain: {status.err}")
                    return False
                if status.confirmation_status in ("confirmed", "finalized"):
                    return True
        except Exception as e:
            logger.warning(f"Error checking tx status: {e}")

        await asyncio.sleep(poll_interval_s)

    logger.warning(f"Transaction confirmation timed out: {tx_signature[:16]}...")
    return False
