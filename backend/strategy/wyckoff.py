"""
Strategy & Signal Generation Layer — Wyckoff Cycle Detector

Detects Accumulation, Markup, Distribution, Markdown phases
and generates trade signals (BUY/SELL/HOLD).

Wyckoff applied to compressed memecoin timeframes:
- Accumulation: consolidation after downtrend → BUY
- Markup: breakout, upward momentum → HOLD
- Distribution: consolidation after uptrend → SELL
- Markdown: breakdown, panic selling → STRONG_SELL / wait for re-accumulation
"""

import time
import logging
import statistics
from enum import Enum
from dataclasses import dataclass, field
from typing import Optional

logger = logging.getLogger("strategy.wyckoff")


class WyckoffPhase(Enum):
    ACCUMULATION = "accumulation"
    MARKUP = "markup"
    DISTRIBUTION = "distribution"
    MARKDOWN = "markdown"
    UNKNOWN = "unknown"


class TradeSignal(Enum):
    STRONG_BUY = "strong_buy"
    BUY = "buy"
    HOLD = "hold"
    SELL = "sell"
    STRONG_SELL = "strong_sell"
    NO_ACTION = "no_action"


@dataclass
class MarketSnapshot:
    """Point-in-time market data for analysis."""
    price: float
    volume: float
    timestamp: float
    liquidity: float = 0.0
    high: float = 0.0
    low: float = 0.0


@dataclass
class PhaseAnalysis:
    """Result of Wyckoff phase detection."""
    phase: WyckoffPhase
    confidence: float
    signal: TradeSignal
    reason: str
    price_trend: str
    volume_trend: str
    suggested_action: str
    timestamp: float = field(default_factory=time.time)

    def to_dict(self) -> dict:
        return {
            "phase": self.phase.value,
            "confidence": round(self.confidence, 3),
            "signal": self.signal.value,
            "reason": self.reason,
            "price_trend": self.price_trend,
            "volume_trend": self.volume_trend,
            "suggested_action": self.suggested_action,
            "timestamp": self.timestamp,
        }


@dataclass
class WyckoffConfig:
    """Tunable parameters for phase detection."""
    trend_lookback_periods: int = 20
    sideways_threshold_pct: float = 3.0
    volume_lookback_periods: int = 10
    volume_surge_multiplier: float = 2.0
    accumulation_range_pct: float = 5.0
    markup_min_gain_pct: float = 10.0
    distribution_range_pct: float = 5.0
    markdown_min_loss_pct: float = 10.0
    false_breakout_pct: float = 3.0
    false_breakout_recovery_pct: float = 2.0
    min_data_points: int = 10


