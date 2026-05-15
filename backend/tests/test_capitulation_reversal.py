"""F217-a Capitulation Reversal pure tests — Sprint Contract T1-T12.

T1   常量重命名验证
T2   compute_wilder_atr Wilder 算法正确性
T3   chart_service _compute_atr_series 重构后数值逐位对齐
T4   _detect_swing_lows 降序索引列表
T5   7 AND 门 happy path
T6   每条门单独失败 (7 sub-tests, gate5 via lookahead design)
T7   数据不足分支
T8   条件 5 尾部数据处理（lookahead-safe）
T9   优先级测试 (5 sub-tests)
T10  docstring + 死代码扫描
T11  _ACTIONABLE_TYPES 包含 CAPITULATION
T12  compute_and_store_all 集成：不写 PULLBACK；CAPITULATION entry/stop 符合 NP3
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.models import Base
from app.models.daily_bar import DailyBar
from app.models.market_index import MarketIndex
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock
from app.services.cockpit._indicators import compute_wilder_atr
from app.services.cockpit.chart_service import _compute_atr_series
from app.services.cockpit.cockpit_params import SETUP
from app.services.cockpit.setup_service import (
    SETUP_CAPITULATION,
    SetupService,
    _ACTIONABLE_TYPES,
    _classify_setup_type,
    _detect_swing_lows,
    _is_capitulation_reversal,
)

# ── _base_cap_inputs: 80-bar explicit design satisfying all 7 gates ───────────
#
# Structure (n=80):
#   0-49   : uptrend, close 80→104.5, lows 79→103.5 (TR≈2)
#   50-53  : dip, swing low @ idx 51  low=74  (gate 6: 2nd most-recent)
#   54-59  : recovery to ~155
#   60-63  : dip, swing low @ idx 61  low=89  (gate 6: most-recent)
#   64-70  : recovery to 170
#   71-78  : decline stock 170→145, SPY 540→508 (gate 1: 12.7%+ drop)
#   79     : capitulation bar: close=144, low=120, high=155, SPY=440
#
# Gate checks (all must pass):
#   G1  drop: close[-8]=165  → (165-144)/165 = 12.7% ≥ 10% ✓
#   G2  vol_z: vols[-1]=20M, base varied → z >> 2.5 ✓
#   G3  TR=max(35,11,25)=35 ≥ 2.0*ATR14(≈4) ✓
#   G4  (144-120)/(155-120)=0.686 ≥ (1-0.333)=0.667 ✓
#   G5  always skip (no future bars) ✓
#   G6  swing_lows=[61(low=89),51(low=74)]; today low=120>74 ✓
#   G7  rs_today=144/440=0.327 > min_rs_prev=145/508=0.285 ✓

_TODAY = date(2026, 5, 15)
_START = date(2025, 1, 1)


def _base_cap_inputs() -> tuple[list[float], list[float], list[float], list[int], list[float]]:
    """Return (closes, highs, lows, volumes, spy_closes) where bar[-1] passes all 7 gates."""
    n = 80
    closes: list[float] = [0.0] * n
    highs:  list[float] = [0.0] * n
    lows:   list[float] = [0.0] * n
    spy:    list[float] = [0.0] * n

    # Phase 1: uptrend 0-49
    for i in range(50):
        closes[i] = 80.0 + i * 0.5
        highs[i]  = closes[i] + 1.0
        lows[i]   = closes[i] - 1.0
        spy[i]    = 400.0 + i * 1.5

    # Phase 2: dip → swing low at index 51 (low=74, below today's 120)
    _vals = [(110.0, 111.0, 109.0, 477.0),
             (75.0,   80.0,  74.0, 470.0),   # swing low
             (112.0, 113.0, 111.0, 475.0),
             (115.0, 116.0, 114.0, 480.0)]
    for j, (c, h, lo, s) in enumerate(_vals):
        closes[50+j] = c
        highs[50+j] = h
        lows[50+j] = lo
        spy[50+j] = s

    # Phase 3: recovery 54-59
    for i in range(54, 60):
        closes[i] = 115.0 + (i - 54) * 8.0
        highs[i]  = closes[i] + 1.0
        lows[i]   = closes[i] - 1.0
        spy[i]    = 480.0 + (i - 54) * 8.0

    # Phase 4: dip → swing low at index 61 (low=89, most-recent in lookback)
    _vals2 = [(158.0, 160.0, 157.0, 520.0),
              (90.0,   95.0,  89.0, 510.0),   # swing low
              (160.0, 162.0, 159.0, 520.0),
              (163.0, 165.0, 162.0, 525.0)]
    for j, (c, h, lo, s) in enumerate(_vals2):
        closes[60+j] = c
        highs[60+j] = h
        lows[60+j] = lo
        spy[60+j] = s

    # Phase 5: continued recovery 64-70
    for i in range(64, 71):
        closes[i] = 163.0 + (i - 64) * 1.0
        highs[i]  = closes[i] + 1.0
        lows[i]   = closes[i] - 1.0
        spy[i]    = 525.0 + (i - 64) * 2.0

    # Phase 6: decline 71-78 (stock 170→145, SPY 540→508)
    _dc = [170.0, 165.0, 161.0, 157.0, 153.0, 150.0, 147.0, 145.0]
    _ds = [540.0, 536.0, 532.0, 528.0, 524.0, 520.0, 514.0, 508.0]
    for i in range(8):
        closes[71+i] = _dc[i]
        highs[71+i]  = _dc[i] + 1.5
        lows[71+i]   = _dc[i] - 1.5
        spy[71+i]    = _ds[i]

    # Phase 7: capitulation bar (index 79)
    closes[79] = 144.0   # in upper bin: (144-120)/(155-120) = 0.686 ≥ 0.667
    highs[79]  = 155.0
    lows[79]   = 120.0   # today's low > 2nd swing low (74) ✓
    spy[79]    = 440.0   # SPY drops → rs_today=144/440=0.327 > prev_min=145/508=0.285 ✓

    # Volumes: deterministic variance so z-score is computable; last bar huge
    vols = [1_000_000 + (i % 11) * 100_000 for i in range(n)]
    vols[79] = 20_000_000   # far above mean → z >> 2.5

    return closes, highs, lows, vols, spy


# ── T1: Constants ─────────────────────────────────────────────────────────────


def test_t1_setup_capitulation_constant_exists() -> None:
    assert SETUP_CAPITULATION == "CAPITULATION"


def test_t1_setup_pullback_constant_removed() -> None:
    import app.services.cockpit.setup_service as svc_mod
    assert not hasattr(svc_mod, "SETUP_PULLBACK"), "SETUP_PULLBACK should be removed"


def test_t1_all_four_pullback_fields_removed() -> None:
    assert not hasattr(SETUP, "PULLBACK_STOP_MA21_PCT")
    assert not hasattr(SETUP, "PULLBACK_FLOOR_MA50_PCT")
    assert not hasattr(SETUP, "PULLBACK_ZONE_ABOVE_MA50_PCT")
    assert not hasattr(SETUP, "PULLBACK_FALLBACK_SUPPORT_PCT")


# ── T2: compute_wilder_atr ────────────────────────────────────────────────────


def test_t2_wilder_atr_hand_calc() -> None:
    # period=2, 4 bars
    # TR1=max(2,1,1)=2  TR2=max(5,3,2)=5  TR3=max(2,1,1)=2
    # seed=(2+5)/2=3.5; ATR=(3.5*1+2)/2=2.75
    h = [10.0, 11.0, 13.0, 12.0]
    lo = [8.0,  9.0,  8.0,  10.0]
    c = [9.0,  10.0, 11.0, 11.0]
    r = compute_wilder_atr(h, lo, c, 2)
    assert len(r) == 2
    assert abs(r[0] - 3.5) < 1e-9
    assert abs(r[1] - 2.75) < 1e-9


def test_t2_insufficient_data_returns_empty() -> None:
    assert compute_wilder_atr([1.0] * 3, [0.9] * 3, [1.0] * 3, 14) == []
    assert compute_wilder_atr([], [], [], 14) == []


def test_t2_wilder_smoothing_formula() -> None:
    # 5 bars, period=2 → 3 ATR values
    h = [10.0, 11.0, 12.0, 11.5, 10.5]
    lo = [9.0,  9.5,  10.5, 9.5,  9.0]
    c = [9.5,  10.0, 11.0, 10.0, 9.5]
    r = compute_wilder_atr(h, lo, c, 2)
    assert len(r) == 3
    trs = [max(h[i]-lo[i], abs(h[i]-c[i-1]), abs(lo[i]-c[i-1])) for i in range(1, 5)]
    seed = (trs[0] + trs[1]) / 2
    a1 = (seed + trs[2]) / 2
    a2 = (a1 + trs[3]) / 2
    assert abs(r[0] - seed) < 1e-9
    assert abs(r[1] - a1) < 1e-9
    assert abs(r[2] - a2) < 1e-9


# ── T3: chart_service _compute_atr_series alignment ──────────────────────────


def test_t3_chart_service_atr_matches_indicator() -> None:
    """_compute_atr_series output must align digit-for-digit with compute_wilder_atr."""
    n = 30
    bars = [
        {
            "date": date(2024, 1, 1) + timedelta(days=i),
            "open": 100.0,
            "high": 100.0 + i * 0.3 + 1.5,
            "low":  100.0 + i * 0.3 - 1.5,
            "close": 100.0 + i * 0.3,
            "volume": 1_000_000,
        }
        for i in range(n)
    ]
    period = 14
    chart_result = _compute_atr_series(bars, period)
    indicator_result = compute_wilder_atr(
        [b["high"] for b in bars],
        [b["low"]  for b in bars],
        [b["close"] for b in bars],
        period,
    )
    assert len(chart_result) == len(indicator_result)
    for item, val in zip(chart_result, indicator_result):
        assert abs(item["value"] - val) < 1e-9, f"mismatch: {item['value']} vs {val}"


# ── T4: _detect_swing_lows ────────────────────────────────────────────────────


def test_t4_detect_swing_lows_descending_order() -> None:
    lows = [5.0, 3.0, 4.0, 2.0, 3.5, 6.0, 1.5, 4.0, 3.0]
    result = _detect_swing_lows(lows, 30)
    assert result == sorted(result, reverse=True)


def test_t4_zero_swing_lows() -> None:
    assert _detect_swing_lows([3.0] * 10, 30) == []


def test_t4_one_swing_low() -> None:
    lows = [5.0, 3.0, 5.0]
    result = _detect_swing_lows(lows, 30)
    assert 1 in result


def test_t4_two_swing_lows() -> None:
    lows = [5.0, 2.0, 4.0, 1.0, 3.0, 5.0]
    result = _detect_swing_lows(lows, 30)
    assert 1 in result and 3 in result
    assert len(result) == 2


def test_t4_lookback_limits_search() -> None:
    # lookback=3 → start = max(1, 5-3)=2; only checks idx 2,3 (not 4 — no i+1)
    lows = [5.0, 2.0, 4.0, 3.5, 5.0]
    result = _detect_swing_lows(lows, 3)
    assert 1 not in result
    assert 3 in result


# ── T5: 7 AND gates happy path ────────────────────────────────────────────────


def test_t5_capitulation_happy_path() -> None:
    """_base_cap_inputs satisfies all 7 gates → True."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is True


