"""
Bonding Curve Phase Configuration

Defines three market-making phases based on pump.fun bonding curve progress:
1. Stealth Accumulation (0-30%) — aggressive buying, 40% of capital
2. Stabilization & Momentum (30-80%) — balanced trading, 30% of capital
3. Graduation Push (80-100%) — final push, 30% of capital

These phases are SEPARATE from Wyckoff phases:
- Bonding phases control HOW MUCH capital to allocate and trade sizes
- Wyckoff signals control WHEN to buy/sell within each bonding phase
"""

from enum import Enum
from dataclasses import dataclass, asdict


class BondingCurvePhase(Enum):
    STEALTH_ACCUMULATION = "stealth_accumulation"
    STABILIZATION = "stabilization"
    GRADUATION_PUSH = "graduation_push"


@dataclass
class PhaseConfig:
    """Percentage-based configuration for a bonding curve phase."""

    phase_name: str

    # Capital allocation (% of total budget)
    phase_capital_allocation_pct: float

    # Trade sizing (% of phase allocation)
    base_trade_size_pct: float
    strong_signal_multiplier: float
    min_trade_size_pct: float
    max_trade_size_pct: float

    # Risk limits (% of total budget)
    max_position_per_wallet_pct: float
    max_phase_exposure_pct: float  # cumulative across phases

    # Slippage and stops
    max_slippage_pct: float
    stop_loss_enabled: bool
    stop_loss_pct: float
    max_drawdown_pct: float

    # Execution
    cycle_interval_s: float
    max_trades_per_minute: int

    # Strategy overrides
    force_buy_mode: bool  # Phase 1: always buy, block sell signals
    enable_dip_buying: bool
    dip_buy_threshold_pct: float
    dip_buy_size_multiplier: float

    def to_dict(self) -> dict:
        return asdict(self)


DEFAULT_PHASE_CONFIGS: dict[BondingCurvePhase, PhaseConfig] = {
    BondingCurvePhase.STEALTH_ACCUMULATION: PhaseConfig(
        phase_name="Stealth Accumulation",
        phase_capital_allocation_pct=40.0,
        base_trade_size_pct=2.5,
        strong_signal_multiplier=3.0,
        min_trade_size_pct=1.0,
        max_trade_size_pct=8.0,
        max_position_per_wallet_pct=15.0,
        max_phase_exposure_pct=40.0,
        max_slippage_pct=10.0,
        stop_loss_enabled=False,
        stop_loss_pct=0.0,
        max_drawdown_pct=50.0,
        cycle_interval_s=10.0,
        max_trades_per_minute=20,
        force_buy_mode=True,
        enable_dip_buying=False,
        dip_buy_threshold_pct=0.0,
        dip_buy_size_multiplier=1.0,
    ),
    BondingCurvePhase.STABILIZATION: PhaseConfig(
        phase_name="Stabilization & Momentum",
        phase_capital_allocation_pct=30.0,
        base_trade_size_pct=2.0,
        strong_signal_multiplier=2.0,
        min_trade_size_pct=0.5,
        max_trade_size_pct=5.0,
        max_position_per_wallet_pct=12.0,
        max_phase_exposure_pct=70.0,
        max_slippage_pct=5.0,
        stop_loss_enabled=True,
        stop_loss_pct=20.0,
        max_drawdown_pct=25.0,
        cycle_interval_s=15.0,
        max_trades_per_minute=15,
        force_buy_mode=False,
        enable_dip_buying=True,
        dip_buy_threshold_pct=5.0,
        dip_buy_size_multiplier=2.0,
    ),
    BondingCurvePhase.GRADUATION_PUSH: PhaseConfig(
        phase_name="Graduation Push & Distribution",
        phase_capital_allocation_pct=30.0,
        base_trade_size_pct=5.0,
        strong_signal_multiplier=4.0,
        min_trade_size_pct=2.0,
        max_trade_size_pct=15.0,
        max_position_per_wallet_pct=20.0,
        max_phase_exposure_pct=100.0,
        max_slippage_pct=15.0,
        stop_loss_enabled=True,
        stop_loss_pct=15.0,
        max_drawdown_pct=20.0,
        cycle_interval_s=10.0,
        max_trades_per_minute=25,
        force_buy_mode=False,
        enable_dip_buying=True,
        dip_buy_threshold_pct=3.0,
        dip_buy_size_multiplier=3.0,
    ),
}


def get_phase_config(phase: BondingCurvePhase) -> PhaseConfig:
    """Get the configuration for a bonding curve phase."""
    return DEFAULT_PHASE_CONFIGS[phase]
