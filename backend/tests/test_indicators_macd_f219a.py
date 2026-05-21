"""F219-a: Unit tests for compute_macd_series + detect_macd_divergence.

Sprint Contract standards covered:
  #1  compute_macd_series — 3 fixture shapes (monotonic up/down/sine), first 25 positions None
  #2  compute_macd_series — len(closes) < SLOW → all-None list
  #3  detect_macd_divergence — bearish case
  #4  detect_macd_divergence — bullish case
  #5  detect_macd_divergence — no divergence → None
  #6  detect_macd_divergence — macd_line[-1] is None (short history) → None
  #7  detect_macd_divergence — pathological both bearish+bullish → None, no exception
"""
from __future__ import annotations

import math

import pytest

from app.services.cockpit._indicators import compute_macd_series, detect_macd_divergence
from app.services.cockpit.cockpit_params import MACD


# ── Reference EMA helper (mirrors chart_service._compute_ema_series logic) ─────

def _ref_ema(values: list[float], period: int) -> list[float | None]:
    """Reference EMA series: seed=SMA(period), then α=2/(period+1)."""
    n = len(values)
    result: list[float | None] = [None] * n
    if n < period:
        return result
    alpha = 2.0 / (period + 1)
    ema = sum(values[:period]) / period
    result[period - 1] = ema
    for i in range(period, n):
        ema = alpha * values[i] + (1 - alpha) * ema
        result[i] = ema
    return result


def _ref_macd(closes: list[float], fast: int, slow: int) -> list[float | None]:
    fast_emas = _ref_ema(closes, fast)
    slow_emas = _ref_ema(closes, slow)
    result: list[float | None] = [None] * len(closes)
    for i in range(slow - 1, len(closes)):
        f = fast_emas[i]
        s = slow_emas[i]
        if f is not None and s is not None:
            result[i] = f - s
    return result


# ── Test #1: compute_macd_series fixture shapes ────────────────────────────────

class TestComputeMacdSeriesFixtures:
    """#1: Hand-calc fixtures for 3 close shapes; first (SLOW-1)=25 positions must be None."""

    def _assert_macd_matches_ref(self, closes: list[float]) -> None:
        fast, slow = MACD.FAST, MACD.SLOW  # 12, 26
        result = compute_macd_series(closes, fast, slow)
        expected = _ref_macd(closes, fast, slow)
        assert len(result) == len(closes)
        for i, (got, exp) in enumerate(zip(result, expected)):
            if exp is None:
                assert got is None, f"index {i}: expected None, got {got}"
            else:
                assert got is not None, f"index {i}: expected {exp}, got None"
                assert abs(got - exp) < 1e-6, f"index {i}: {got} vs {exp}"

    def test_s1_monotonic_up_first_25_none(self):
        """#1a: Monotonically increasing closes — first 25 positions None."""
        closes = [100.0 + i for i in range(100)]
        result = compute_macd_series(closes, MACD.FAST, MACD.SLOW)
        for i in range(MACD.SLOW - 1):  # 0..24
            assert result[i] is None, f"index {i} should be None"
        assert result[MACD.SLOW - 1] is not None

    def test_s1_monotonic_up_values_match_ref(self):
        """#1a: Monotonically increasing — values match reference EMA to 1e-6."""
        closes = [100.0 + i for i in range(100)]
        self._assert_macd_matches_ref(closes)

    def test_s1_monotonic_down_values_match_ref(self):
        """#1b: Monotonically decreasing — values match reference EMA to 1e-6."""
        closes = [200.0 - i * 0.5 for i in range(100)]
        self._assert_macd_matches_ref(closes)

    def test_s1_sine_wave_values_match_ref(self):
        """#1c: Sinusoidal closes — values match reference EMA to 1e-6."""
        closes = [100.0 + 10.0 * math.sin(i * 0.3) for i in range(100)]
        self._assert_macd_matches_ref(closes)

    def test_s1_monotonic_up_macd_positive(self):
        """Fast EMA > slow EMA on monotonically rising series → MACD > 0."""
        closes = [100.0 + i for i in range(100)]
        result = compute_macd_series(closes, MACD.FAST, MACD.SLOW)
        for v in result[MACD.SLOW - 1:]:
            assert v is not None and v > 0


# ── Test #2: short input → all None ───────────────────────────────────────────

class TestComputeMacdSeriesShortInput:
    """#2: len(closes) < SLOW → all-None list of same length."""

    def test_s2_empty_list(self):
        result = compute_macd_series([], MACD.FAST, MACD.SLOW)
        assert result == []

    def test_s2_too_short(self):
        closes = [100.0] * (MACD.SLOW - 1)  # 25 bars, need 26
        result = compute_macd_series(closes, MACD.FAST, MACD.SLOW)
        assert len(result) == len(closes)
        assert all(v is None for v in result)

    def test_s2_exactly_slow_first_valid(self):
        """Exactly SLOW bars — position SLOW-1 has valid MACD."""
        closes = [100.0 + i for i in range(MACD.SLOW)]
        result = compute_macd_series(closes, MACD.FAST, MACD.SLOW)
        assert len(result) == MACD.SLOW
        assert all(v is None for v in result[: MACD.SLOW - 1])
        assert result[MACD.SLOW - 1] is not None


