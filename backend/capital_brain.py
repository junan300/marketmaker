"""
Capital Brain — Central Capital Management Module

The Capital Brain is the single source of truth for all capital-related decisions:
- Tracks total operational budget in USD
- Fetches real-time SOL/USD price from Jupiter (cached)
- Calculates available vs deployed capital from wallet balances
- Converts percentage allocations to actual SOL amounts
- Provides affordability checks before trade execution
"""

import time
import logging
from typing import Optional

logger = logging.getLogger("capital_brain")

# SOL mint address for price lookups
SOL_MINT = "So11111111111111111111111111111111111111112"


class CapitalBrain:
    """Central capital management — the brain of the percentage-based system."""

    def __init__(self, total_budget_usd: float, jupiter, cache_ttl_s: int = 60):
        """
        Args:
            total_budget_usd: Total operational budget in USD (e.g., 1000.0)
            jupiter: JupiterAdapter instance for SOL/USD price fetching
            cache_ttl_s: How long to cache SOL price (seconds)
        """
        if total_budget_usd <= 0:
            raise ValueError("Total budget must be positive")

        self.total_budget_usd = total_budget_usd
        self._jupiter = jupiter
        self._cache_ttl_s = cache_ttl_s

        # SOL/USD price cache
        self._sol_price_usd: float = 0.0
        self._price_fetched_at: float = 0.0

        # Capital tracking
        self._deployed_capital_usd: float = 0.0

    # ── Properties ───────────────────────────────────────────────────

    @property
    def sol_price_usd(self) -> float:
        """Current cached SOL/USD price."""
        return self._sol_price_usd

    @property
    def deployed_capital_usd(self) -> float:
        """Total capital currently deployed across all wallets."""
        return self._deployed_capital_usd

    @property
    def available_capital_usd(self) -> float:
        """Undeployed capital available for new trades."""
        return max(0.0, self.total_budget_usd - self._deployed_capital_usd)

    @property
    def capital_utilization_pct(self) -> float:
        """Percentage of total budget currently deployed."""
        if self.total_budget_usd <= 0:
            return 0.0
        return (self._deployed_capital_usd / self.total_budget_usd) * 100

    # ── Core Methods ─────────────────────────────────────────────────

    async def refresh(self, wallet_orchestrator) -> None:
        """
        Refresh SOL/USD price and wallet balances.
        Must be called at the start of every trading cycle.
        """
        await self._refresh_sol_price()
        await self._refresh_deployed_capital(wallet_orchestrator)

    async def _refresh_sol_price(self) -> None:
        """Fetch SOL/USD price from Jupiter with caching."""
        now = time.time()
        if (now - self._price_fetched_at) < self._cache_ttl_s and self._sol_price_usd > 0:
            return  # Cache still valid

        try:
            price = await self._jupiter.get_price(SOL_MINT)
            if price and price > 0:
                self._sol_price_usd = float(price)
                self._price_fetched_at = now
                logger.debug(f"SOL/USD price updated: ${self._sol_price_usd:.2f}")
            else:
                logger.warning("Jupiter returned no SOL price, keeping cached value")
        except Exception as e:
            logger.warning(f"Failed to fetch SOL price: {e}")
            # Keep using the last known price

    async def _refresh_deployed_capital(self, wallet_orchestrator) -> None:
        """Calculate deployed capital from wallet balances."""
        if self._sol_price_usd <= 0:
            logger.warning("Cannot calculate deployed capital without SOL price")
            return

        pool = wallet_orchestrator.get_pool_status()
        total_sol = pool.get("total_balance_sol", 0.0)
        self._deployed_capital_usd = total_sol * self._sol_price_usd

    def pct_to_sol(self, percentage: float, base_usd: float) -> float:
        """
        Convert a percentage of a USD base amount to SOL.

        Example: pct_to_sol(2.5, 400) with SOL at $192
                 = (2.5/100) * 400 / 192 = 0.052 SOL

        Args:
            percentage: The percentage (e.g., 2.5 for 2.5%)
            base_usd: The USD base amount to take the percentage of

        Returns:
            Amount in SOL
        """
        if self._sol_price_usd <= 0:
            logger.error("SOL price is zero, cannot convert to SOL")
            return 0.0

        usd_amount = (percentage / 100) * base_usd
        return usd_amount / self._sol_price_usd

    def usd_to_sol(self, amount_usd: float) -> float:
        """Convert a USD amount to SOL."""
        if self._sol_price_usd <= 0:
            return 0.0
        return amount_usd / self._sol_price_usd

    def sol_to_usd(self, amount_sol: float) -> float:
        """Convert a SOL amount to USD."""
        return amount_sol * self._sol_price_usd

    def can_afford(self, amount_sol: float) -> bool:
        """Check if we have enough available capital for a trade."""
        if self._sol_price_usd <= 0:
            return False
        trade_cost_usd = amount_sol * self._sol_price_usd
        return trade_cost_usd <= self.available_capital_usd

    def get_total_budget_sol(self) -> float:
        """Get total budget expressed in SOL at current price."""
        if self._sol_price_usd <= 0:
            return 0.0
        return self.total_budget_usd / self._sol_price_usd

    def get_phase_allocation_usd(self, phase_capital_allocation_pct: float) -> float:
        """Get USD amount allocated to a phase."""
        return (phase_capital_allocation_pct / 100) * self.total_budget_usd

    # ── Status ───────────────────────────────────────────────────────

    def get_status(self) -> dict:
        """Get capital status for API/frontend."""
        return {
            "total_budget_usd": self.total_budget_usd,
            "total_budget_sol": self.get_total_budget_sol(),
            "deployed_capital_usd": self._deployed_capital_usd,
            "deployed_capital_sol": self.usd_to_sol(self._deployed_capital_usd),
            "available_capital_usd": self.available_capital_usd,
            "available_capital_sol": self.usd_to_sol(self.available_capital_usd),
            "capital_utilization_pct": round(self.capital_utilization_pct, 1),
            "sol_price_usd": self._sol_price_usd,
            "price_last_updated": self._price_fetched_at,
        }
