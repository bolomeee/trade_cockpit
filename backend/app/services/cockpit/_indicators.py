"""Reusable technical indicator pure functions used by chart_service and setup_service."""
from __future__ import annotations


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
