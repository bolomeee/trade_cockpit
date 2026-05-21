"""F216-d2: weekly_stage as 8th ready_signal AND gate.

Standards from Sprint Contract §4 / Evaluator checklist:
  T1   weekly_stage=2 + all 7 conditions met → True
  T2   weekly_stage=None + all 7 met → False (NULL not satisfied)
  T3   weekly_stage=0 (UNKNOWN) → False
  T4   weekly_stage=1 (Base) → False
  T5   weekly_stage=3 (Distribution) → False
  T6   weekly_stage=4 (Declining) → False
  T7   READY_REQUIRE_STAGE2=False → any stage/None does not block (other 7 met → True)
  T8   original 7 any one fails + weekly_stage=2 → still False
  T9   integration: stage_map stage=2 → row.ready_signal=True, row.weekly_stage=2
  T10  integration: stage_map stage=4 → row.ready_signal=False, row.weekly_stage=4
  T11  integration: ticker absent from stage_map → row.ready_signal=False, row.weekly_stage=None
  T12  integration: short-data branch (closes<10) → row.weekly_stage from stage_map
  T13  integration: multi-ticker (A=2, B=3, C=None) → only A ready
  T14  _row_to_dict(row) contains weeklyStage key, value matches row.weekly_stage (int)
  T15  _row_to_dict(row) weeklyStage=None when row.weekly_stage is None
  T16  SetupItemResponse schema: weekly_stage field round-trips via alias weeklyStage
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.orm import Session

import app.services.cockpit.setup_service as svc_mod
from app.models.daily_bar import DailyBar
from app.models.earnings_event import EarningsEvent
from app.models.market_index import MarketIndex
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock
from app.models.weekly_stage_snapshot import WeeklyStageSnapshot
from app.schemas.cockpit.setup import SetupItemResponse
from app.services.cockpit.cockpit_params import SETUP
from app.services.cockpit.setup_service import SetupService, _compute_ready_signal, _row_to_dict

_TODAY = date(2026, 5, 14)
_START = _TODAY - timedelta(days=300)

# ── Pure-function helpers ──────────────────────────────────────────────────────


def _all_conds(weekly_stage: int | None = 2) -> dict:
    """All 8 conditions fully satisfied by default."""
    return dict(
        trend_score=4,
        rs_percentile=75.0,
        setup_quality="A",
        distance_to_entry_pct=2.0,
        reward_risk=2.5,
        earnings_risk="SAFE",
        regime="CONSTRUCTIVE",
        weekly_stage=weekly_stage,
    )


# ── T1-T6: stage value vs gate ────────────────────────────────────────────────


def test_t1_stage2_all_conditions_true() -> None:
    assert _compute_ready_signal(**_all_conds(weekly_stage=2)) is True


def test_t2_stage_none_blocks() -> None:
    assert _compute_ready_signal(**_all_conds(weekly_stage=None)) is False


def test_t3_stage0_unknown_blocks() -> None:
    assert _compute_ready_signal(**_all_conds(weekly_stage=0)) is False


def test_t4_stage1_base_blocks() -> None:
    assert _compute_ready_signal(**_all_conds(weekly_stage=1)) is False


def test_t5_stage3_distribution_blocks() -> None:
    assert _compute_ready_signal(**_all_conds(weekly_stage=3)) is False


def test_t6_stage4_declining_blocks() -> None:
    assert _compute_ready_signal(**_all_conds(weekly_stage=4)) is False


# ── T7: flag off disables gate ────────────────────────────────────────────────


@pytest.mark.parametrize("stage", [None, 0, 1, 3, 4])
def test_t7_flag_off_stage_does_not_block(monkeypatch: pytest.MonkeyPatch, stage: int | None) -> None:
    patched = SETUP.model_copy(update={"READY_REQUIRE_STAGE2": False})
    monkeypatch.setattr(svc_mod, "SETUP", patched)
    assert _compute_ready_signal(**_all_conds(weekly_stage=stage)) is True


# ── T8: stage=2 cannot rescue a failing condition ─────────────────────────────


@pytest.mark.parametrize("override,value", [
    ("trend_score", 3),
    ("rs_percentile", 69.0),
    ("setup_quality", "C"),
    ("distance_to_entry_pct", 4.0),
    ("reward_risk", 1.9),
    ("earnings_risk", "DANGER"),
    ("regime", "RISK_OFF"),
])
def test_t8_stage2_cannot_rescue_failing_condition(override: str, value) -> None:
    kwargs = _all_conds(weekly_stage=2)
    kwargs[override] = value
    assert _compute_ready_signal(**kwargs) is False


# ── Integration helpers ───────────────────────────────────────────────────────


def _insert_stock(db: Session, ticker: str) -> Stock:
    stock = Stock(ticker=ticker, name=f"{ticker} Inc", is_active=True, added_at=datetime.now(timezone.utc))
    db.add(stock)
    db.flush()
    return stock


def _insert_rising_bars(db: Session, stock_id: int, count: int = 260) -> None:
    """260 monotonically rising bars → trend_score=5, EARNINGS_DRIFT setup when earnings present."""
    for i in range(count):
        close = 100.0 + i * 0.5
        db.add(DailyBar(
            stock_id=stock_id,
            date=_START + timedelta(days=i),
            open=close * 0.99,
            high=close * 1.01,
            low=close * 0.98,
            close=close,
            volume=1_000_000,
        ))
    db.flush()


def _insert_flat_bars(db: Session, stock_id: int, price: float = 50.0, count: int = 260) -> None:
    for i in range(count):
        db.add(DailyBar(
            stock_id=stock_id,
            date=_START + timedelta(days=i),
            open=price,
            high=price * 1.005,
            low=price * 0.995,
            close=price,
            volume=1_000_000,
        ))
    db.flush()


def _insert_short_bars(db: Session, stock_id: int, count: int = 5) -> None:
    for i in range(count):
        db.add(DailyBar(
            stock_id=stock_id,
            date=_START + timedelta(days=i),
            open=100.0,
            high=101.0,
            low=99.0,
            close=100.0,
            volume=500_000,
        ))
    db.flush()


def _insert_spy(db: Session, count: int = 260) -> None:
    for i in range(count):
        db.add(MarketIndex(
            symbol="SPY",
            name="SPDR S&P 500",
            date=_START + timedelta(days=i),
            close=400.0 + i * 0.1,
        ))
    db.flush()


def _insert_regime(db: Session) -> None:
    db.add(MarketRegimeSnapshot(
        date=_TODAY,
        regime="CONSTRUCTIVE",
        market_score=65,
        spy_trend_score=20,
        qqq_trend_score=15,
        iwm_breadth_score=10,
        sector_participation_score=10,
        risk_appetite_score=5,
        volatility_stress_score=5,
        allowed_exposure_pct=70.0,
        single_trade_risk_pct=1.0,
        preferred_setups=json.dumps(["BREAKOUT", "CAPITULATION"]),
        avoid_setups=json.dumps(["EXTENDED"]),
        computed_at=datetime.now(timezone.utc),
    ))
    db.flush()


def _insert_past_earnings(db: Session, ticker: str, days_ago: int = 5) -> None:
    """Seed a past earnings event to trigger EARNINGS_DRIFT setup."""
    db.add(EarningsEvent(ticker=ticker, earnings_date=_TODAY - timedelta(days=days_ago)))
    db.flush()


def _insert_stage(db: Session, ticker: str, stage: int, scan_date: date | None = None) -> None:
    db.add(WeeklyStageSnapshot(
        ticker=ticker,
        scan_date=scan_date or _TODAY - timedelta(days=3),
        stage=stage,
    ))
    db.flush()


def _get_row(db: Session, ticker: str) -> SetupSnapshot:
    return db.execute(
        select(SetupSnapshot).where(SetupSnapshot.ticker == ticker)
    ).scalar_one()


# ── T9: stage=2 → ready=True ──────────────────────────────────────────────────


def test_t9_stage2_produces_ready_true(db_session: Session) -> None:
    # 4 stocks: AAPL (high RS), NVDA/MSFT/AMD (low RS) → AAPL gets 75% rs_percentile
    aapl = _insert_stock(db_session, "AAPL")
    nvda = _insert_stock(db_session, "NVDA")
    msft = _insert_stock(db_session, "MSFT")
    amd = _insert_stock(db_session, "AMD")
    _insert_rising_bars(db_session, aapl.id)
    _insert_flat_bars(db_session, nvda.id)
    _insert_flat_bars(db_session, msft.id)
    _insert_flat_bars(db_session, amd.id)
    _insert_past_earnings(db_session, "AAPL")
    _insert_spy(db_session)
    _insert_regime(db_session)
    _insert_stage(db_session, "AAPL", stage=2)
    db_session.commit()

    svc = SetupService(db_session)
    svc.compute_and_store_all(today=_TODAY)

    row = _get_row(db_session, "AAPL")
    assert row.weekly_stage == 2
    assert row.ready_signal is True


# ── T10: stage=4 → ready=False ───────────────────────────────────────────────


def test_t10_stage4_produces_ready_false(db_session: Session) -> None:
    aapl = _insert_stock(db_session, "AAPL")
    nvda = _insert_stock(db_session, "NVDA")
    msft = _insert_stock(db_session, "MSFT")
    amd = _insert_stock(db_session, "AMD")
    _insert_rising_bars(db_session, aapl.id)
    _insert_flat_bars(db_session, nvda.id)
    _insert_flat_bars(db_session, msft.id)
    _insert_flat_bars(db_session, amd.id)
    _insert_past_earnings(db_session, "AAPL")
    _insert_spy(db_session)
    _insert_regime(db_session)
    _insert_stage(db_session, "AAPL", stage=4)
    db_session.commit()

    svc = SetupService(db_session)
    svc.compute_and_store_all(today=_TODAY)

    row = _get_row(db_session, "AAPL")
    assert row.weekly_stage == 4
    assert row.ready_signal is False


# ── T11: no stage_map entry → weekly_stage=None, ready=False ──────────────────


def test_t11_no_stage_entry_produces_none_and_false(db_session: Session) -> None:
    aapl = _insert_stock(db_session, "AAPL")
    nvda = _insert_stock(db_session, "NVDA")
    msft = _insert_stock(db_session, "MSFT")
    amd = _insert_stock(db_session, "AMD")
    _insert_rising_bars(db_session, aapl.id)
    _insert_flat_bars(db_session, nvda.id)
    _insert_flat_bars(db_session, msft.id)
    _insert_flat_bars(db_session, amd.id)
    _insert_past_earnings(db_session, "AAPL")
    _insert_spy(db_session)
    _insert_regime(db_session)
    # No WeeklyStageSnapshot for AAPL
    db_session.commit()

    svc = SetupService(db_session)
    svc.compute_and_store_all(today=_TODAY)

    row = _get_row(db_session, "AAPL")
    assert row.weekly_stage is None
    assert row.ready_signal is False


# ── T12: short data branch still writes weekly_stage ──────────────────────────


def test_t12_short_data_branch_writes_weekly_stage(db_session: Session) -> None:
    short = _insert_stock(db_session, "SHORT")
    _insert_short_bars(db_session, short.id, count=5)
    _insert_spy(db_session)
    _insert_regime(db_session)
    _insert_stage(db_session, "SHORT", stage=2)
    db_session.commit()

    svc = SetupService(db_session)
    svc.compute_and_store_all(today=_TODAY)

    row = _get_row(db_session, "SHORT")
    assert row.setup_type == "NONE"
    assert row.ready_signal is False  # short data → always False
    assert row.weekly_stage == 2  # stage_map value written even in short branch


def test_t12_short_data_no_stage_writes_none(db_session: Session) -> None:
    short = _insert_stock(db_session, "SHORT")
    _insert_short_bars(db_session, short.id, count=5)
    _insert_spy(db_session)
    _insert_regime(db_session)
    # No stage entry for SHORT
    db_session.commit()

    svc = SetupService(db_session)
    svc.compute_and_store_all(today=_TODAY)

    row = _get_row(db_session, "SHORT")
    assert row.weekly_stage is None


# ── T13: multi-ticker — only stage=2 stock ready ─────────────────────────────


def _insert_rising_bars_step(db: Session, stock_id: int, step: float, count: int = 260) -> None:
    """Rising bars with custom step — used to give stocks distinct RS ratios."""
    for i in range(count):
        close = 100.0 + i * step
        db.add(DailyBar(
            stock_id=stock_id,
            date=_START + timedelta(days=i),
            open=close * 0.99,
            high=close * 1.01,
            low=close * 0.98,
            close=close,
            volume=1_000_000,
        ))
    db.flush()


def test_t13_multi_ticker_only_stage2_ready(db_session: Session) -> None:
    # AAA has strictly highest RS; BBB and CCC are below AAA, above DDD/EEE.
    # _percentile_rank uses strict < so all stocks must be at different RS levels.
    # With 5 stocks and AAA at position 4 (0-indexed), percentile = 4/5*100 = 80% >= 70.
    stock_a = _insert_stock(db_session, "AAA")
    stock_b = _insert_stock(db_session, "BBB")
    stock_c = _insert_stock(db_session, "CCC")
    stock_d = _insert_stock(db_session, "DDD")
    stock_e = _insert_stock(db_session, "EEE")

    _insert_rising_bars_step(db_session, stock_a.id, step=0.50)  # return ≈130%, RS≈10.4
    _insert_rising_bars_step(db_session, stock_b.id, step=0.30)  # return ≈78%, RS≈6.2
    _insert_rising_bars_step(db_session, stock_c.id, step=0.15)  # return ≈39%, RS≈3.1
    _insert_flat_bars(db_session, stock_d.id, price=50.0)        # return=0%, RS=0
    _insert_flat_bars(db_session, stock_e.id, price=50.0)        # return=0%, RS=0

    # Past earnings trigger EARNINGS_DRIFT for rising stocks (close > MA21)
    _insert_past_earnings(db_session, "AAA")
    _insert_past_earnings(db_session, "BBB")
    _insert_past_earnings(db_session, "CCC")

    _insert_spy(db_session)
    _insert_regime(db_session)

    _insert_stage(db_session, "AAA", stage=2)
    _insert_stage(db_session, "BBB", stage=3)
    # No stage for CCC

    db_session.commit()

    svc = SetupService(db_session)
    svc.compute_and_store_all(today=_TODAY)

    row_a = _get_row(db_session, "AAA")
    row_b = _get_row(db_session, "BBB")
    row_c = _get_row(db_session, "CCC")

    assert row_a.weekly_stage == 2
    assert row_b.weekly_stage == 3
    assert row_c.weekly_stage is None

    # AAA: rs_percentile=80%>=70, stage=2 passes gate → ready=True
    assert row_a.ready_signal is True
    # BBB: stage=3 blocks even if other conditions met → ready=False
    assert row_b.ready_signal is False
    # CCC: no stage (None) blocks → ready=False
    assert row_c.ready_signal is False


# ── T14/T15: _row_to_dict ─────────────────────────────────────────────────────


class _FakeRow:
    """Minimal ORM-row stub for _row_to_dict."""
    ticker = "TEST"
    setup_type = "BREAKOUT"
    setup_quality = "A"
    entry_price = 100.0
    stop_price = 95.0
    target_2r = 110.0
    target_3r = 115.0
    distance_to_entry_pct = 1.0
    reward_risk = 2.0
    rs_percentile = 80.0
    volume_status = "HIGH"
    trend_score = 4
    earnings_risk = "SAFE"
    ready_signal = True
    suggested_action = "enter"
    scan_date = _TODAY
    volume_zscore = 1.5
    obv_trend = "UP"
    up_down_volume_ratio = 1.3
    weekly_stage: int | None = None
    macd_divergence: str | None = None


def test_t14_row_to_dict_includes_weekly_stage_int() -> None:
    row = _FakeRow()
    row.weekly_stage = 2
    d = _row_to_dict(row)
    assert "weeklyStage" in d
    assert d["weeklyStage"] == 2


def test_t15_row_to_dict_weekly_stage_none() -> None:
    row = _FakeRow()
    row.weekly_stage = None
    d = _row_to_dict(row)
    assert "weeklyStage" in d
    assert d["weeklyStage"] is None


# ── T16: SetupItemResponse schema ─────────────────────────────────────────────

_ITEM_REQUIRED = dict(
    ticker="TEST",
    stock_name=None,
    setup_type="BREAKOUT",
    setup_quality="A",
    entry_price=100.0,
    stop_price=95.0,
    target2r=110.0,
    target3r=115.0,
    distance_to_entry_pct=1.0,
    reward_risk=2.0,
    rs_percentile=80.0,
    volume_status="HIGH",
    trend_score=4,
    earnings_risk="SAFE",
    ready_signal=True,
    suggested_action="enter",
    scan_date="2026-05-14",
)


def test_t16_schema_weekly_stage_alias() -> None:
    resp = SetupItemResponse(**_ITEM_REQUIRED, weekly_stage=2)
    by_alias = resp.model_dump(by_alias=True)
    assert "weeklyStage" in by_alias
    assert by_alias["weeklyStage"] == 2


def test_t16_schema_weekly_stage_none_default() -> None:
    resp = SetupItemResponse(**_ITEM_REQUIRED)
    by_alias = resp.model_dump(by_alias=True)
    assert by_alias["weeklyStage"] is None
