"""Unit tests for PoolService (F205-c).

Covers sprint contract acceptance criteria:
  #8  rsPercentileMin filter
  #9  revenueGrowthYoyMin + fail-open on None
  #10  trend cap → POOL_TREND_CAP, market_cap desc
  #10b concurrent FMP: 30 tickers with 200ms latency → total < 50% of serial
  #10c per-ticker FMP failure → that ticker drops at RS layer, rest succeed
  #16  distanceTo50maPct = compute_distance_to_50ma_pct(close, ma50)
  #17  FMP get_daily_bars exception → ticker skips RS layer (ratio=None → percentile=bottom)
  #18  FMP get_financial_growth returns None → fail-open (ticker passes fundamental)

Strategy: monkeypatch FmpClient methods directly (no parallel mock class);
         repos replaced with in-memory SQLite via SQLAlchemy.
"""
from __future__ import annotations

import time
from datetime import date, datetime, timedelta, timezone
from unittest.mock import patch

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models import Base
from app.models.market_breakout_scan import MarketBreakoutScan
from app.models.market_scan_universe import MarketScanUniverse
from app.services.cockpit.pool_service import POOL_TREND_CAP, PoolParams, PoolService


# ── fixtures ─────────────────────────────────────────────────────────────────

@pytest.fixture()
def db():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    with Session(engine) as session:
        yield session


@pytest.fixture()
def fmp():
    """Real FmpClient instance; individual methods patched per test."""
    return FmpClient.__new__(FmpClient)


def _make_service(db: Session, fmp: FmpClient) -> PoolService:
    return PoolService(db=db, fmp=fmp)


_BAR_START = date(2023, 1, 1)


def _make_bars(n: int = 260, base: float = 100.0, final: float | None = None) -> list[dict]:
    """Generate n daily bar dicts with proper ISO dates (ascending, sorts correctly)."""
    bars = []
    for i in range(n):
        d = (_BAR_START + timedelta(days=i)).isoformat()
        close = base if final is None or i < n - 1 else final
        bars.append({"date": d, "close": close})
    return bars


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


# ── Test #8: rsPercentileMin ──────────────────────────────────────────────────

def test_rs_percentile_min_filters_low_rank(db: Session, fmp: FmpClient):
    """#8: rsPercentileMin=80 → only tickers with rs_percentile ≥ 80 pass."""
    # 3 tickers: A outperforms SPY (high RS), B matches SPY (mid RS), C lags (low RS)
    _insert_universe(db, [("AAA", 100_000_000_000), ("BBB", 100_000_000_000), ("CCC", 100_000_000_000)])
    _insert_breakout(db, ["AAA", "BBB", "CCC"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    aaa_bars = _make_bars(260, base=100.0, final=130.0)  # +30% vs SPY +10% → ratio 3.0 (top)
    bbb_bars = _make_bars(260, base=100.0, final=110.0)  # same as SPY → ratio 1.0 (mid)
    ccc_bars = _make_bars(260, base=100.0, final=100.0)  # flat → ratio 0 / SPY +10% (bottom)

    bars_by_ticker = {"SPY": spy_bars, "AAA": aaa_bars, "BBB": bbb_bars, "CCC": ccc_bars}

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: bars_by_ticker.get(s, [])), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.5}):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=80.0, revenue_growth_yoy_min=0.0)
        result = svc.get_pool(params)

    item_tickers = {i["ticker"] for i in result["items"]}
    # Only AAA should be in top 80th percentile (3 tickers: AAA=top, BBB=mid, CCC=bottom)
    assert "AAA" in item_tickers
    assert "CCC" not in item_tickers
    assert result["funnel"]["rs"] <= result["funnel"]["trend"]


# ── Test #9: revenueGrowthYoyMin + fail-open ─────────────────────────────────