# ── T6: each gate fails individually ─────────────────────────────────────────


def test_t6_gate1_drop_too_small() -> None:
    closes, highs, lows, vols, spy = _base_cap_inputs()
    # Flatten recent 15 bars so no window [5,10] can show ≥10% drop
    last = closes[-1]
    for i in range(1, 16):
        closes[-i - 1] = last * (1 + 0.001 * i)   # only ~1.5% gap max
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is False


def test_t6_gate2_vol_zscore_too_low() -> None:
    closes, highs, lows, vols, spy = _base_cap_inputs()
    # Make all vols uniform → std=0 → z-score=None → gate fails
    vols = [1_000_000] * len(vols)
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is False


def test_t6_gate3_tr_too_small() -> None:
    closes, highs, lows, vols, spy = _base_cap_inputs()
    # Squash last bar range to tiny → TR << ATR14
    highs[-1] = closes[-1] + 0.01
    lows[-1]  = closes[-1] - 0.01
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is False


def test_t6_gate4_close_in_lower_bin() -> None:
    closes, highs, lows, vols, spy = _base_cap_inputs()
    # Move close to bottom 10% of range
    bar_range = highs[-1] - lows[-1]
    closes[-1] = lows[-1] + bar_range * 0.05   # bottom 5%
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is False


