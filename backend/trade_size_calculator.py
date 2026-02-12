"""
Trade Size Calculator — Dynamic Percentage-Based Trade Sizing

Converts phase configuration percentages into actual SOL trade amounts:

1. Get total budget in SOL from Capital Brain
2. Calculate phase allocation (e.g., 40% of total = $400)
3. Calculate base trade size (e.g., 2.5% of phase = $10)
4. Apply signal multiplier (e.g., 3x for STRONG_BUY = $30)
5. Clamp to [min, max] trade size for the phase
6. Check affordability via Capital Brain
7. Return final SOL amount
"""

import logging
from backend.capital_brain import CapitalBrain
from backend.phase_config import PhaseConfig
from backend.strategy.wyckoff import TradeSignal

logger = logging.getLogger("trade_size_calculator")


class TradeSizeCalculator:
    """Converts percentage-based phase configs into SOL trade amounts."""

    def __init__(self, capital_brain: CapitalBrain):
        self.capital_brain = capital_brain

    async def calculate(
        self,
        signal: TradeSignal,
        phase_config: PhaseConfig,
    ) -> float:
        """
        Calculate trade size in SOL based on signal and phase config.

        Returns:
            Trade size in SOL, or 0.0 if the trade cannot be executed.
        """
        if self.capital_brain.sol_price_usd <= 0:
            logger.warning("SOL price not available, cannot calculate trade size")
            return 0.0

        # 1. Calculate phase allocation in USD
        phase_allocation_usd = self.capital_brain.get_phase_allocation_usd(
            phase_config.phase_capital_allocation_pct
        )

        # 2. Calculate base trade size in USD
        base_trade_usd = (phase_config.base_trade_size_pct / 100) * phase_allocation_usd

        # 3. Apply signal multiplier for strong signals
        if signal in (TradeSignal.STRONG_BUY, TradeSignal.STRONG_SELL):
            trade_usd = base_trade_usd * phase_config.strong_signal_multiplier
        else:
            trade_usd = base_trade_usd

        # 4. Enforce min/max trade size (as % of phase allocation)
        min_trade_usd = (phase_config.min_trade_size_pct / 100) * phase_allocation_usd
        max_trade_usd = (phase_config.max_trade_size_pct / 100) * phase_allocation_usd

        trade_usd = max(trade_usd, min_trade_usd)
        trade_usd = min(trade_usd, max_trade_usd)

        # 5. Convert to SOL
        trade_sol = self.capital_brain.usd_to_sol(trade_usd)

        # 6. Check affordability
        if not self.capital_brain.can_afford(trade_sol):
            logger.warning(
                f"Cannot afford trade: {trade_sol:.4f} SOL (${trade_usd:.2f}). "
                f"Available: ${self.capital_brain.available_capital_usd:.2f}"
            )
            return 0.0

        logger.debug(
            f"Trade size calculated: {trade_sol:.4f} SOL (${trade_usd:.2f}) "
            f"[{signal.value}, phase={phase_config.phase_name}]"
        )

        return trade_sol

    def get_effective_sizes(self, phase_config: PhaseConfig) -> dict:
        """
        Get the effective trade sizes in USD and SOL for display.
        Useful for showing the user what the current config translates to.
        """
        phase_alloc_usd = self.capital_brain.get_phase_allocation_usd(
            phase_config.phase_capital_allocation_pct
        )

        base_usd = (phase_config.base_trade_size_pct / 100) * phase_alloc_usd
        strong_usd = base_usd * phase_config.strong_signal_multiplier
        min_usd = (phase_config.min_trade_size_pct / 100) * phase_alloc_usd
        max_usd = (phase_config.max_trade_size_pct / 100) * phase_alloc_usd

        return {
            "phase_allocation_usd": round(phase_alloc_usd, 2),
            "phase_allocation_sol": round(self.capital_brain.usd_to_sol(phase_alloc_usd), 4),
            "base_trade_usd": round(base_usd, 2),
            "base_trade_sol": round(self.capital_brain.usd_to_sol(base_usd), 4),
            "strong_signal_trade_usd": round(strong_usd, 2),
            "strong_signal_trade_sol": round(self.capital_brain.usd_to_sol(strong_usd), 4),
            "min_trade_usd": round(min_usd, 2),
            "min_trade_sol": round(self.capital_brain.usd_to_sol(min_usd), 4),
            "max_trade_usd": round(max_usd, 2),
            "max_trade_sol": round(self.capital_brain.usd_to_sol(max_usd), 4),
        }