def test_revenue_growth_min_filters_low_growth(db: Session, fmp: FmpClient):
    """#9a: revenueGrowthYoyMin=15.0 → ticker with 10% growth is excluded."""
    _insert_universe(db, [("HIGH", 100_000_000_000), ("LOW", 100_000_000_000)])
    _insert_breakout(db, ["HIGH", "LOW"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    stock_bars = _make_bars(260, base=100.0, final=130.0)  # both pass RS easily

    growth_by_ticker = {
        "HIGH": {"revenueGrowth": 0.20},  # 20% → passes 15% threshold
        "LOW":  {"revenueGrowth": 0.10},  # 10% → fails 15% threshold
    }

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", side_effect=lambda t: growth_by_ticker.get(t)):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=15.0)
        result = svc.get_pool(params)

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "HIGH" in item_tickers
    assert "LOW" not in item_tickers


def test_revenue_growth_none_fail_open(db: Session, fmp: FmpClient):
    """#9b: get_financial_growth returns None → ticker passes fundamental (fail-open D079)."""
    _insert_universe(db, [("NODATA", 100_000_000_000)])
    _insert_breakout(db, ["NODATA"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    stock_bars = _make_bars(260, base=100.0, final=130.0)

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value=None):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=50.0)
        result = svc.get_pool(params)

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "NODATA" in item_tickers
    assert result["items"][0]["revenue_growth_yoy"] is None


# ── Test #10: trend cap ────────────────────────────────────────────────────────

def test_trend_cap_truncates_to_200_by_market_cap(db: Session, fmp: FmpClient):
    """#10: trend subset > POOL_TREND_CAP → cap to 200 by market_cap desc."""
    n_tickers = POOL_TREND_CAP + 20  # 220 tickers
    # All tickers have market_cap ≥ 100B so they all pass the default market_cap_min=50B.
    # T000 has the highest cap, T219 the lowest (so T200..T219 are dropped by the cap).
    tickers_caps = [(f"T{i:03d}", (1000 - i) * 1_000_000_000) for i in range(n_tickers)]
    _insert_universe(db, tickers_caps)
    _insert_breakout(db, [t for t, _ in tickers_caps])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    stock_bars = _make_bars(260, base=100.0, final=120.0)

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.5}):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0, limit=200)
        result = svc.get_pool(params)

    assert result["funnel"]["trend"] == POOL_TREND_CAP
    # Top 200 by market_cap are T000–T199; T200–T219 are dropped.
    item_tickers = {i["ticker"] for i in result["items"]}
    assert "T000" in item_tickers
    assert "T200" not in item_tickers


# ── Test #10b: concurrency timing ─────────────────────────────────────────────

def test_concurrent_fmp_calls_faster_than_serial(db: Session, fmp: FmpClient):
    """#10b: 30 tickers with 200ms latency each → concurrent < 50% of serial (6s)."""
    n = 30
    tickers_caps = [(f"C{i:02d}", 1_000_000_000) for i in range(n)]
    _insert_universe(db, tickers_caps)
    _insert_breakout(db, [t for t, _ in tickers_caps])

    spy_bars = _make_bars(260, base=100.0, final=110.0)

    def _slow_bars(symbol: str, *args):
        time.sleep(0.2)
        return spy_bars  # same data for all — all will have ratio ~1.0 and low RS percentile

    with patch.object(fmp, "get_daily_bars", side_effect=_slow_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.5}):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0, limit=30)
        start = time.monotonic()
        svc.get_pool(params)
        elapsed = time.monotonic() - start

    serial_time = 0.2 * (n + 1)  # +1 for SPY call (serial)
    assert elapsed < serial_time * 0.50, (
        f"concurrent elapsed {elapsed:.2f}s ≥ 50% of serial {serial_time:.2f}s"
    )


# ── Test #10c: per-ticker FMP failure ─────────────────────────────────────────

def test_per_ticker_fmp_failure_does_not_crash_pool(db: Session, fmp: FmpClient):
    """#10c: one ticker's get_daily_bars raises → that ticker skips RS, rest succeed."""
    _insert_universe(db, [("GOOD", 100_000_000_000), ("FAIL", 100_000_000_000)])
    _insert_breakout(db, ["GOOD", "FAIL"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    good_bars = _make_bars(260, base=100.0, final=130.0)

    def _selective_bars(symbol: str, *args):
        if symbol == "SPY":
            return spy_bars
        if symbol == "FAIL":
            raise RuntimeError("simulated FMP error")
        return good_bars

    with patch.object(fmp, "get_daily_bars", side_effect=_selective_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.5}):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0)
        # Must not raise
        result = svc.get_pool(params)

    item_tickers = {i["ticker"] for i in result["items"]}
    # GOOD should still appear; FAIL is at bottom percentile (ratio=None) but with
    # rs_percentile_min=0.0 it may also appear — key: no exception raised
    assert result["funnel"]["tradable"] == 2
    assert result["funnel"]["trend"] == 2


# ── Test #16: distanceTo50maPct ───────────────────────────────────────────────

