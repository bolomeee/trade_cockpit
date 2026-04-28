"""Unit tests for PoolService (F205-e) and PoolCacheService (F205-e).

PoolService tests (adapted from F205-c):
  Cache-based fixtures replace FMP mocks — cockpit_pool_cache rows are seeded directly.
  #8  rsPercentileMin filter
  #9  revenueGrowthYoyMin + fail-open on None
  #10  trend cap → POOL_TREND_CAP, market_cap desc
  #10c ticker not in cache → excluded from RS layer
  #16  distanceTo50maPct = compute_distance_to_50ma_pct(last_close, ma50)
  #17  ticker with no cache row → excluded at RS layer
  #18  revenue_growth_yoy=None in cache → fail-open (passes fundamental)
  cache_miss  empty cockpit_pool_cache → empty funnel + WARN log

PoolCacheService tests (new in F205-e):
  rebuild_normal        writes correct number of rows
  rebuild_replace       DELETE old rows → INSERT new (transactional replace)
  rebuild_bars_failure  single-ticker bars failure → ticker excluded, rest succeed
  rebuild_growth_null   financial-growth missing → revenue_growth_yoy=null (fail-open)
  rebuild_no_trend      no trend snapshot → 0 upserted, no crash
  rebuild_rs_correct    rs_percentile values ordered correctly
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock, patch

import pytest
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models import Base
from app.models.cockpit_pool_cache import CockpitPoolCache
from app.models.market_breakout_scan import MarketBreakoutScan
from app.models.market_scan_universe import MarketScanUniverse
from app.services.cockpit.pool_cache_service import PoolCacheService
from app.services.cockpit.pool_service import POOL_TREND_CAP, PoolParams, PoolService


# ── fixtures ──────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def fmp():
    return FmpClient.__new__(FmpClient)


def _make_service(db: Session, fmp: FmpClient) -> PoolService:
    return PoolService(db=db, fmp=fmp)


# ── seed helpers ──────────────────────────────────────────────────────────────

def _insert_universe(db: Session, tickers_caps: list[tuple[str, int]]) -> None:
    now = datetime.now(timezone.utc)
    for ticker, cap in tickers_caps:
        db.add(MarketScanUniverse(
            ticker=ticker,
            company_name=f"{ticker} Corp",
            exchange="NASDAQ",
            market_cap=cap,
            last_price=50.0,
            last_volume=1_000_000,
            last_seen_at=now,
            added_at=now,
        ))
    db.commit()


def _insert_breakout(db: Session, tickers: list[str]) -> None:
    scan_date = date(2026, 4, 27)
    now = datetime.now(timezone.utc)
    for ticker in tickers:
        db.add(MarketBreakoutScan(
            scan_date=scan_date,
            ticker=ticker,
            company_name=f"{ticker} Corp",
            signal_type="BREAKOUT",
            close_price=50.0,
            ma150_value=45.0,
            pct_above_ma150=11.0,
            slope_value=0.5,
            market_cap=1_000_000_000,
            scanned_at=now,
        ))
    db.commit()


def _insert_cache(
    db: Session,
    rows: list[dict],
) -> None:
    """Seed cockpit_pool_cache rows; any omitted field defaults to a safe value."""
    now = datetime.now(timezone.utc)
    for row in rows:
        db.add(CockpitPoolCache(
            ticker=row["ticker"],
            rs_percentile=row.get("rs_percentile", 50.0),
            ma50=row.get("ma50", 100.0),
            last_close=row.get("last_close", 100.0),
            revenue_growth_yoy=row.get("revenue_growth_yoy", 20.0),
            computed_at=row.get("computed_at", now),
        ))
    db.commit()


_BAR_START = date(2023, 1, 1)


def _make_bars(n: int = 260, base: float = 100.0, final: float | None = None) -> list[dict]:
    bars = []
    for i in range(n):
        d = (_BAR_START + timedelta(days=i)).isoformat()
        close = base if final is None or i < n - 1 else final
        bars.append({"date": d, "close": close})
    return bars


# ═══════════════════════════════════════════════════════════════════════════════
# PoolService tests (cache-based)
# ═══════════════════════════════════════════════════════════════════════════════

def test_rs_percentile_min_filters_low_rank(db: Session, fmp: FmpClient):
    """#8: rsPercentileMin=80 → only tickers with rs_percentile ≥ 80 pass."""
    _insert_universe(db, [("AAA", 100_000_000_000), ("BBB", 100_000_000_000), ("CCC", 100_000_000_000)])
    _insert_breakout(db, ["AAA", "BBB", "CCC"])
    _insert_cache(db, [
        {"ticker": "AAA", "rs_percentile": 90.0, "revenue_growth_yoy": 20.0},
        {"ticker": "BBB", "rs_percentile": 50.0, "revenue_growth_yoy": 20.0},
        {"ticker": "CCC", "rs_percentile": 20.0, "revenue_growth_yoy": 20.0},
    ])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=80.0, revenue_growth_yoy_min=0.0))

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "AAA" in item_tickers
    assert "CCC" not in item_tickers
    assert result["funnel"]["rs"] <= result["funnel"]["trend"]