def test_t6_gate6_lower_low_vs_second_swing() -> None:
    """Gate 6: today's low below 2nd most-recent swing low → False."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    # In _base_cap_inputs swing_lows[1]=idx 51, lows[51]=74
    # Set today's low below 74 to trigger failure
    lows[-1] = 70.0   # below swing_lows[1] low (74)
    # Keep close in upper bin of new range
    highs[-1] = 155.0
    closes[-1] = lows[-1] + (highs[-1] - lows[-1]) * 0.8  # still upper bin
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is False


def test_t6_gate7_rs_line_new_low() -> None:
    """Gate 7: RS today is the lowest in last RS_NO_NEW_LOW_DAYS → False."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    # Make spy[-1] very high so rs_today is the lowest
    spy[-1] = spy[-1] * 5   # SPY surges → rs_today drops to tiny
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is False


# ── T7: data insufficient ─────────────────────────────────────────────────────


def test_t7_insufficient_bars_returns_false() -> None:
    n = SETUP.CAPITULATION_SWING_LOW_LOOKBACK + 1   # one below threshold
    assert _is_capitulation_reversal([100.0]*n, [101.0]*n, [99.0]*n, [1_000_000]*n, [500.0]*n) is False


def test_t7_exactly_threshold_does_not_crash() -> None:
    n = SETUP.CAPITULATION_SWING_LOW_LOOKBACK + 2   # exactly at threshold
    result = _is_capitulation_reversal([100.0]*n, [101.0]*n, [99.0]*n, [1_000_000]*n, [500.0]*n)
    assert isinstance(result, bool)