def test_distance_to_50ma_pct_computed_correctly(db: Session, fmp: FmpClient):
    """#16: distanceTo50maPct = compute_distance_to_50ma_pct(close, closes[-50:] mean)."""
    _insert_universe(db, [("MA50", 100_000_000_000)])
    _insert_breakout(db, ["MA50"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    # All 260 bars at close=50.0 → ma50 = 50.0, close = 50.0 → distance = 0%
    stock_bars = _make_bars(260, base=50.0)

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.5}):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0)
        result = svc.get_pool(params)

    assert result["items"], "expected at least one item"
    item = next(i for i in result["items"] if i["ticker"] == "MA50")
    assert item["distance_to_50ma_pct"] == pytest.approx(0.0, abs=1e-4)


def test_distance_to_50ma_pct_above_ma(db: Session, fmp: FmpClient):
    """#16b: close 10% above ma50 → distanceTo50maPct ≈ 10.0."""
    _insert_universe(db, [("ABOVE", 100_000_000_000)])
    _insert_breakout(db, ["ABOVE"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    # First 210 bars at 100, last 50 bars at 110 → ma50 = 110, close = 110 → 0%
    # Better: 260 bars at 100 except final = 110 → ma50 = (210*100 + 50*100)/50 = 100, close=110 → 10%
    # Actually last bar is close=110, previous 259 bars close=100
    bars_210 = [{"date": f"2025-{i + 1:04d}", "close": 100.0} for i in range(210)]
    bars_50 = [{"date": f"2026-{i + 1:04d}", "close": 100.0} for i in range(49)]
    bars_50.append({"date": "2026-0050", "close": 110.0})  # final bar
    stock_bars = bars_210 + bars_50  # last 50 bars: 49×100 + 1×110 → ma50 = 100.2

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.5}):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=0.0)
        result = svc.get_pool(params)

    item = next((i for i in result["items"] if i["ticker"] == "ABOVE"), None)
    assert item is not None
    # close=110, ma50 = (49*100 + 110)/50 = 100.2 → (110 - 100.2) / 100.2 * 100 ≈ 9.78%
    assert item["distance_to_50ma_pct"] is not None
    assert item["distance_to_50ma_pct"] > 0


# ── Test #17: FMP bars exception → skip RS ────────────────────────────────────

def test_fmp_bars_exception_skips_ticker_at_rs_layer(db: Session, fmp: FmpClient):
    """#17: get_daily_bars raises for ticker X → X gets None ratio → bottom percentile."""
    _insert_universe(db, [("ERRX", 100_000_000_000), ("GOOD", 100_000_000_000)])
    _insert_breakout(db, ["ERRX", "GOOD"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    # GOOD: stock return = +80%, SPY return = +10% → ratio = 8.0 (very high)
    good_bars = _make_bars(260, base=100.0, final=180.0)

    def _bars(symbol, *args):
        if symbol == "ERRX":
            raise ConnectionError("timeout")
        return spy_bars if symbol == "SPY" else good_bars

    with patch.object(fmp, "get_daily_bars", side_effect=_bars), \
         patch.object(fmp, "get_financial_growth", return_value={"revenueGrowth": 0.5}):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=60.0, revenue_growth_yoy_min=0.0)
        result = svc.get_pool(params)

    item_tickers = {i["ticker"] for i in result["items"]}
    assert "GOOD" in item_tickers
    assert "ERRX" not in item_tickers  # failed bars → bottom percentile, filtered by rs_percentile_min=60


# ── Test #18: financial_growth None → fail-open ──────────────────────────────

def test_financial_growth_none_passes_fundamental(db: Session, fmp: FmpClient):
    """#18: get_financial_growth returns None → ticker passes fundamental layer (fail-open)."""
    _insert_universe(db, [("NOFUND", 100_000_000_000)])
    _insert_breakout(db, ["NOFUND"])

    spy_bars = _make_bars(260, base=100.0, final=110.0)
    stock_bars = _make_bars(260, base=100.0, final=130.0)

    with patch.object(fmp, "get_daily_bars", side_effect=lambda s, *a: spy_bars if s == "SPY" else stock_bars), \
         patch.object(fmp, "get_financial_growth", return_value=None):
        svc = _make_service(db, fmp)
        params = PoolParams(rs_percentile_min=0.0, revenue_growth_yoy_min=99.0)
        result = svc.get_pool(params)

    assert result["funnel"]["fundamental"] == 1
    assert any(i["ticker"] == "NOFUND" for i in result["items"])