def test_revenue_growth_min_filters_low_growth(db: Session, fmp: FmpClient):
    """#9a: revenueGrowthYoyMin=15.0 → ticker with 10% growth is excluded."""
    _insert_universe(db, [("HIGH", 100_000_000_000), ("LOW", 100_000_000_000)])
    _insert_breakout(db, ["HIGH", "LOW"])
    _insert_cache(db, [
        {"ticker": "HIGH", "rs_percentile": 90.0, "revenue_growth_yoy": 20.0},
        {"ticker": "LOW",  "rs_percentile": 90.0, "revenue_growth_yoy": 10.0},
    ])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=15.0))

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "HIGH" in item_tickers
    assert "LOW" not in item_tickers


def test_revenue_growth_none_fail_open(db: Session, fmp: FmpClient):
    """#9b: revenue_growth_yoy=null in cache → ticker passes fundamental (fail-open D079)."""
    _insert_universe(db, [("NODATA", 100_000_000_000)])
    _insert_breakout(db, ["NODATA"])
    _insert_cache(db, [{"ticker": "NODATA", "rs_percentile": 90.0, "revenue_growth_yoy": None}])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=50.0))

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "NODATA" in item_tickers
    assert result["items"][0]["revenue_growth_yoy"] is None


def test_trend_cap_truncates_to_200_by_market_cap(db: Session, fmp: FmpClient):
    """#10: trend subset > POOL_TREND_CAP → cap to 200 by market_cap desc."""
    n_tickers = POOL_TREND_CAP + 20  # 220
    tickers_caps = [(f"T{i:03d}", (1000 - i) * 1_000_000_000) for i in range(n_tickers)]
    _insert_universe(db, tickers_caps)
    _insert_breakout(db, [t for t, _ in tickers_caps])
    _insert_cache(db, [
        {"ticker": t, "rs_percentile": 90.0, "revenue_growth_yoy": 20.0}
        for t, _ in tickers_caps
    ])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0, limit=200))

    assert result["funnel"]["trend"] == POOL_TREND_CAP
    item_tickers = {i["ticker"] for i in result["items"]}
    assert "T000" in item_tickers
    assert "T200" not in item_tickers


def test_ticker_not_in_cache_excluded_from_rs(db: Session, fmp: FmpClient):
    """#10c: trend ticker with no cache entry is excluded from rs layer."""
    _insert_universe(db, [("GOOD", 100_000_000_000), ("NOCACHE", 100_000_000_000)])
    _insert_breakout(db, ["GOOD", "NOCACHE"])
    _insert_cache(db, [{"ticker": "GOOD", "rs_percentile": 90.0, "revenue_growth_yoy": 20.0}])
    # NOCACHE has no cache row

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0))

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "GOOD" in item_tickers
    assert "NOCACHE" not in item_tickers


def test_distance_to_50ma_pct_computed_correctly(db: Session, fmp: FmpClient):
    """#16: distanceTo50maPct = compute_distance_to_50ma_pct(last_close, ma50) from cache."""
    _insert_universe(db, [("MA50", 100_000_000_000)])
    _insert_breakout(db, ["MA50"])
    # last_close == ma50 → distance = 0%
    _insert_cache(db, [{"ticker": "MA50", "rs_percentile": 90.0, "last_close": 50.0, "ma50": 50.0}])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0))

    assert result["items"]
    item = next(i for i in result["items"] if i["ticker"] == "MA50")
    assert item["distance_to_50ma_pct"] == pytest.approx(0.0, abs=1e-4)