# ── T8: condition 5 lookahead-safe ───────────────────────────────────────────


def test_t8_condition5_skipped_no_future_bars() -> None:
    """NP2: bar[-1]=today, no future data → condition 5 passes by skip → True (other gates pass)."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    assert _is_capitulation_reversal(closes, highs, lows, vols, spy) is True


def test_t8_condition5_does_not_block_happy_path() -> None:
    """Condition 5 is always skipped: happy path should not be blocked by it."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    # Happy path must return True (condition 5 skip logic doesn't break anything)
    result = _is_capitulation_reversal(closes, highs, lows, vols, spy)
    assert result is True


# ── T9: priority tests ────────────────────────────────────────────────────────


def _cap_mas(last_close: float) -> dict[int, float]:
    """MAs: not broken, not extended (≈3% above MA50)."""
    return {10: last_close + 5, 21: last_close + 3, 50: last_close - 5,
            150: last_close - 20, 200: last_close - 30}


def test_t9_broken_beats_capitulation() -> None:
    closes, highs, lows, vols, spy = _base_cap_inputs()
    last_close = closes[-1]
    # MA150 > close → BROKEN
    mas = {10: last_close+5, 21: last_close+3, 50: last_close+1,
           150: last_close+50, 200: last_close+40}
    with patch("app.services.cockpit.setup_service._is_capitulation_reversal", return_value=True):
        st, *_ = _classify_setup_type(last_close, mas, highs, 5, False, closes[:-1],
                                       lows=lows, volumes=vols, spy_closes=spy)
    assert st == "BROKEN"


def test_t9_extended_beats_capitulation() -> None:
    closes, highs, lows, vols, spy = _base_cap_inputs()
    last_close = closes[-1]
    # MA50 very low → (close-ma50)/ma50 > 15% → EXTENDED
    ma50 = last_close / (1 + SETUP.EXTENDED_MA50_PCT / 100 + 0.05)
    mas = {10: last_close-1, 21: last_close-2, 50: ma50, 150: ma50*0.8, 200: ma50*0.7}
    with patch("app.services.cockpit.setup_service._is_capitulation_reversal", return_value=True):
        st, *_ = _classify_setup_type(last_close, mas, highs, 3, False, closes[:-1],
                                       lows=lows, volumes=vols, spy_closes=spy)
    assert st == "EXTENDED"


def test_t9_earnings_drift_beats_capitulation() -> None:
    closes, highs, lows, vols, spy = _base_cap_inputs()
    last_close = closes[-1]
    mas = _cap_mas(last_close)
    mas[21] = last_close - 1   # close > ma21 → EARNINGS_DRIFT eligible
    with patch("app.services.cockpit.setup_service._is_capitulation_reversal", return_value=True):
        st, *_ = _classify_setup_type(last_close, mas, highs, 4, True, closes[:-1],
                                       lows=lows, volumes=vols, spy_closes=spy)
    assert st == "EARNINGS_DRIFT"


def test_t9_capitulation_beats_breakout() -> None:
    """CAPITULATION (priority 4) fires before BREAKOUT (priority 5)."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    last_close = closes[-1]
    mas = _cap_mas(last_close)
    # Breakout zone: pivot just above close so close is in the 5% zone
    pivot = last_close * 1.01
    highs_bo = [pivot] * len(highs)
    highs_bo[-1] = highs[-1]
    with patch("app.services.cockpit.setup_service._is_capitulation_reversal", return_value=True):
        st, *_ = _classify_setup_type(
            last_close, mas, highs_bo, 4, False, closes[:-1],
            vol_zscore=2.0, ud_ratio=1.5,
            lows=lows, volumes=vols, spy_closes=spy,
        )
    assert st == "CAPITULATION"


def test_t9_capitulation_beats_reclaim() -> None:
    """CAPITULATION (priority 4) fires before RECLAIM (priority 6)."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    last_close = closes[-1]
    ma50 = last_close - 5
    mas = {10: last_close+2, 21: last_close+1, 50: ma50, 150: ma50-15, 200: ma50-25}
    # prev_closes with some below ma50 → RECLAIM gate would fire without CAPITULATION
    prev = [ma50 - 2] * 5 + [ma50 + 1] * (len(closes) - 6)
    with patch("app.services.cockpit.setup_service._is_capitulation_reversal", return_value=True):
        st, *_ = _classify_setup_type(
            last_close, mas, highs, 3, False, prev,
            lows=lows, volumes=vols, spy_closes=spy,
        )
    assert st == "CAPITULATION"


