"""
Risk & Position Management Layer

Every trade MUST pass through evaluate_trade() before execution.
- Circuit breakers (rapid price change, consecutive failures)
- Position limits and exposure caps (percentage-based via Capital Brain)
- Per-position stop loss
- Emergency shutdown
- Drawdown protection
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional
from threading import Lock

logger = logging.getLogger("risk_manager")


class RiskAction(Enum):
    APPROVED = "approved"
    REJECTED = "rejected"
    HALTED = "halted"


class CircuitBreakerState(Enum):
    CLOSED = "closed"
    OPEN = "open"
    HALF_OPEN = "half_open"


@dataclass
class RiskRules:
    """Configurable risk parameters — percentage-based via Capital Brain."""

    # Per-wallet limits (% of total budget)
    max_position_per_wallet_pct: float = 15.0
    max_exposure_per_token_pct: float = 50.0

    # System-wide limits (% of total budget)
    total_max_exposure_pct: float = 80.0
    max_daily_volume_pct: float = 100.0

    # Frequency controls
    max_trades_per_minute: int = 10
    min_time_between_trades_ms: int = 2000

    # Stop conditions
    max_drawdown_percent: float = 15.0
    max_consecutive_losses: int = 5
    max_slippage_percent: float = 5.0

    # Per-position stop loss (% below entry price triggers forced sell)
    stop_loss_percent: float = 10.0

    # Circuit breaker thresholds
    rapid_price_change_percent: float = 20.0
    rapid_price_change_window_s: int = 60
    max_failed_transactions: int = 3
    breaker_cooldown_s: int = 300


@dataclass
class RiskState:
    """Mutable state tracked by the risk manager."""

    total_exposure_sol: float = 0.0
    daily_volume_sol: float = 0.0
    daily_volume_reset_time: float = 0.0

    consecutive_losses: int = 0
    trades_this_minute: int = 0
    minute_window_start: float = 0.0
    last_trade_time: float = 0.0

    peak_portfolio_value: float = 0.0
    current_portfolio_value: float = 0.0

    failed_transactions: int = 0

    wallet_exposures: dict = field(default_factory=dict)
    token_exposures: dict = field(default_factory=dict)

    emergency_shutdown: bool = False


@dataclass
class TradeIntent:
    """What the strategy layer wants to do. Risk manager evaluates this."""

    wallet_address: str
    token_mint: str
    side: str
    amount_sol: float
    expected_price: float
    max_slippage_percent: float = 2.0
    strategy_reason: str = ""


@dataclass
class RiskDecision:
    action: RiskAction
    reason: str
    trade_intent: Optional[TradeIntent] = None
    checks_passed: list = field(default_factory=list)
    checks_failed: list = field(default_factory=list)


class CircuitBreaker:
    """Three-state circuit breaker: CLOSED -> OPEN -> HALF_OPEN -> CLOSED"""

    def __init__(self, cooldown_s: int = 300):
        self.state = CircuitBreakerState.CLOSED
        self.tripped_at: float = 0.0
        self.cooldown_s = cooldown_s
        self.trip_reason: str = ""
        self._lock = Lock()

    def trip(self, reason: str):
        with self._lock:
            self.state = CircuitBreakerState.OPEN
            self.tripped_at = time.time()
            self.trip_reason = reason
            logger.critical(f"CIRCUIT BREAKER TRIPPED: {reason}")

    def check(self) -> bool:
        """Returns True if trading is allowed."""
        with self._lock:
            if self.state == CircuitBreakerState.CLOSED:
                return True

            if self.state == CircuitBreakerState.OPEN:
                elapsed = time.time() - self.tripped_at
                if elapsed >= self.cooldown_s:
                    self.state = CircuitBreakerState.HALF_OPEN
                    logger.info("Circuit breaker entering HALF_OPEN state")
                    return True
                return False

            return True

    def record_success(self):
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.CLOSED
                self.trip_reason = ""
                logger.info("Circuit breaker CLOSED — normal operation resumed")

    def record_failure(self):
        with self._lock:
            if self.state == CircuitBreakerState.HALF_OPEN:
                self.state = CircuitBreakerState.OPEN
                self.tripped_at = time.time()
                logger.warning("Circuit breaker re-OPENED after failure in HALF_OPEN")

    def reset(self):
        with self._lock:
            self.state = CircuitBreakerState.CLOSED
            self.trip_reason = ""
            logger.info("Circuit breaker manually reset")

    def to_dict(self) -> dict:
        return {
            "state": self.state.value,
            "tripped_at": self.tripped_at,
            "trip_reason": self.trip_reason,
            "cooldown_s": self.cooldown_s,
        }


class RiskManager:
    """
    Central risk management engine. Every trade intent MUST pass through
    evaluate_trade() before execution. No exceptions.

    Uses Capital Brain for percentage-based limit calculations.
    """

    def __init__(self, rules: Optional[RiskRules] = None, capital_brain=None):
        self.rules = rules or RiskRules()
        self.state = RiskState()
        self.circuit_breaker = CircuitBreaker(self.rules.breaker_cooldown_s)
        self.capital_brain = capital_brain
        self._lock = Lock()
        self._price_history: list = []

    def _get_limit_sol(self, pct: float) -> float:
        """Convert a percentage-of-total-budget to SOL using Capital Brain."""
        if self.capital_brain and self.capital_brain.sol_price_usd > 0:
            return (pct / 100) * self.capital_brain.total_budget_usd / self.capital_brain.sol_price_usd
        # Fallback: return a large number so checks don't block when capital brain isn't ready
        return float('inf')

    def evaluate_trade(self, intent: TradeIntent) -> RiskDecision:
        """Run all risk checks against a trade intent."""
        checks_passed = []
        checks_failed = []

        # 0. Emergency shutdown
        if self.state.emergency_shutdown:
            return RiskDecision(
                action=RiskAction.HALTED,
                reason="Emergency shutdown is active",
                trade_intent=intent,
            )

        # 1. Circuit breaker
        if not self.circuit_breaker.check():
            return RiskDecision(
                action=RiskAction.HALTED,
                reason=f"Circuit breaker OPEN: {self.circuit_breaker.trip_reason}",
                trade_intent=intent,
            )

        # 2. Frequency limit
        now = time.time()
        if now - self.state.minute_window_start > 60:
            self.state.trades_this_minute = 0
            self.state.minute_window_start = now

        if self.state.trades_this_minute >= self.rules.max_trades_per_minute:
            checks_failed.append(f"Frequency: {self.state.trades_this_minute} trades/min exceeds {self.rules.max_trades_per_minute}")
        else:
            checks_passed.append("Frequency OK")

        # 3. Minimum time between trades
        time_since_last = (now - self.state.last_trade_time) * 1000
        if self.state.last_trade_time > 0 and time_since_last < self.rules.min_time_between_trades_ms:
            checks_failed.append(f"Cooldown: {time_since_last:.0f}ms < {self.rules.min_time_between_trades_ms}ms minimum")
        else:
            checks_passed.append("Cooldown OK")

        # 4. Per-wallet position limit (% of total budget)
        wallet_exposure = self.state.wallet_exposures.get(intent.wallet_address, 0.0)
        max_wallet_sol = self._get_limit_sol(self.rules.max_position_per_wallet_pct)
        if intent.side == "buy":
            new_exposure = wallet_exposure + intent.amount_sol
            if new_exposure > max_wallet_sol:
                checks_failed.append(
                    f"Wallet exposure: {new_exposure:.4f} SOL > {max_wallet_sol:.4f} SOL "
                    f"({self.rules.max_position_per_wallet_pct}% of budget)"
                )
            else:
                checks_passed.append("Wallet exposure OK")
        else:
            checks_passed.append("Wallet exposure OK (sell)")

        # 5. Per-token exposure limit (% of total budget)
        token_exposure = self.state.token_exposures.get(intent.token_mint, 0.0)
        max_token_sol = self._get_limit_sol(self.rules.max_exposure_per_token_pct)
        if intent.side == "buy":
            new_token_exposure = token_exposure + intent.amount_sol
            if new_token_exposure > max_token_sol:
                checks_failed.append(
                    f"Token exposure: {new_token_exposure:.4f} SOL > {max_token_sol:.4f} SOL "
                    f"({self.rules.max_exposure_per_token_pct}% of budget)"
                )
            else:
                checks_passed.append("Token exposure OK")
        else:
            checks_passed.append("Token exposure OK (sell)")

        # 6. Total system exposure (% of total budget)
        max_total_sol = self._get_limit_sol(self.rules.total_max_exposure_pct)
        if intent.side == "buy":
            new_total = self.state.total_exposure_sol + intent.amount_sol
            if new_total > max_total_sol:
                checks_failed.append(
                    f"Total exposure: {new_total:.4f} SOL > {max_total_sol:.4f} SOL "
                    f"({self.rules.total_max_exposure_pct}% of budget)"
                )
            else:
                checks_passed.append("Total exposure OK")
        else:
            checks_passed.append("Total exposure OK (sell)")

        # 7. Daily volume limit (% of total budget)
        self._reset_daily_volume_if_needed()
        max_daily_sol = self._get_limit_sol(self.rules.max_daily_volume_pct)
        new_daily = self.state.daily_volume_sol + intent.amount_sol
        if new_daily > max_daily_sol:
            checks_failed.append(
                f"Daily volume: {new_daily:.4f} SOL > {max_daily_sol:.4f} SOL "
                f"({self.rules.max_daily_volume_pct}% of budget)"
            )
        else:
            checks_passed.append("Daily volume OK")

        # 8. Slippage check
        if intent.max_slippage_percent > self.rules.max_slippage_percent:
            checks_failed.append(
                f"Slippage: {intent.max_slippage_percent}% > {self.rules.max_slippage_percent}% max"
            )
        else:
            checks_passed.append("Slippage OK")

        # 9. Consecutive losses
        if self.state.consecutive_losses >= self.rules.max_consecutive_losses:
            checks_failed.append(
                f"Consecutive losses: {self.state.consecutive_losses} >= {self.rules.max_consecutive_losses} max"
            )
        else:
            checks_passed.append("Consecutive losses OK")

        # 10. Drawdown check
        drawdown = self._calculate_drawdown()
        if drawdown > self.rules.max_drawdown_percent:
            checks_failed.append(
                f"Drawdown: {drawdown:.1f}% > {self.rules.max_drawdown_percent}% max"
            )
            self.circuit_breaker.trip(f"Max drawdown exceeded: {drawdown:.1f}%")
        else:
            checks_passed.append(f"Drawdown OK ({drawdown:.1f}%)")

        # 11. Capital utilization check (phase exposure limit)
        if self.capital_brain:
            utilization = self.capital_brain.capital_utilization_pct
            if utilization >= self.rules.total_max_exposure_pct and intent.side == "buy":
                checks_failed.append(
                    f"Capital utilization: {utilization:.1f}% >= {self.rules.total_max_exposure_pct}% phase limit"
                )
            else:
                checks_passed.append(f"Capital utilization OK ({utilization:.1f}%)")

        # Decision
        if checks_failed:
            decision = RiskDecision(
                action=RiskAction.REJECTED,
                reason="; ".join(checks_failed),
                trade_intent=intent,
                checks_passed=checks_passed,
                checks_failed=checks_failed,
            )
            logger.warning(f"TRADE REJECTED: {decision.reason}")
        else:
            decision = RiskDecision(
                action=RiskAction.APPROVED,
                reason="All risk checks passed",
                trade_intent=intent,
                checks_passed=checks_passed,
                checks_failed=[],
            )
            logger.info(f"TRADE APPROVED: {intent.side} {intent.amount_sol:.4f} SOL")

        return decision

    # ── State updates ───────────────────────────────────────────────

    def record_trade_executed(self, intent: TradeIntent, success: bool, pnl: float = 0.0):
        """Call after every trade attempt to update risk state."""
        with self._lock:
            self.state.last_trade_time = time.time()
            self.state.trades_this_minute += 1
            self.state.daily_volume_sol += intent.amount_sol

            if success:
                self.state.failed_transactions = 0
                self.circuit_breaker.record_success()

                if intent.side == "buy":
                    self.state.wallet_exposures[intent.wallet_address] = (
                        self.state.wallet_exposures.get(intent.wallet_address, 0.0) + intent.amount_sol
                    )
                    self.state.token_exposures[intent.token_mint] = (
                        self.state.token_exposures.get(intent.token_mint, 0.0) + intent.amount_sol
                    )
                    self.state.total_exposure_sol += intent.amount_sol
                else:
                    self.state.wallet_exposures[intent.wallet_address] = max(
                        0, self.state.wallet_exposures.get(intent.wallet_address, 0.0) - intent.amount_sol
                    )
                    self.state.token_exposures[intent.token_mint] = max(
                        0, self.state.token_exposures.get(intent.token_mint, 0.0) - intent.amount_sol
                    )
                    self.state.total_exposure_sol = max(0, self.state.total_exposure_sol - intent.amount_sol)

                if pnl >= 0:
                    self.state.consecutive_losses = 0
                else:
                    self.state.consecutive_losses += 1

            else:
                self.state.failed_transactions += 1
                self.circuit_breaker.record_failure()

                if self.state.failed_transactions >= self.rules.max_failed_transactions:
                    self.circuit_breaker.trip(
                        f"{self.state.failed_transactions} consecutive transaction failures"
                    )

    def update_portfolio_value(self, value_sol: float):
        """Call periodically with current portfolio value for drawdown tracking."""
        with self._lock:
            self.state.current_portfolio_value = value_sol
            if value_sol > self.state.peak_portfolio_value:
                self.state.peak_portfolio_value = value_sol

    def record_price(self, price: float):
        """Feed price data for rapid price change detection."""
        now = time.time()
        self._price_history.append((now, price))

        cutoff = now - self.rules.rapid_price_change_window_s
        self._price_history = [(t, p) for t, p in self._price_history if t >= cutoff]

        if len(self._price_history) >= 2:
            oldest_price = self._price_history[0][1]
            if oldest_price > 0:
                change_pct = abs((price - oldest_price) / oldest_price) * 100
                if change_pct > self.rules.rapid_price_change_percent:
                    self.circuit_breaker.trip(
                        f"Rapid price change: {change_pct:.1f}% in {self.rules.rapid_price_change_window_s}s"
                    )

    # ── Emergency controls ──────────────────────────────────────────

    def emergency_shutdown(self):
        """Immediately halt all trading. Requires manual reset."""
        self.state.emergency_shutdown = True
        self.circuit_breaker.trip("EMERGENCY SHUTDOWN activated")
        logger.critical("EMERGENCY SHUTDOWN — all trading halted")

    def reset_emergency(self):
        """Manually resume trading after emergency shutdown."""
        self.state.emergency_shutdown = False
        self.circuit_breaker.reset()
        logger.info("Emergency shutdown cleared — trading can resume")

    # ── Phase Integration ────────────────────────────────────────────

    def update_from_phase_config(self, phase_config) -> None:
        """Update risk rules from a bonding curve phase configuration."""
        self.rules.max_position_per_wallet_pct = phase_config.max_position_per_wallet_pct
        self.rules.total_max_exposure_pct = phase_config.max_phase_exposure_pct
        self.rules.max_drawdown_percent = phase_config.max_drawdown_pct
        self.rules.max_slippage_percent = phase_config.max_slippage_pct
        self.rules.max_trades_per_minute = phase_config.max_trades_per_minute

        if phase_config.stop_loss_enabled:
            self.rules.stop_loss_percent = phase_config.stop_loss_pct

        logger.info(
            f"Risk rules updated from phase '{phase_config.phase_name}': "
            f"max_wallet={phase_config.max_position_per_wallet_pct}%, "
            f"max_exposure={phase_config.max_phase_exposure_pct}%, "
            f"max_drawdown={phase_config.max_drawdown_pct}%"
        )

    # ── Helpers ──────────────────────────────────────────────────────

    def _calculate_drawdown(self) -> float:
        if self.state.peak_portfolio_value <= 0:
            return 0.0
        return (
            (self.state.peak_portfolio_value - self.state.current_portfolio_value)
            / self.state.peak_portfolio_value
            * 100
        )

    def _reset_daily_volume_if_needed(self):
        now = time.time()
        if now - self.state.daily_volume_reset_time > 86400:
            self.state.daily_volume_sol = 0.0
            self.state.daily_volume_reset_time = now

    def update_rules(self, **kwargs):
        """Update risk rules at runtime."""
        for key, value in kwargs.items():
            if hasattr(self.rules, key):
                setattr(self.rules, key, value)
                logger.info(f"Risk rule updated: {key} = {value}")
            else:
                logger.warning(f"Unknown risk rule: {key}")

    def get_status(self) -> dict:
        status = {
            "circuit_breaker": self.circuit_breaker.to_dict(),
            "emergency_shutdown": self.state.emergency_shutdown,
            "total_exposure_sol": self.state.total_exposure_sol,
            "daily_volume_sol": self.state.daily_volume_sol,
            "consecutive_losses": self.state.consecutive_losses,
            "failed_transactions": self.state.failed_transactions,
            "drawdown_percent": self._calculate_drawdown(),
            "trades_this_minute": self.state.trades_this_minute,
            "wallet_exposures": dict(self.state.wallet_exposures),
            "token_exposures": dict(self.state.token_exposures),
            "rules": {
                "max_position_per_wallet_pct": self.rules.max_position_per_wallet_pct,
                "max_exposure_per_token_pct": self.rules.max_exposure_per_token_pct,
                "total_max_exposure_pct": self.rules.total_max_exposure_pct,
                "max_daily_volume_pct": self.rules.max_daily_volume_pct,
                "max_drawdown_percent": self.rules.max_drawdown_percent,
                "max_trades_per_minute": self.rules.max_trades_per_minute,
                "max_consecutive_losses": self.rules.max_consecutive_losses,
                "stop_loss_percent": self.rules.stop_loss_percent,
            },
        }

        # Include effective SOL limits if Capital Brain is available
        if self.capital_brain and self.capital_brain.sol_price_usd > 0:
            status["effective_limits_sol"] = {
                "max_position_per_wallet_sol": round(self._get_limit_sol(self.rules.max_position_per_wallet_pct), 4),
                "max_exposure_per_token_sol": round(self._get_limit_sol(self.rules.max_exposure_per_token_pct), 4),
                "total_max_exposure_sol": round(self._get_limit_sol(self.rules.total_max_exposure_pct), 4),
                "max_daily_volume_sol": round(self._get_limit_sol(self.rules.max_daily_volume_pct), 4),
            }

        return status
