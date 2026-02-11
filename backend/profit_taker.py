"""
Profit-Taking & Market Stabilization Module

Strategies:
- TWAP: Spread sales evenly over time
- Volume-Weighted: Sell more into high liquidity
- Percentage-Based: Auto-sell at predefined price targets
- Wyckoff-Informed: Phase-aware distribution
"""

import time
import logging
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("profit_taker")


class DistributionStrategy(Enum):
    TWAP = "twap"
    VWAP = "vwap"
    PERCENTAGE = "percentage"
    WYCKOFF = "wyckoff"


@dataclass
class PriceTarget:
    """A price level at which to sell a percentage of holdings."""
    target_price: float
    sell_percent: float
    triggered: bool = False
    triggered_at: float = 0.0


@dataclass
class DistributionSchedule:
    """A planned distribution over time."""
    total_amount: float
    remaining_amount: float
    strategy: DistributionStrategy
    start_time: float
    end_time: float
    interval_seconds: float
    amount_per_step: float
    steps_completed: int = 0
    steps_total: int = 0
    last_step_time: float = 0.0
    paused: bool = False

    def to_dict(self) -> dict:
        return {
            "strategy": self.strategy.value,
            "total_amount": self.total_amount,
            "remaining_amount": self.remaining_amount,
            "progress_pct": ((self.total_amount - self.remaining_amount) / self.total_amount * 100)
                if self.total_amount > 0 else 0,
            "steps_completed": self.steps_completed,
            "steps_total": self.steps_total,
            "paused": self.paused,
            "estimated_completion": self.end_time,
        }


@dataclass
class DistributionStep:
    """A single sell action within a distribution plan."""
    amount: float
    reason: str
    timestamp: float = field(default_factory=time.time)
    wallet_hint: str = ""


@dataclass
class MarketImpactEstimate:
    """Estimated price impact of a sell order."""
    sell_amount: float
    current_liquidity: float
    estimated_price_change_pct: float
    estimated_slippage_pct: float
    confidence: float
    recommendation: str


