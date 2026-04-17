from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.services.signal_engine import (
    BUY_ZONE_UPPER_PCT,
    MA_WINDOW,
    SIGNAL_BREAKOUT,
    SIGNAL_BUY_ZONE,
    SIGNAL_INSUFFICIENT,
    SIGNAL_NEUTRAL,
    SLOPE_WINDOW,
    BarPoint,
    attach_pullback_returns,
    build_signals,
    classify,
    compute_distance_pct,
    compute_ma150_series,
    compute_slope,
    detect_pullbacks,
)

START = date(2025, 1, 1)


def _day(i: int) -> date:
    return START + timedelta(days=i)


def _bars(closes: list[float]) -> list[BarPoint]:
    return [BarPoint(date=_day(i), close=c) for i, c in enumerate(closes)]


# --- MA150 ------------------------------------------------------------------


def test_ma150_series_is_none_until_window_fills() -> None:
    closes = [float(i) for i in range(MA_WINDOW + 5)]
    series = compute_ma150_series(closes)
    assert all(v is None for v in series[: MA_WINDOW - 1])
    assert series[MA_WINDOW - 1] is not None
    assert series[MA_WINDOW - 1] == pytest.approx(
        sum(closes[:MA_WINDOW]) / MA_WINDOW
    )
    assert series[MA_WINDOW] == pytest.approx(
        sum(closes[1 : MA_WINDOW + 1]) / MA_WINDOW
    )


# --- Slope ------------------------------------------------------------------


def test_slope_positive_for_increasing_series() -> None:
    slope = compute_slope([float(i) for i in range(SLOPE_WINDOW)])
    assert slope is not None
    assert slope > 0


def test_slope_negative_for_decreasing_series() -> None:
    slope = compute_slope([float(-i) for i in range(SLOPE_WINDOW)])
    assert slope is not None
    assert slope < 0


def test_slope_none_when_below_window() -> None:
    assert compute_slope([1.0, 2.0, 3.0]) is None


# --- Distance % -------------------------------------------------------------


def test_distance_pct_calculation() -> None:
    assert compute_distance_pct(105.0, 100.0) == pytest.approx(5.0)
    assert compute_distance_pct(95.0, 100.0) == pytest.approx(-5.0)
    assert compute_distance_pct(100.0, None) is None


# --- classify ---------------------------------------------------------------


def test_classify_insufficient_when_ma_missing() -> None:
    assert (
        classify(
            close=100.0,
            ma150=None,
            prev_close=None,
            prev_ma150=None,
            slope_positive=None,
            distance_pct=None,
        )
        == SIGNAL_INSUFFICIENT
    )


def test_classify_buy_zone_when_slope_positive_and_in_range() -> None:
    # No crossing (prev close already above prev MA), still within 0-5% band → BUY_ZONE
    assert (
        classify(
            close=102.0,
            ma150=100.0,
            prev_close=101.5,
            prev_ma150=99.8,
            slope_positive=True,
            distance_pct=2.0,
        )
        == SIGNAL_BUY_ZONE
    )


def test_classify_breakout_beats_buy_zone() -> None:
    assert (
        classify(
            close=100.5,
            ma150=100.0,
            prev_close=98.0,
            prev_ma150=99.0,
            slope_positive=True,
            distance_pct=0.5,
        )
        == SIGNAL_BREAKOUT
    )


def test_classify_neutral_when_slope_negative() -> None:
    assert (
        classify(
            close=101.0,
            ma150=100.0,
            prev_close=100.5,
            prev_ma150=100.0,
            slope_positive=False,
            distance_pct=1.0,
        )
        == SIGNAL_NEUTRAL
    )


def test_classify_neutral_when_distance_above_buy_zone_upper() -> None:
    above = BUY_ZONE_UPPER_PCT + 0.01
    assert (
        classify(
            close=105.01,
            ma150=100.0,
            prev_close=104.0,
            prev_ma150=99.5,
            slope_positive=True,
            distance_pct=above,
        )
        == SIGNAL_NEUTRAL
    )


