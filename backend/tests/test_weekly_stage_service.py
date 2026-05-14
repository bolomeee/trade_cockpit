"""F216-b tests — WeeklyStageService: classify (standards 1-7) + repo + integration (8-13)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.services.cockpit.weekly_stage_service import (
    STAGE_1,
    STAGE_2,
    STAGE_3,
    STAGE_4,
    STAGE_UNKNOWN,
    WeeklyStageResult,
    WeeklyStageService,
)


# ── Fixtures / helpers ────────────────────────────────────────────────────────

def _make_bars(n: int, close: float = 100.0) -> list[dict]:
    base = date(2024, 1, 1)
    return [
        {"date": base + timedelta(weeks=i), "open": close, "high": close, "low": close, "close": close, "volume": 1000}
        for i in range(n)
    ]


def _make_ma_series(values: list[float], start: date | None = None) -> list[dict]:
    """Build MA series [{"date": ..., "value": float}] aligned with weekly_bars dates."""
    base = start or date(2024, 1, 1)
    return [{"date": base + timedelta(weeks=i), "value": v} for i, v in enumerate(values)]


def _svc(db_session) -> WeeklyStageService:
    return WeeklyStageService(db_session)


# ── Standard 1: insufficient weekly_bars → UNKNOWN ───────────────────────────

def test_classify_empty_bars_returns_unknown(db_session):
    svc = _svc(db_session)
    result = svc.classify([], [], [], [])
    assert result.stage == STAGE_UNKNOWN
    assert result.weekly_close is None
    assert result.slope_30w is None


def test_classify_29_bars_returns_unknown(db_session):
    svc = _svc(db_session)
    bars = _make_bars(29, close=150.0)
    result = svc.classify(bars, [], [], [])
    assert result.stage == STAGE_UNKNOWN


# ── Standard 2: Stage 2 fixture ──────────────────────────────────────────────

def test_classify_stage2(db_session):
    """30wMA monotone up (slope>0.5%), close>ma30, ma10>ma30 → Stage 2."""
    svc = _svc(db_session)
    n = 35
    # 30wMA: 100 → 134 (monotone up, +1/week)
    ma30_values = [100.0 + i for i in range(n)]
    ma30_series = _make_ma_series(ma30_values)
    # close=140 > ma30[-1]=134; ma10=138 > ma30=134
    bars = _make_bars(n, close=140.0)
    ma10_series = _make_ma_series([138.0] * n)
    ma40_series = _make_ma_series([90.0] * n)

    result = svc.classify(bars, ma10_series, ma30_series, ma40_series)
    assert result.stage == STAGE_2


# ── Standard 3: Stage 4 fixture ──────────────────────────────────────────────

def test_classify_stage4(db_session):
    """30wMA monotone down (slope<-0.5%), close<ma30 → Stage 4."""
    svc = _svc(db_session)
    n = 35
    ma30_values = [110.0 - i for i in range(n)]  # 110 → 76, declining
    ma30_series = _make_ma_series(ma30_values)
    bars = _make_bars(n, close=60.0)   # close=60 < ma30[-1]=76
    result = svc.classify(bars, [], ma30_series, [])
    assert result.stage == STAGE_4


# ── Standard 4: Stage 1 fixture ──────────────────────────────────────────────

def test_classify_stage1(db_session):
    """30wMA flat (|slope|≤2%), close within ±3% of 30wMA → Stage 1."""
    svc = _svc(db_session)
    n = 35
    ma30_values = [100.0] * n           # perfectly flat → slope=0
    ma30_series = _make_ma_series(ma30_values)
    bars = _make_bars(n, close=101.0)   # |101-100|/100 = 1% ≤ 3%
    result = svc.classify(bars, [], ma30_series, [])
    assert result.stage == STAGE_1


# ── Standard 5: Stage 3 fixture ──────────────────────────────────────────────

def test_classify_stage3(db_session):
    """30wMA flat + ≥3 crossings of 30wMA in last 10 weeks → Stage 3."""
    svc = _svc(db_session)
    n = 35
    ma30_values = [100.0] * n           # flat → slope=0
    base_date = date(2024, 1, 1)
    ma30_series = _make_ma_series(ma30_values, start=base_date)

    # Build bars: first 25 bars at close=100 (no crossings); last 10 alternate 101/99 → 9 crossings
    bars: list[dict] = []
    early_close = 100.0
    for i in range(25):
        bars.append({
            "date": base_date + timedelta(weeks=i),
            "open": early_close, "high": early_close, "low": early_close,
            "close": early_close, "volume": 1000,
        })
    crossing_closes = [101.0, 99.0, 101.0, 99.0, 101.0, 99.0, 101.0, 99.0, 101.0, 99.0]
    for i, cl in enumerate(crossing_closes):
        bars.append({
            "date": base_date + timedelta(weeks=25 + i),
            "open": cl, "high": cl, "low": cl, "close": cl, "volume": 1000,
        })

    # close is currently 99 < ma30=100: not Stage 1 (|99-100|/100=1% ≤ 3%)
    # Hmm, this might match Stage 1 too. I need |close-ma30|/ma30 > 3% OR slope that disqualifies.
    # The close is 99. |99-100|/100 = 1% ≤ 3% → Stage 1 would match first.
    # Priority: Stage 2, Stage 4, Stage 1, Stage 3.
    # Since slope=0 and close=99 < 100 (ma30), Stage 2 requires close>ma30 → no.
    # Stage 4 requires slope < -0.5% → no (slope=0).
    # Stage 1: |slope|≤2% ✓ AND |close-ma30|/ma30 ≤ 3%? 1% ✓ → would return Stage 1!
    # Need to make close far from ma30 to avoid Stage 1, but still cross it.
    # Solution: use a wider oscillation: 108 / 92 → |108-100|/100=8% > 3% ✓
    # But then |92-100|/100=8% > 3% also, so Stage 1 won't trigger.
    bars_wide: list[dict] = []
    for i in range(25):
        bars_wide.append({
            "date": base_date + timedelta(weeks=i),
            "open": 100.0, "high": 100.0, "low": 100.0, "close": 100.0, "volume": 1000,
        })
    crossing_closes_wide = [108.0, 92.0, 108.0, 92.0, 108.0, 92.0, 108.0, 92.0, 108.0, 92.0]
    for i, cl in enumerate(crossing_closes_wide):
        bars_wide.append({
            "date": base_date + timedelta(weeks=25 + i),
            "open": cl, "high": cl, "low": cl, "close": cl, "volume": 1000,
        })

    result = svc.classify(bars_wide, [], ma30_series, [])
    assert result.stage == STAGE_3


# ── Standard 6: UNKNOWN fallback ─────────────────────────────────────────────

def test_classify_unknown_fallback(db_session):
    """close>ma30 but slope≈0 (not Stage 2) + not Stage 1 price band + no crossings → UNKNOWN."""
    svc = _svc(db_session)
    n = 35
    ma30_values = [100.0] * n           # flat, slope=0
    ma30_series = _make_ma_series(ma30_values)
    # close=106: |106-100|/100=6% > 3% (Stage 1 price band fails)
    # slope=0 → no Stage 2 (requires slope>0.5%), no Stage 4
    # All bars above ma30 → 0 crossings → Stage 3 fails
    bars = _make_bars(n, close=106.0)
    result = svc.classify(bars, [], ma30_series, [])
    assert result.stage == STAGE_UNKNOWN


# ── Standard 7: _compute_slope_30w ───────────────────────────────────────────

def test_slope_insufficient_data_returns_none(db_session):
    """len(ma_series) < SLOPE_LOOKBACK_WEEKS+1 → None."""
    svc = _svc(db_session)
    # SLOPE_LOOKBACK_WEEKS=5 → needs ≥6 points; give only 5
    short_series = _make_ma_series([100.0] * 5)
    assert svc._compute_slope_30w(short_series) is None


def test_slope_monotone_up_returns_positive(db_session):
    """Monotone +1/week 30wMA → slope_30w > 0."""
    svc = _svc(db_session)
    # 35 points: 100, 101, ..., 134; last 6 = [129,130,131,132,133,134], mean=131.5
    # beta=1.0, slope = 1.0/131.5*100 ≈ 0.76%
    values = [100.0 + i for i in range(35)]
    series = _make_ma_series(values)
    slope = svc._compute_slope_30w(series)
    assert slope is not None
    assert slope > 0


def test_slope_monotone_down_returns_negative(db_session):
    """Monotone -1/week 30wMA → slope_30w < 0."""
    svc = _svc(db_session)
    values = [110.0 - i for i in range(35)]
    series = _make_ma_series(values)
    slope = svc._compute_slope_30w(series)
    assert slope is not None
    assert slope < 0


def test_slope_constant_returns_zero(db_session):
    """Constant 30wMA → slope_30w == 0.0."""
    svc = _svc(db_session)
    values = [100.0] * 35
    series = _make_ma_series(values)
    slope = svc._compute_slope_30w(series)
    assert slope is not None
    assert abs(slope) < 1e-9


# ── Standard 8: repo upsert idempotency ──────────────────────────────────────

def test_repo_upsert_updates_existing_row(db_session):
    """Same (ticker, scan_date) → second upsert updates, does not insert new row."""
    from app.repositories.weekly_stage_repository import WeeklyStageRepository
    from app.models.weekly_stage_snapshot import WeeklyStageSnapshot
    from sqlalchemy import select

    repo = WeeklyStageRepository(db_session)
    payload = {
        "ticker": "AAPL",
        "scan_date": date(2024, 6, 28),
        "stage": STAGE_2,
        "weekly_close": 195.0,
        "weekly_ma_10": 190.0,
        "weekly_ma_30": 185.0,
        "weekly_ma_40": 180.0,
        "slope_30w": 0.8,
        "computed_at": datetime.now(timezone.utc),
    }
    repo.upsert(payload)
    # Second upsert with updated stage
    payload["stage"] = STAGE_1
    payload["weekly_close"] = 186.0
    repo.upsert(payload)

    rows = db_session.execute(
        select(WeeklyStageSnapshot)
        .where(WeeklyStageSnapshot.ticker == "AAPL")
    ).scalars().all()
    assert len(rows) == 1
    assert rows[0].stage == STAGE_1
    assert rows[0].weekly_close == pytest.approx(186.0)


# ── Standard 9: get_latest_for_tickers ───────────────────────────────────────

def test_repo_get_latest_for_tickers_missing_silently_omitted(db_session):
    """Missing ticker not in result dict; no exception raised."""
    from app.repositories.weekly_stage_repository import WeeklyStageRepository

    repo = WeeklyStageRepository(db_session)
    # Insert only AAPL
    repo.upsert({
        "ticker": "AAPL",
        "scan_date": date(2024, 6, 28),
        "stage": STAGE_2,
        "weekly_close": 195.0,
        "weekly_ma_10": None, "weekly_ma_30": None, "weekly_ma_40": None,
        "slope_30w": None,
        "computed_at": datetime.now(timezone.utc),
    })
    result = repo.get_latest_for_tickers(["AAPL", "NVDA"])
    assert "AAPL" in result
    assert "NVDA" not in result
    assert result["AAPL"].stage == STAGE_2


# ── Standard 10: compute_for_ticker NOT_FOUND ────────────────────────────────

def test_compute_for_ticker_not_found_raises(db_session):
    """Unknown ticker → APIError NOT_FOUND."""
    from app.services.watchlist_service import APIError

    svc = _svc(db_session)
    with pytest.raises(APIError) as exc_info:
        svc.compute_for_ticker("ZZZZZZ")
    assert exc_info.value.code == "NOT_FOUND"


# ── Standard 11: data insufficient → UNKNOWN snapshot ────────────────────────

def test_compute_for_ticker_insufficient_data_writes_unknown(db_session):
    """< 30 weekly bars → stage=UNKNOWN written; numeric fields null."""
    from app.models import Stock, DailyBar

    # Seed a stock
    stock = Stock(ticker="TSTX", name="Test Corp", is_active=True)
    db_session.add(stock)
    db_session.flush()

    # Add only ~10 weeks of daily bars (50 days)
    for i in range(50):
        db_session.add(DailyBar(
            stock_id=stock.id,
            date=date(2024, 1, 2) + timedelta(days=i),
            open=100.0, high=101.0, low=99.0, close=100.0, volume=1000,
        ))
    db_session.commit()

    svc = _svc(db_session)
    snapshot = svc.compute_for_ticker("TSTX")
    assert snapshot.stage == STAGE_UNKNOWN
    assert snapshot.weekly_close is None
    assert snapshot.slope_30w is None


# ── Standard 12: compute_and_store_all ───────────────────────────────────────

def test_compute_and_store_all_returns_stage_counts(db_session):
    """compute_and_store_all with 3 mock active stocks → returns count dict."""
    from app.models import Stock

    for ticker in ["AA1", "AA2", "AA3"]:
        db_session.add(Stock(ticker=ticker, name=f"{ticker} Corp", is_active=True))
    db_session.commit()

    svc = _svc(db_session)
    # Stocks have no bars → all UNKNOWN
    counts = svc.compute_and_store_all(scan_date=date(2024, 6, 28))
    total = sum(counts.values())
    assert total == 3
    # All should be UNKNOWN (no bars)
    assert counts.get(STAGE_UNKNOWN, 0) == 3


# ── Standard 13: alembic migration up/down ───────────────────────────────────

def test_alembic_019_upgrade_and_downgrade():
    """019 migration creates table + unique constraint; downgrade removes it."""
    import os
    import shutil
    import sqlite3
    import tempfile
    from alembic.config import Config
    from alembic import command

    tmp = tempfile.mkdtemp()
    db_path = os.path.join(tmp, "test_019.db")
    ini_path = os.path.join(os.path.dirname(__file__), "..", "alembic.ini")
    cfg = Config(os.path.abspath(ini_path))
    cfg.set_main_option("sqlalchemy.url", f"sqlite:///{db_path}")
    try:
        command.upgrade(cfg, "019_f216b_weekly_stage_snapshots")

        conn = sqlite3.connect(db_path)
        tables = {r[0] for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "weekly_stage_snapshots" in tables, f"table missing; tables={tables}"

        cols = {r[1] for r in conn.execute("PRAGMA table_info(weekly_stage_snapshots)").fetchall()}
        assert {"id", "ticker", "scan_date", "stage", "weekly_close", "slope_30w"} <= cols
        conn.close()

        command.downgrade(cfg, "018_f215b_setup_volume_accumulation")
        conn2 = sqlite3.connect(db_path)
        tables_after = {r[0] for r in conn2.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()}
        assert "weekly_stage_snapshots" not in tables_after, f"table still present; tables={tables_after}"
        conn2.close()
    finally:
        shutil.rmtree(tmp, ignore_errors=True)
