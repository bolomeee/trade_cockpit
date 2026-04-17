from __future__ import annotations

from dataclasses import dataclass
from datetime import date

MA_WINDOW = 150
SLOPE_WINDOW = 20
BUY_ZONE_UPPER_PCT = 5.0
SIGNAL_RETENTION_DAYS = 250
PULLBACK_RETURN_HORIZONS = (10, 20, 30)

SIGNAL_BREAKOUT = "BREAKOUT"
SIGNAL_BUY_ZONE = "BUY_ZONE"
SIGNAL_NEUTRAL = "NEUTRAL"
SIGNAL_INSUFFICIENT = "INSUFFICIENT"

SIGNAL_PRIORITY = {
    SIGNAL_BREAKOUT: 0,
    SIGNAL_BUY_ZONE: 1,
    SIGNAL_NEUTRAL: 2,
    SIGNAL_INSUFFICIENT: 3,
}


@dataclass(frozen=True)
class BarPoint:
    date: date
    close: float


@dataclass(frozen=True)
class SignalPoint:
    date: date
    signal_type: str
    close_price: float
    ma150_value: float | None
    distance_pct: float | None
    slope_positive: bool | None
    slope_value: float | None


@dataclass(frozen=True)
class PullbackPoint:
    date: date
    close_price: float
    ma150_value: float
    distance_pct: float
    return_10d: float | None
    return_20d: float | None
    return_30d: float | None


def compute_ma150_series(closes: list[float]) -> list[float | None]:
    series: list[float | None] = []
    running_sum = 0.0
    for i, price in enumerate(closes):
        running_sum += price
        if i >= MA_WINDOW:
            running_sum -= closes[i - MA_WINDOW]
        if i + 1 >= MA_WINDOW:
            series.append(running_sum / MA_WINDOW)
        else:
            series.append(None)
    return series


def compute_slope(ma_window_values: list[float]) -> float | None:
    if len(ma_window_values) < SLOPE_WINDOW:
        return None
    ys = ma_window_values[-SLOPE_WINDOW:]
    n = SLOPE_WINDOW
    x_mean = (n - 1) / 2.0
    y_mean = sum(ys) / n
    num = sum((i - x_mean) * (y - y_mean) for i, y in enumerate(ys))
    den = sum((i - x_mean) ** 2 for i in range(n))
    if den == 0:
        return None
    return num / den


def compute_distance_pct(close: float, ma150: float | None) -> float | None:
    if ma150 is None or ma150 == 0:
        return None
    return (close - ma150) / ma150 * 100.0


def classify(
    close: float,
    ma150: float | None,
    prev_close: float | None,
    prev_ma150: float | None,
    slope_positive: bool | None,
    distance_pct: float | None,
) -> str:
    if ma150 is None:
        return SIGNAL_INSUFFICIENT
    if slope_positive is not True:
        return SIGNAL_NEUTRAL
    if (
        prev_close is not None
        and prev_ma150 is not None
        and prev_close < prev_ma150
        and close >= ma150
    ):
        return SIGNAL_BREAKOUT
    if distance_pct is not None and 0.0 <= distance_pct <= BUY_ZONE_UPPER_PCT:
        return SIGNAL_BUY_ZONE
    return SIGNAL_NEUTRAL


def build_signals(bars: list[BarPoint]) -> list[SignalPoint]:
    if not bars:
        return []
    closes = [b.close for b in bars]
    ma_series = compute_ma150_series(closes)
    signals: list[SignalPoint] = []
    for i, bar in enumerate(bars):
        ma = ma_series[i]
        prev_ma = ma_series[i - 1] if i > 0 else None
        prev_close = bars[i - 1].close if i > 0 else None
        ma_window = [v for v in ma_series[: i + 1] if v is not None]
        slope = compute_slope(ma_window)
        slope_positive = None if slope is None else slope > 0
        distance_pct = compute_distance_pct(bar.close, ma)
        signal_type = classify(
            close=bar.close,
            ma150=ma,
            prev_close=prev_close,
            prev_ma150=prev_ma,
            slope_positive=slope_positive,
            distance_pct=distance_pct,
        )
        signals.append(
            SignalPoint(
                date=bar.date,
                signal_type=signal_type,
                close_price=bar.close,
                ma150_value=ma,
                distance_pct=distance_pct,
                slope_positive=slope_positive,
                slope_value=slope,
            )
        )
    return signals


def detect_pullbacks(signals: list[SignalPoint]) -> list[PullbackPoint]:
    pullbacks: list[PullbackPoint] = []
    prev_type: str | None = None
    for s in signals:
        if s.signal_type == SIGNAL_BUY_ZONE and prev_type != SIGNAL_BUY_ZONE:
            if s.ma150_value is not None and s.distance_pct is not None:
                pullbacks.append(
                    PullbackPoint(
                        date=s.date,
                        close_price=s.close_price,
                        ma150_value=s.ma150_value,
                        distance_pct=s.distance_pct,
                        return_10d=None,
                        return_20d=None,
                        return_30d=None,
                    )
                )
        prev_type = s.signal_type
    return pullbacks


def attach_pullback_returns(
    pullbacks: list[PullbackPoint], bars: list[BarPoint]
) -> list[PullbackPoint]:
    date_to_index = {b.date: i for i, b in enumerate(bars)}
    enriched: list[PullbackPoint] = []
    for p in pullbacks:
        idx = date_to_index.get(p.date)
        if idx is None:
            enriched.append(p)
            continue
        base = bars[idx].close
        returns: list[float | None] = []
        for horizon in PULLBACK_RETURN_HORIZONS:
            target = idx + horizon
            if target < len(bars) and base != 0:
                returns.append((bars[target].close - base) / base * 100.0)
            else:
                returns.append(None)
        enriched.append(
            PullbackPoint(
                date=p.date,
                close_price=p.close_price,
                ma150_value=p.ma150_value,
                distance_pct=p.distance_pct,
                return_10d=returns[0],
                return_20d=returns[1],
                return_30d=returns[2],
            )
        )
    return enriched