# ── Test #3: detect_macd_divergence — bearish ─────────────────────────────────

class TestDetectMacdDivergenceBearish:
    """#3: closes[-1] == 20d max AND macd_line[-1] < 20d macd max → 'bearish'."""

    def test_s3_bearish_detected(self):
        lookback = 20
        # Closes: mostly flat then spike at end (price new high)
        closes = [100.0] * (lookback - 1) + [110.0]  # 110 is the max
        # MACD: mostly at 2.0 then drops to 1.0 (NOT the max)
        macd_line: list[float | None] = [2.0] * (lookback - 1) + [1.0]
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result == "bearish"

    def test_s3_bearish_when_macd_below_prior_high(self):
        lookback = 5
        closes = [100.0, 102.0, 101.0, 103.0, 105.0]  # 105 is max
        macd_line: list[float | None] = [0.5, 1.0, 0.8, 0.7, 0.6]  # 0.6 < max 1.0
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result == "bearish"


# ── Test #4: detect_macd_divergence — bullish ─────────────────────────────────

class TestDetectMacdDivergenceBullish:
    """#4: closes[-1] == 20d min AND macd_line[-1] > 20d macd min → 'bullish'."""

    def test_s4_bullish_detected(self):
        lookback = 20
        # Closes: mostly flat then drops (price new low)
        closes = [100.0] * (lookback - 1) + [90.0]  # 90 is the min
        # MACD: hit low at -2.0 earlier, now -1.0 (NOT the min)
        macd_line: list[float | None] = [-2.0] * (lookback - 1) + [-1.0]
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result == "bullish"

    def test_s4_bullish_when_macd_above_prior_low(self):
        lookback = 5
        closes = [100.0, 98.0, 99.0, 97.0, 95.0]  # 95 is min
        macd_line: list[float | None] = [-0.5, -1.0, -0.8, -0.7, -0.6]  # -0.6 > min -1.0
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result == "bullish"


# ── Test #5: no divergence → None ─────────────────────────────────────────────

class TestDetectMacdDivergenceNone:
    """#5: closes[-1] neither 20d high nor 20d low → None."""

    def test_s5_mid_range_close(self):
        lookback = 5
        closes = [100.0, 105.0, 103.0, 102.0, 101.0]  # last=101, max=105, min=100
        macd_line: list[float | None] = [0.5, 1.0, 0.8, 0.7, 0.6]
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result is None

    def test_s5_price_at_high_macd_also_at_high(self):
        """Price at 20d high but MACD also at 20d high → not bearish → None."""
        lookback = 5
        closes = [100.0, 101.0, 102.0, 103.0, 105.0]  # 105 is max
        macd_line: list[float | None] = [0.5, 0.7, 0.8, 0.9, 1.0]  # 1.0 IS max
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result is None

    def test_s5_price_at_low_macd_also_at_low(self):
        """Price at 20d low but MACD also at 20d low → not bullish → None."""
        lookback = 5
        closes = [105.0, 103.0, 102.0, 101.0, 100.0]  # 100 is min
        macd_line: list[float | None] = [1.0, 0.8, 0.6, 0.4, 0.3]  # 0.3 IS min
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result is None


# ── Test #6: macd_line[-1] is None → None ─────────────────────────────────────

class TestDetectMacdDivergenceNullMacd:
    """#6: any None in macd_line[-lookback:] → None (short history guard)."""

    def test_s6_last_macd_none(self):
        lookback = 5
        closes = [100.0, 102.0, 101.0, 103.0, 105.0]
        macd_line: list[float | None] = [0.5, 0.7, 0.8, 0.9, None]
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result is None

    def test_s6_mid_window_macd_none(self):
        lookback = 5
        closes = [100.0, 102.0, 101.0, 103.0, 105.0]
        macd_line: list[float | None] = [0.5, None, 0.8, 0.9, 0.3]
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result is None

    def test_s6_all_none_macd(self):
        lookback = 5
        closes = [100.0] * 5
        macd_line: list[float | None] = [None] * 5
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result is None


# ── Test #7: pathological — both conditions or too short → None, no exception ──

class TestDetectMacdDivergencePathological:
    """#7: both bearish+bullish simultaneously (flat sequence) → None, no exception."""

    def test_s7_flat_closes_both_high_and_low(self):
        """All closes equal → last is both max and min.
        macd_last between (min, max) → both bearish and bullish conditions true → None.
        """
        lookback = 5
        closes = [100.0] * 5  # all equal: last == max AND last == min
        # macd min=0.3, max=1.5, last=0.7 → 0.7 < 1.5 (bearish) AND 0.7 > 0.3 (bullish)
        macd_line: list[float | None] = [1.5, 0.3, 0.8, 1.2, 0.7]
        result = detect_macd_divergence(closes, macd_line, lookback)
        assert result is None  # both → None

    def test_s7_too_short_input(self):
        """len(closes) < lookback → None, no exception."""
        closes = [100.0, 101.0]
        macd_line: list[float | None] = [0.5, 0.6]
        result = detect_macd_divergence(closes, macd_line, 5)
        assert result is None

    def test_s7_empty_input(self):
        result = detect_macd_divergence([], [], 20)
        assert result is None