# ── T10: docstring + dead code ────────────────────────────────────────────────


def test_t10_classify_docstring_has_new_priority() -> None:
    doc = _classify_setup_type.__doc__ or ""
    assert "CAPITULATION" in doc
    assert "BROKEN" in doc


def test_t10_no_active_pullback_star_refs() -> None:
    import inspect
    import re
    import app.services.cockpit.setup_service as mod
    src = inspect.getsource(mod)
    # SETUP.PULLBACK_* references must be gone (comments OK but none expected)
    matches = re.findall(r"SETUP\.PULLBACK_\w+", src)
    assert matches == [], f"Found active PULLBACK_* refs: {matches}"


# ── T11: _ACTIONABLE_TYPES ───────────────────────────────────────────────────


def test_t11_actionable_types_correct() -> None:
    assert _ACTIONABLE_TYPES == {"BREAKOUT", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT"}


def test_t11_pullback_not_in_actionable() -> None:
    assert "PULLBACK" not in _ACTIONABLE_TYPES


# ── T12: compute_and_store_all integration ────────────────────────────────────


@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


def _insert_stock(db: Session, ticker: str) -> Stock:
    s = Stock(ticker=ticker, name=f"{ticker} Corp", is_active=True, added_at=datetime.now(timezone.utc))
    db.add(s)
    db.flush()
    return s


def _insert_bars_t12(db: Session, stock_id: int, n: int = 260) -> None:
    for i in range(n):
        db.add(DailyBar(
            stock_id=stock_id,
            date=_START + timedelta(days=i),
            open=100.0, high=102.0, low=98.0,
            close=100.0 + i * 0.2,
            volume=1_000_000,
        ))
    db.flush()


def _insert_spy_t12(db: Session, n: int = 260) -> None:
    for i in range(n):
        db.add(MarketIndex(symbol="SPY", name="SPDR", date=_START + timedelta(days=i), close=400.0 + i * 0.1))
    db.flush()


def _insert_regime(db: Session) -> None:
    import json
    db.add(MarketRegimeSnapshot(
        date=_TODAY, regime="CONSTRUCTIVE", market_score=65,
        spy_trend_score=20, qqq_trend_score=15, iwm_breadth_score=10,
        sector_participation_score=10, risk_appetite_score=5, volatility_stress_score=5,
        allowed_exposure_pct=70.0, single_trade_risk_pct=1.0,
        preferred_setups=json.dumps(["BREAKOUT"]),
        avoid_setups=json.dumps(["EXTENDED"]),
        computed_at=datetime.now(timezone.utc),
    ))
    db.flush()


def test_t12_no_pullback_written(db: Session) -> None:
    """compute_and_store_all must never write setup_type='PULLBACK'."""
    aapl = _insert_stock(db, "AAPL")
    _insert_bars_t12(db, aapl.id)
    _insert_spy_t12(db)
    _insert_regime(db)
    db.commit()
    SetupService(db).compute_and_store_all(today=_TODAY)
    for row in db.execute(select(SetupSnapshot)).scalars().all():
        assert row.setup_type != "PULLBACK", f"PULLBACK written for {row.ticker}"


def test_t12_capitulation_entry_stop_formula(db: Session) -> None:
    """When CAPITULATION fires: entry=close*(1+tick), stop=low*(1-STOP_BUFFER/100)."""
    closes, highs, lows, vols, spy = _base_cap_inputs()
    last_close = closes[-1]
    mas = _cap_mas(last_close)
    with patch("app.services.cockpit.setup_service._is_capitulation_reversal", return_value=True):
        st, entry, stop, t2r, t3r = _classify_setup_type(
            last_close, mas, highs, 4, False, closes[:-1],
            lows=lows, volumes=vols, spy_closes=spy,
        )
    assert st == "CAPITULATION"
    tick = SETUP.ENTRY_TICK_PCT / 100
    assert abs(entry - round(last_close * (1 + tick), 4)) < 1e-6
    assert abs(stop  - round(lows[-1] * (1 - SETUP.CAPITULATION_STOP_BUFFER_PCT / 100), 4)) < 1e-6
    assert t2r > entry and t3r > t2r