def test_distance_to_50ma_pct_above_ma(db: Session, fmp: FmpClient):
    """#16b: close 10% above ma50 → distanceTo50maPct ≈ 10.0."""
    _insert_universe(db, [("ABOVE", 100_000_000_000)])
    _insert_breakout(db, ["ABOVE"])
    _insert_cache(db, [{"ticker": "ABOVE", "rs_percentile": 90.0, "last_close": 110.0, "ma50": 100.0}])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0))

    item = next((i for i in result["items"] if i["ticker"] == "ABOVE"), None)
    assert item is not None
    assert item["distance_to_50ma_pct"] == pytest.approx(10.0, abs=0.01)


def test_fmp_bars_exception_skips_ticker_at_rs_layer(db: Session, fmp: FmpClient):
    """#17: ticker not in cache (bars would have failed) → excluded; others succeed."""
    _insert_universe(db, [("ERRX", 100_000_000_000), ("GOOD", 100_000_000_000)])
    _insert_breakout(db, ["ERRX", "GOOD"])
    _insert_cache(db, [{"ticker": "GOOD", "rs_percentile": 80.0, "revenue_growth_yoy": 20.0}])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=60.0, revenue_growth_yoy_min=0.0))

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "GOOD" in item_tickers
    assert "ERRX" not in item_tickers


def test_financial_growth_none_passes_fundamental(db: Session, fmp: FmpClient):
    """#18: revenue_growth_yoy=null → fail-open (ticker passes fundamental layer)."""
    _insert_universe(db, [("NOFUND", 100_000_000_000)])
    _insert_breakout(db, ["NOFUND"])
    _insert_cache(db, [{"ticker": "NOFUND", "rs_percentile": 90.0, "revenue_growth_yoy": None}])

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=99.0))

    assert result["funnel"]["fundamental"] == 1
    assert any(i["ticker"] == "NOFUND" for i in result["items"])


def test_cache_miss_returns_empty_funnel_with_warn_log(db: Session, fmp: FmpClient):
    """cache_miss: cockpit_pool_cache empty → rs=0, fundamental=0, action=0 + WARN log (Q3=A)."""
    _insert_universe(db, [("AAA", 100_000_000_000)])
    _insert_breakout(db, ["AAA"])
    # no cache rows inserted

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0))

    assert result["funnel"]["rs"] == 0
    assert result["funnel"]["fundamental"] == 0
    assert result["funnel"]["action"] == 0
    assert result["items"] == []
    assert result["funnel"]["tradable"] >= 1
    assert result["funnel"]["trend"] >= 1


def test_pool_service_does_not_call_fmp(db: Session, fmp: FmpClient):
    """PoolService must not call FmpClient.get_daily_bars or get_financial_growth."""
    _insert_universe(db, [("AAA", 100_000_000_000)])
    _insert_breakout(db, ["AAA"])
    _insert_cache(db, [{"ticker": "AAA", "rs_percentile": 90.0, "revenue_growth_yoy": 20.0}])

    fmp.get_daily_bars = MagicMock(side_effect=AssertionError("must not call FMP bars"))
    fmp.get_financial_growth = MagicMock(side_effect=AssertionError("must not call FMP growth"))

    svc = _make_service(db, fmp)
    result = svc.get_pool(PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0))

    fmp.get_daily_bars.assert_not_called()
    fmp.get_financial_growth.assert_not_called()
    assert result["funnel"]["rs"] >= 1


# ═══════════════════════════════════════════════════════════════════════════════
# PoolCacheService tests
# ═══════════════════════════════════════════════════════════════════════════════

def test_pool_cache_rebuild_writes_correct_row_count(db: Session, fmp: FmpClient):
    """rebuild_normal: N trend tickers → N rows in cockpit_pool_cache."""
    _insert_breakout(db, ["AAA", "BBB", "CCC"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    stock_bars = _make_bars(260, base=100.0, final=120.0)

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.2}):
        result = PoolCacheService(db, fmp).rebuild()

    assert result.status == "ok"
    assert result.upserted == 3
    rows = db.execute(select(CockpitPoolCache)).scalars().all()
    assert len(rows) == 3
    assert {r.ticker for r in rows} == {"AAA", "BBB", "CCC"}