def test_classify_neutral_when_price_below_ma() -> None:
    assert (
        classify(
            close=99.0,
            ma150=100.0,
            prev_close=98.0,
            prev_ma150=100.0,
            slope_positive=True,
            distance_pct=-1.0,
        )
        == SIGNAL_NEUTRAL
    )


# --- build_signals end-to-end ----------------------------------------------


def _build_increasing_closes_with_pullback(length: int) -> list[float]:
    """Gently rising series so the most recent close lands ~3% above MA150."""
    return [100.0 + i * 0.05 for i in range(length)]


def test_build_signals_marks_insufficient_before_150() -> None:
    bars = _bars([100.0 + i * 0.1 for i in range(140)])
    signals = build_signals(bars)
    assert len(signals) == 140
    assert all(s.signal_type == SIGNAL_INSUFFICIENT for s in signals)


def test_build_signals_buy_zone_after_rising_history() -> None:
    closes = _build_increasing_closes_with_pullback(200)
    bars = _bars(closes)
    signals = build_signals(bars)
    last = signals[-1]
    assert last.ma150_value is not None
    assert last.distance_pct is not None and last.distance_pct >= 0
    assert last.slope_positive is True
    assert last.signal_type in {SIGNAL_BUY_ZONE, SIGNAL_BREAKOUT}


def test_build_signals_breakout_takes_priority() -> None:
    # Gently rising trend, penultimate bar dips below MA, last bar crosses back above
    closes = [100.0 + i * 0.01 for i in range(198)]
    closes.append(101.1)
    closes.append(102.0)
    bars = _bars(closes)
    signals = build_signals(bars)
    assert signals[-2].close_price < (signals[-2].ma150_value or 0)
    assert signals[-1].signal_type == SIGNAL_BREAKOUT


# --- Pullback detection -----------------------------------------------------


def test_detect_pullbacks_only_on_transition() -> None:
    # Construct artificial signals with alternating BUY_ZONE states
    from app.services.signal_engine import SignalPoint

    types = [
        SIGNAL_NEUTRAL,
        SIGNAL_BUY_ZONE,  # pullback #1
        SIGNAL_BUY_ZONE,  # ignored (continuation)
        SIGNAL_NEUTRAL,
        SIGNAL_BUY_ZONE,  # pullback #2
        SIGNAL_NEUTRAL,
    ]
    signals = [
        SignalPoint(
            date=_day(i),
            signal_type=t,
            close_price=100.0 + i,
            ma150_value=99.0,
            distance_pct=(100.0 + i - 99.0) / 99.0 * 100,
            slope_positive=True,
            slope_value=0.1,
        )
        for i, t in enumerate(types)
    ]
    pullbacks = detect_pullbacks(signals)
    assert [p.date for p in pullbacks] == [_day(1), _day(4)]


# --- Pullback returns -------------------------------------------------------


def test_attach_pullback_returns_computes_horizons() -> None:
    from app.services.signal_engine import PullbackPoint

    bars = _bars([100.0 + i for i in range(50)])
    pullback = PullbackPoint(
        date=_day(0),
        close_price=100.0,
        ma150_value=100.0,
        distance_pct=0.0,
        return_10d=None,
        return_20d=None,
        return_30d=None,
    )
    [enriched] = attach_pullback_returns([pullback], bars)
    assert enriched.return_10d == pytest.approx((110.0 - 100.0) / 100.0 * 100)
    assert enriched.return_20d == pytest.approx((120.0 - 100.0) / 100.0 * 100)
    assert enriched.return_30d == pytest.approx((130.0 - 100.0) / 100.0 * 100)


def test_attach_pullback_returns_none_when_horizon_missing() -> None:
    from app.services.signal_engine import PullbackPoint

    bars = _bars([100.0 + i for i in range(15)])
    pullback = PullbackPoint(
        date=_day(0),
        close_price=100.0,
        ma150_value=100.0,
        distance_pct=0.0,
        return_10d=None,
        return_20d=None,
        return_30d=None,
    )
    [enriched] = attach_pullback_returns([pullback], bars)
    assert enriched.return_10d is not None
    assert enriched.return_20d is None
    assert enriched.return_30d is None