class WyckoffDetector:
    """
    Detects Wyckoff market cycle phases from price and volume data.
    Outputs PhaseAnalysis with trade signals (INTENTS, not orders).
    """

    def __init__(self, config: WyckoffConfig = None):
        self.config = config or WyckoffConfig()
        self._history: list[MarketSnapshot] = []
        self._current_phase: WyckoffPhase = WyckoffPhase.UNKNOWN
        self._phase_start_time: float = 0.0
        self._phase_start_price: float = 0.0

    def add_data(self, snapshot: MarketSnapshot):
        """Feed new market data into the detector."""
        self._history.append(snapshot)
        if len(self._history) > 500:
            self._history = self._history[-300:]

    def analyze(self) -> PhaseAnalysis:
        """Run Wyckoff phase analysis on current data."""
        if len(self._history) < self.config.min_data_points:
            return PhaseAnalysis(
                phase=WyckoffPhase.UNKNOWN,
                confidence=0.0,
                signal=TradeSignal.NO_ACTION,
                reason=f"Insufficient data ({len(self._history)}/{self.config.min_data_points})",
                price_trend="unknown",
                volume_trend="unknown",
                suggested_action="Wait for more data before trading",
            )

        price_trend = self._detect_price_trend()
        volume_trend = self._detect_volume_trend()
        price_range = self._calculate_price_range()
        momentum = self._calculate_momentum()

        phase, confidence, reason = self._detect_phase(
            price_trend, volume_trend, price_range, momentum
        )

        signal, action = self._generate_signal(phase, confidence, momentum)

        if phase != self._current_phase:
            old_phase = self._current_phase
            self._current_phase = phase
            self._phase_start_time = time.time()
            self._phase_start_price = self._history[-1].price
            logger.info(
                f"Phase transition: {old_phase.value} → {phase.value} "
                f"(confidence: {confidence:.1%})"
            )

        return PhaseAnalysis(
            phase=phase,
            confidence=confidence,
            signal=signal,
            reason=reason,
            price_trend=price_trend,
            volume_trend=volume_trend,
            suggested_action=action,
        )

    def _detect_price_trend(self) -> str:
        lookback = self.config.trend_lookback_periods
        prices = [s.price for s in self._history[-lookback:]]

        if len(prices) < 3:
            return "unknown"

        first_half_avg = statistics.mean(prices[:len(prices)//2])
        second_half_avg = statistics.mean(prices[len(prices)//2:])

        if first_half_avg <= 0:
            return "unknown"

        change_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100

        if change_pct > self.config.sideways_threshold_pct:
            return "up"
        elif change_pct < -self.config.sideways_threshold_pct:
            return "down"
        return "sideways"

    def _detect_volume_trend(self) -> str:
        lookback = self.config.volume_lookback_periods
        volumes = [s.volume for s in self._history[-lookback:] if s.volume > 0]

        if len(volumes) < 4:
            return "stable"

        first_half_avg = statistics.mean(volumes[:len(volumes)//2])
        second_half_avg = statistics.mean(volumes[len(volumes)//2:])

        if first_half_avg <= 0:
            return "stable"

        change_pct = ((second_half_avg - first_half_avg) / first_half_avg) * 100

        if change_pct > 30:
            return "increasing"
        elif change_pct < -30:
            return "decreasing"
        return "stable"

    def _calculate_price_range(self) -> float:
        lookback = self.config.trend_lookback_periods
        prices = [s.price for s in self._history[-lookback:]]
        if not prices or min(prices) <= 0:
            return 0.0
        return ((max(prices) - min(prices)) / min(prices)) * 100

    def _calculate_momentum(self) -> float:
        if len(self._history) < 5:
            return 0.0
        recent = self._history[-1].price
        earlier = self._history[-5].price
        if earlier <= 0:
            return 0.0
        return ((recent - earlier) / earlier) * 100

    def _detect_phase(
        self,
        price_trend: str,
        volume_trend: str,
        price_range: float,
        momentum: float,
    ) -> tuple:
        # ACCUMULATION: Sideways price, decreasing volume, after downtrend
        if (
            price_trend == "sideways"
            and volume_trend in ("decreasing", "stable")
            and price_range < self.config.accumulation_range_pct
        ):
            if self._was_recent_downtrend():
                return (
                    WyckoffPhase.ACCUMULATION,
                    0.7,
                    "Sideways consolidation with declining volume after downtrend",
                )
            return (
                WyckoffPhase.ACCUMULATION,
                0.4,
                "Sideways consolidation with low volume",
            )

        # MARKUP: Price trending up, increasing volume
        if (
            price_trend == "up"
            and momentum > self.config.markup_min_gain_pct * 0.3
        ):
            confidence = min(0.9, 0.5 + (momentum / 100))
            if volume_trend == "increasing":
                confidence = min(0.95, confidence + 0.15)
                return (
                    WyckoffPhase.MARKUP,
                    confidence,
                    f"Uptrend with increasing volume (momentum: {momentum:.1f}%)",
                )
            return (
                WyckoffPhase.MARKUP,
                confidence,
                f"Uptrend detected (momentum: {momentum:.1f}%)",
            )

        # DISTRIBUTION: Sideways after uptrend, high volume
        if (
            price_trend == "sideways"
            and volume_trend in ("increasing", "stable")
            and price_range < self.config.distribution_range_pct
        ):
            if self._was_recent_uptrend():
                return (
                    WyckoffPhase.DISTRIBUTION,
                    0.7,
                    "Sideways consolidation with high volume after uptrend",
                )
            return (
                WyckoffPhase.DISTRIBUTION,
                0.4,
                "Sideways with high volume",
            )

        # MARKDOWN: Price trending down, often with volume spike
        if (
            price_trend == "down"
            and momentum < -self.config.markdown_min_loss_pct * 0.3
        ):
            confidence = min(0.9, 0.5 + (abs(momentum) / 100))
            if volume_trend == "increasing":
                confidence = min(0.95, confidence + 0.15)
                return (
                    WyckoffPhase.MARKDOWN,
                    confidence,
                    f"Downtrend with panic volume (momentum: {momentum:.1f}%)",
                )
            return (
                WyckoffPhase.MARKDOWN,
                confidence,
                f"Downtrend detected (momentum: {momentum:.1f}%)",
            )

        return (
            WyckoffPhase.UNKNOWN,
            0.2,
            "No clear Wyckoff phase detected",
        )

    def _was_recent_downtrend(self) -> bool:
        if len(self._history) < 30:
            return False
        lookback = self.config.trend_lookback_periods
        earlier_prices = [s.price for s in self._history[-(lookback*2):-(lookback)]]
        if not earlier_prices or max(earlier_prices) <= 0:
            return False
        change = ((min(earlier_prices) - max(earlier_prices)) / max(earlier_prices)) * 100
        return change < -self.config.markdown_min_loss_pct * 0.5

    def _was_recent_uptrend(self) -> bool:
        if len(self._history) < 30:
            return False
        lookback = self.config.trend_lookback_periods
        earlier_prices = [s.price for s in self._history[-(lookback*2):-(lookback)]]
        if not earlier_prices or min(earlier_prices) <= 0:
            return False
        change = ((max(earlier_prices) - min(earlier_prices)) / min(earlier_prices)) * 100
        return change > self.config.markup_min_gain_pct * 0.5

    def _generate_signal(
        self,
        phase: WyckoffPhase,
        confidence: float,
        momentum: float,
    ) -> tuple:
        """Generate trade signal based on detected phase."""
        if confidence < 0.4:
            return TradeSignal.NO_ACTION, "Low confidence — no action recommended"

        if phase == WyckoffPhase.ACCUMULATION:
            if confidence > 0.6:
                return TradeSignal.BUY, "Accumulation phase — buy at support (good value)"
            return TradeSignal.HOLD, "Possible accumulation — hold and monitor"

        elif phase == WyckoffPhase.MARKUP:
            return TradeSignal.HOLD, "Markup phase — hold position, pause distribution"

        elif phase == WyckoffPhase.DISTRIBUTION:
            if confidence > 0.6:
                return TradeSignal.SELL, "Distribution phase — sell into demand (take profit)"
            return TradeSignal.HOLD, "Possible distribution — prepare to sell"

        elif phase == WyckoffPhase.MARKDOWN:
            if confidence > 0.6:
                return TradeSignal.STRONG_SELL, "Markdown phase — exit positions (stop loss)"
            return TradeSignal.SELL, "Possible markdown — reduce exposure"

        return TradeSignal.NO_ACTION, "Phase unclear — maintain current positions"

    def get_current_phase(self) -> WyckoffPhase:
        return self._current_phase

    def get_data_count(self) -> int:
        return len(self._history)

    def get_recent_prices(self, count: int = 20) -> list:
        return [s.price for s in self._history[-count:]]

    def reset(self):
        self._history.clear()
        self._current_phase = WyckoffPhase.UNKNOWN
        self._phase_start_time = 0.0
        self._phase_start_price = 0.0