def test_pool_cache_rebuild_replaces_old_rows(db: Session, fmp: FmpClient):
    """rebuild_replace: old cache rows are deleted before new rows are inserted."""
    # Seed stale rows for STALE ticker
    now = datetime.now(timezone.utc)
    db.add(CockpitPoolCache(
        ticker="STALE", rs_percentile=99.0, ma50=50.0,
        last_close=50.0, revenue_growth_yoy=5.0, computed_at=now,
    ))
    db.commit()

    _insert_breakout(db, ["NEW1", "NEW2"])
    spy_bars = _make_bars(260, base=100.0, final=110.0)
    stock_bars = _make_bars(260, base=100.0, final=120.0)

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.2}):
        result = PoolCacheService(db, fmp).rebuild()

    assert result.status == "ok"
    rows = db.execute(select(CockpitPoolCache)).scalars().all()
    tickers = {r.ticker for r in rows}
    assert "STALE" not in tickers
    assert {"NEW1", "NEW2"} == tickers


def test_pool_cache_rebuild_bars_failure_excludes_ticker(db: Session, fmp: FmpClient):
    """rebuild_bars_failure: one ticker's bars fail → excluded, others succeed."""
    _insert_breakout(db, ["GOOD", "FAIL"])
    spy_bars = _make_bars(260, base=100.0, final=110.0)
    good_bars = _make_bars(260, base=100.0, final=120.0)

    def _bars(symbol, *args):
        if symbol == "FAIL":
            raise RuntimeError("simulated error")
        return spy_bars if symbol == "SPY" else good_bars

    with patch.object(fmp, "get_daily_bars", side_effect=_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.2}):
        result = PoolCacheService(db, fmp).rebuild()

    assert result.status == "ok"
    assert result.upserted == 1
    rows = db.execute(select(CockpitPoolCache)).scalars().all()
    assert {r.ticker for r in rows} == {"GOOD"}


def test_pool_cache_rebuild_growth_null_fail_open(db: Session, fmp: FmpClient):
    """rebuild_growth_null: financial-growth missing → revenue_growth_yoy=null (D079 fail-open)."""
    _insert_breakout(db, ["AAA"])
    spy_bars = _make_bars(260, base=100.0, final=110.0)
    stock_bars = _make_bars(260, base=100.0, final=120.0)

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value=None):
        result = PoolCacheService(db, fmp).rebuild()

    assert result.status == "ok"
    row = db.execute(select(CockpitPoolCache)).scalars().first()
    assert row is not None
    assert row.revenue_growth_yoy is None


def test_pool_cache_rebuild_no_trend_returns_zero(db: Session, fmp: FmpClient):
    """rebuild_no_trend: no breakout snapshot → 0 upserted, no exception."""
    # no breakout rows
    result = PoolCacheService(db, fmp).rebuild()

    assert result.status == "ok"
    assert result.upserted == 0
    rows = db.execute(select(CockpitPoolCache)).scalars().all()
    assert rows == []


def test_pool_cache_rebuild_rs_percentile_ordered(db: Session, fmp: FmpClient):
    """rebuild_rs_correct: highest-return ticker gets highest rs_percentile."""
    _insert_breakout(db, ["HIGH", "LOW"])
    spy_bars = _make_bars(260, base=100.0, final=110.0)
    high_bars = _make_bars(260, base=100.0, final=200.0)  # +100% vs SPY +10%
    low_bars = _make_bars(260, base=100.0, final=105.0)   # +5% < SPY +10%

    def _bars(symbol, *args):
        if symbol == "SPY":
            return spy_bars
        if symbol == "HIGH":
            return high_bars
        return low_bars

    with patch.object(fmp, "get_daily_bars", side_effect=_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.2}):
        PoolCacheService(db, fmp).rebuild()

    rows = {r.ticker: r for r in db.execute(select(CockpitPoolCache)).scalars().all()}
    assert rows["HIGH"].rs_percentile > rows["LOW"].rs_percentile


# ── cron registration test ────────────────────────────────────────────────────

def test_pool_cache_job_registered_in_scheduler():
    """Cron test: scheduler registers POOL_CACHE_JOB_ID after start_scheduler (autostart=False)."""
    from app.services.refresh_job import POOL_CACHE_JOB_ID, shutdown_scheduler, start_scheduler

    # reset module-level singleton
    shutdown_scheduler()

    session_factory = MagicMock()
    fmp_factory = MagicMock()

    sched = start_scheduler(session_factory, fmp_factory, autostart=False)
    try:
        job_ids = {job.id for job in sched.get_jobs()}
        assert POOL_CACHE_JOB_ID in job_ids
    finally:
        shutdown_scheduler()