class ProfitTaker:
    """
    Manages controlled profit-taking across multiple strategies.
    Coordinates with the Wyckoff detector to time distribution.
    """

    def __init__(self):
        self._active_schedule: Optional[DistributionSchedule] = None
        self._price_targets: list[PriceTarget] = []
        self._total_distributed: float = 0.0
        self._total_profit_sol: float = 0.0
        self._distribution_history: list[dict] = []

    def create_twap_schedule(
        self,
        total_amount: float,
        duration_hours: float,
        num_steps: int = None,
    ) -> DistributionSchedule:
        """TWAP: Distribute sales evenly over a defined period."""
        now = time.time()
        end_time = now + (duration_hours * 3600)

        if num_steps is None:
            num_steps = max(1, int(duration_hours * 4))

        interval = (duration_hours * 3600) / num_steps
        per_step = total_amount / num_steps

        schedule = DistributionSchedule(
            total_amount=total_amount,
            remaining_amount=total_amount,
            strategy=DistributionStrategy.TWAP,
            start_time=now,
            end_time=end_time,
            interval_seconds=interval,
            amount_per_step=per_step,
            steps_total=num_steps,
        )

        self._active_schedule = schedule
        logger.info(
            f"TWAP schedule created: {total_amount} tokens over {duration_hours}h "
            f"({num_steps} steps, {per_step:.2f}/step, every {interval:.0f}s)"
        )
        return schedule

    def set_price_targets(self, targets: list[dict]):
        """Percentage-Based: Sell at predefined price levels."""
        self._price_targets = [
            PriceTarget(
                target_price=t["price"],
                sell_percent=t["sell_percent"],
            )
            for t in targets
        ]
        logger.info(f"Set {len(self._price_targets)} price targets for distribution")

    def get_next_step(
        self,
        current_price: float = 0,
        current_volume: float = 0,
        average_volume: float = 0,
        wyckoff_phase: str = "unknown",
    ) -> Optional[DistributionStep]:
        """
        Determine if it's time for the next distribution step.
        Called periodically by the market maker loop.
        """
        target_step = self._check_price_targets(current_price)
        if target_step:
            return target_step

        if not self._active_schedule or self._active_schedule.paused:
            return None

        schedule = self._active_schedule
        now = time.time()

        if now - schedule.last_step_time < schedule.interval_seconds:
            return None

        if schedule.remaining_amount <= 0:
            logger.info("Distribution schedule complete")
            self._active_schedule = None
            return None

        step_amount = self._calculate_step_amount(
            schedule=schedule,
            current_volume=current_volume,
            average_volume=average_volume,
            wyckoff_phase=wyckoff_phase,
        )

        if step_amount <= 0:
            return None

        step_amount = min(step_amount, schedule.remaining_amount)

        schedule.remaining_amount -= step_amount
        schedule.steps_completed += 1
        schedule.last_step_time = now

        step = DistributionStep(
            amount=step_amount,
            reason=f"{schedule.strategy.value} step {schedule.steps_completed}/{schedule.steps_total}",
        )

        self._distribution_history.append({
            "amount": step_amount,
            "strategy": schedule.strategy.value,
            "price": current_price,
            "timestamp": now,
        })

        return step

    def _calculate_step_amount(
        self,
        schedule: DistributionSchedule,
        current_volume: float,
        average_volume: float,
        wyckoff_phase: str,
    ) -> float:
        """Adjust step size based on strategy type and market conditions."""
        base_amount = schedule.amount_per_step

        if schedule.strategy == DistributionStrategy.TWAP:
            return base_amount

        elif schedule.strategy == DistributionStrategy.VWAP:
            if average_volume <= 0:
                return base_amount
            volume_ratio = current_volume / average_volume
            multiplier = max(0.3, min(3.0, volume_ratio))
            return base_amount * multiplier

        elif schedule.strategy == DistributionStrategy.WYCKOFF:
            phase_multipliers = {
                "distribution": 1.5,
                "markup": 0.0,
                "accumulation": 0.0,
                "markdown": 0.3,
                "unknown": 0.5,
            }
            multiplier = phase_multipliers.get(wyckoff_phase, 0.5)

            if multiplier == 0:
                logger.info(f"Distribution paused — Wyckoff phase: {wyckoff_phase}")
                return 0

            return base_amount * multiplier

        return base_amount

    def _check_price_targets(self, current_price: float) -> Optional[DistributionStep]:
        """Check if any price targets have been hit."""
        if current_price <= 0:
            return None

        for target in self._price_targets:
            if target.triggered:
                continue
            if current_price >= target.target_price:
                target.triggered = True
                target.triggered_at = time.time()

                logger.info(
                    f"Price target hit: {target.target_price} "
                    f"(current: {current_price}) — selling {target.sell_percent}%"
                )

                return DistributionStep(
                    amount=0,  # Caller calculates actual amount from sell_percent
                    reason=f"Price target {target.target_price} hit — sell {target.sell_percent}% of holdings",
                )

        return None

    @staticmethod
    def estimate_market_impact(
        sell_amount_sol: float,
        pool_liquidity_sol: float,
    ) -> MarketImpactEstimate:
        """Estimate price impact using constant product AMM formula."""
        if pool_liquidity_sol <= 0:
            return MarketImpactEstimate(
                sell_amount=sell_amount_sol,
                current_liquidity=0,
                estimated_price_change_pct=100.0,
                estimated_slippage_pct=100.0,
                confidence=0.0,
                recommendation="wait",
            )

        impact_pct = (sell_amount_sol / pool_liquidity_sol) * 100

        if impact_pct < 1.0:
            recommendation = "proceed"
        elif impact_pct < 3.0:
            recommendation = "proceed"
        elif impact_pct < 5.0:
            recommendation = "reduce_size"
        else:
            recommendation = "wait"

        return MarketImpactEstimate(
            sell_amount=sell_amount_sol,
            current_liquidity=pool_liquidity_sol,
            estimated_price_change_pct=impact_pct,
            estimated_slippage_pct=impact_pct * 0.7,
            confidence=0.6,
            recommendation=recommendation,
        )

    def pause_distribution(self):
        if self._active_schedule:
            self._active_schedule.paused = True
            logger.info("Distribution paused")

    def resume_distribution(self):
        if self._active_schedule:
            self._active_schedule.paused = False
            logger.info("Distribution resumed")

    def cancel_distribution(self):
        if self._active_schedule:
            logger.info(
                f"Distribution cancelled. "
                f"Distributed: {self._active_schedule.total_amount - self._active_schedule.remaining_amount:.2f} "
                f"of {self._active_schedule.total_amount:.2f}"
            )
            self._active_schedule = None

    def get_status(self) -> dict:
        return {
            "active_schedule": self._active_schedule.to_dict() if self._active_schedule else None,
            "price_targets": [
                {
                    "price": t.target_price,
                    "sell_percent": t.sell_percent,
                    "triggered": t.triggered,
                    "triggered_at": t.triggered_at,
                }
                for t in self._price_targets
            ],
            "total_distributed": self._total_distributed,
            "total_profit_sol": self._total_profit_sol,
            "recent_distributions": self._distribution_history[-20:],
        }
