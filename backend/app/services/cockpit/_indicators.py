"""Reusable technical indicator pure functions used by chart_service and setup_service."""
from __future__ import annotations

from typing import Literal


def compute_wilder_atr(
    highs: list[float],
    lows: list[float],
    closes: list[float],
    period: int,
) -> list[float]:
    """Wilder ATR series (pure, no dates).

    TR_i = max(H_i - L_i, |H_i - C_{i-1}|, |L_i - C_{i-1}|)  for i >= 1.
    seed  = SMA(TR, period)  using the first `period` TRs.
    ATR_i = (ATR_{i-1} * (period - 1) + TR_i) / period thereafter.

    Returns list[float] of length max(0, n - period) where n = len(closes).
    Returns [] when n < period + 1.
    """
    n = len(closes)
    if period <= 0 or n < period + 1:
        return []

    trs: list[float] = []
    for i in range(1, n):
        tr = max(highs[i] - lows[i], abs(highs[i] - closes[i - 1]), abs(lows[i] - closes[i - 1]))
        trs.append(tr)

    # trs has n-1 elements; need at least `period` to seed
    if len(trs) < period:
        return []

    seed = sum(trs[:period]) / period
    result = [seed]
    current = seed
    for i in range(period, len(trs)):
        current = (current * (period - 1) + trs[i]) / period
        result.append(current)

    return result


def compute_macd_series(closes: list[float], fast: int, slow: int) -> list[float | None]:
    """MACD line = EMA(closes, fast) - EMA(closes, slow).

    Uses α=2/(period+1), seed=SMA(period) — same algorithm as chart_service._compute_ema_series.
    Returns list same length as closes; first (slow-1) positions are None.
    Returns all-None list when len(closes) < slow.
    """
    n = len(closes)
    result: list[float | None] = [None] * n
    if n < slow:
        return result

    alpha_fast = 2.0 / (fast + 1)
    fast_ema = sum(closes[:fast]) / fast
    fast_emas: list[float | None] = [None] * n
    fast_emas[fast - 1] = fast_ema
    for i in range(fast, n):
        fast_ema = alpha_fast * closes[i] + (1 - alpha_fast) * fast_ema
        fast_emas[i] = fast_ema

    alpha_slow = 2.0 / (slow + 1)
    slow_ema = sum(closes[:slow]) / slow
    slow_emas: list[float | None] = [None] * n
    slow_emas[slow - 1] = slow_ema
    for i in range(slow, n):
        slow_ema = alpha_slow * closes[i] + (1 - alpha_slow) * slow_ema
        slow_emas[i] = slow_ema

    for i in range(slow - 1, n):
        f = fast_emas[i]
        s = slow_emas[i]
        if f is not None and s is not None:
            result[i] = f - s

    return result


def detect_macd_divergence(
    closes: list[float],
    macd_line: list[float | None],
    lookback: int,
) -> Literal["bearish", "bullish"] | None:
    """Detect price-vs-MACD divergence over the last `lookback` bars.

    bearish: closes[-1] == max(closes[-lookback:]) AND macd_line[-1] < max(macd_line[-lookback:])
    bullish: closes[-1] == min(closes[-lookback:]) AND macd_line[-1] > min(macd_line[-lookback:])
    Both satisfied simultaneously (pathological) or neither → None.
    Any None in macd_line[-lookback:] → None.
    """
    if len(closes) < lookback or len(macd_line) < lookback:
        return None

    macd_window = macd_line[-lookback:]
    if any(v is None for v in macd_window):
        return None

    macd_valid: list[float] = macd_window  # type: ignore[assignment]
    closes_window = closes[-lookback:]

    close_last = closes_window[-1]
    macd_last = macd_valid[-1]

    bearish = close_last == max(closes_window) and macd_last < max(macd_valid)
    bullish = close_last == min(closes_window) and macd_last > min(macd_valid)

    if bearish and bullish:
        return None
    if bearish:
        return "bearish"
    if bullish:
        return "bullish"
    return None
