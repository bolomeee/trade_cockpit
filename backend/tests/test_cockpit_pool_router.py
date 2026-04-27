"""Integration tests for GET /api/cockpit/pool (F205-c).

Covers sprint contract acceptance criteria:
  #1   universe empty → funnel all-zero + items=[]
  #2   universe present, no breakout_scans → trend=0, rest=0
  #3   breakout_scans 30 in tradable → trend=30
  #4   marketCapMin filter
  #5   priceMin filter
  #6   advMin filter (last_price × last_volume)
  #7   sectors filter
  #11  items sorted by rsPercentile desc
  #12  limit=10 → items ≤ 10; funnel.action = pre-limit count
  #13  watchlist ticker → inWatchlist=true, setupType / suggestedAction / trendScore from snapshots
  #14  non-watchlist ticker → inWatchlist=false, setupType=null, trendScore=null, suggestedAction="watch"
  #15  earnings events → earningsDate / daysUntilEarnings non-null; absent → null
  #19  limit=300 → 422 VALIDATION_ERROR
  #20  rsPercentileMin=120 → 422 VALIDATION_ERROR
  #21  sectors=XYZ → 200, items=[] (no error)

Strategy:
  Uses the conftest `client` fixture (TestClient + FakeFMP).
  FMP is mocked to return adequate bars/growth so RS+fundamental layers always pass
  (except where the test specifically needs them to filter).
  DB fixtures are set up per-test with in-memory SQLite via the conftest db_session / session_engine.
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.dependencies import get_fmp_client
from app.main import app
from app.models.earnings_event import EarningsEvent
from app.models.market_breakout_scan import MarketBreakoutScan
from app.models.market_scan_universe import MarketScanUniverse
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock

_TODAY = date(2026, 4, 27)
_BAR_START = date(2023, 1, 1)


# ── helpers ───────────────────────────────────────────────────────────────────

def _bars(n: int = 260, base: float = 100.0, final: float | None = None) -> list[dict]:
    result = []
    for i in range(n):
        d = (_BAR_START + timedelta(days=i)).isoformat()
        close = base if final is None or i < n - 1 else final
        result.append({"date": d, "close": close})
    return result


def _add_universe(
    db: Session,
    ticker: str,
    *,
    market_cap: int = 100_000_000_000,
    last_price: float = 50.0,
    last_volume: int = 1_000_000,
    sector: str | None = "XLK",
) -> None:
    now = datetime.now(timezone.utc)
    db.add(MarketScanUniverse(
        ticker=ticker,
        company_name=f"{ticker} Corp",
        exchange="NASDAQ",
        market_cap=market_cap,
        last_price=last_price,
        last_volume=last_volume,
        sector=sector,
        last_seen_at=now,
        added_at=now,
    ))
    db.flush()


def _add_breakout(db: Session, ticker: str) -> None:
    db.add(MarketBreakoutScan(
        scan_date=_TODAY,
        ticker=ticker,
        company_name=f"{ticker} Corp",
        signal_type="BREAKOUT",
        close_price=50.0,
        ma150_value=45.0,
        pct_above_ma150=11.0,
        slope_value=0.5,
        market_cap=100_000_000_000,
        scanned_at=datetime.now(timezone.utc),
    ))
    db.flush()


def _add_stock(db: Session, ticker: str) -> Stock:
    stock = Stock(
        ticker=ticker,
        name=f"{ticker} Corp",
        is_active=True,
        added_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.flush()
    return stock


def _add_setup_snapshot(
    db: Session,
    ticker: str,
    *,
    setup_type: str = "BREAKOUT",
    trend_score: int = 4,
    suggested_action: str = "watch",
    distance_to_entry_pct: float = 1.5,
) -> None:
    db.add(SetupSnapshot(
        ticker=ticker,
        scan_date=_TODAY,
        setup_type=setup_type,
        trend_score=trend_score,
        suggested_action=suggested_action,
        distance_to_entry_pct=distance_to_entry_pct,
        earnings_risk="low",
        ready_signal=False,
    ))
    db.flush()


def _add_earnings(db: Session, ticker: str, earnings_date: date) -> None:
    db.add(EarningsEvent(
        ticker=ticker,
        earnings_date=earnings_date,
        fetched_at=datetime.now(timezone.utc),
    ))
    db.flush()


def _configure_fmp_passthrough(fake_fmp, spy_final: float = 110.0, stock_final: float = 130.0) -> None:
    """Configure FakeFMP to return bars that make all tickers pass RS + fundamental."""
    spy_b = _bars(260, base=100.0, final=spy_final)
    stock_b = _bars(260, base=100.0, final=stock_final)
    fake_fmp.daily_bars_results = stock_b
    fake_fmp._spy_bars = spy_b
    fake_fmp._stock_bars = stock_b

    # Override get_daily_bars to be per-symbol aware
    original_get_daily = fake_fmp.get_daily_bars

    def _per_symbol(symbol, from_date=None, to_date=None):
        return spy_b if symbol == "SPY" else stock_b

    fake_fmp.get_daily_bars = _per_symbol
    fake_fmp.financial_growth_results = {"revenueGrowth": 0.5}

    def _growth(ticker):
        return fake_fmp.financial_growth_results

    fake_fmp.get_financial_growth = _growth


# ── #1: empty universe ────────────────────────────────────────────────────────

def test_empty_universe_returns_all_zero_funnel(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#1: universe empty (cold start) → funnel all-zero + items=[]."""
    _configure_fmp_passthrough(fake_fmp)
    db_session.commit()

    resp = client.get("/api/cockpit/pool")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["funnel"] == {"tradable": 0, "trend": 0, "rs": 0, "fundamental": 0, "action": 0}
    assert data["items"] == []


# ── #2: universe present, no breakout_scans ───────────────────────────────────

def test_no_breakout_scans_trend_zero(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#2: universe has tickers but no breakout_scans → trend=0, rest=0."""
    _configure_fmp_passthrough(fake_fmp)
    for i in range(5):
        _add_universe(db_session, f"U{i:02d}")
    db_session.commit()

    resp = client.get("/api/cockpit/pool")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["funnel"]["tradable"] == 5
    assert data["funnel"]["trend"] == 0
    assert data["items"] == []


# ── #3: breakout_scans intersection ───────────────────────────────────────────

def test_trend_count_reflects_breakout_intersection(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#3: 100 universe, 50 breakout with 30 overlap → tradable=100, trend=30."""
    _configure_fmp_passthrough(fake_fmp)
    for i in range(100):
        _add_universe(db_session, f"U{i:03d}")
    # 30 tickers from universe + 20 not in universe
    for i in range(30):
        _add_breakout(db_session, f"U{i:03d}")
    for i in range(20):
        _add_breakout(db_session, f"X{i:03d}")  # not in universe → excluded
    db_session.commit()

    resp = client.get("/api/cockpit/pool")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["funnel"]["tradable"] == 100
    assert data["funnel"]["trend"] == 30


# ── #4: marketCapMin filter ────────────────────────────────────────────────────

def test_market_cap_min_filters_small_caps(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#4: marketCapMin=100B → only market_cap ≥ 100B enter tradable."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "BIG", market_cap=200_000_000_000)
    _add_universe(db_session, "SML", market_cap=50_000_000_000)
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"marketCapMin": 100_000_000_000})
    assert resp.status_code == 200
    assert resp.json()["data"]["funnel"]["tradable"] == 1


# ── #5: priceMin filter ───────────────────────────────────────────────────────

def test_price_min_filters_cheap_stocks(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#5: priceMin=50 → only last_price ≥ 50 enter tradable."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "EXP", last_price=100.0)
    _add_universe(db_session, "CHP", last_price=20.0)
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"priceMin": 50})
    assert resp.status_code == 200
    assert resp.json()["data"]["funnel"]["tradable"] == 1


# ── #6: advMin filter ────────────────────────────────────────────────────────

def test_adv_min_filters_illiquid(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#6: advMin=50M → last_price×last_volume ≥ 50M required."""
    _configure_fmp_passthrough(fake_fmp)
    # 100 × 1_000_000 = 100M → passes 50M
    _add_universe(db_session, "LIQ", last_price=100.0, last_volume=1_000_000)
    # 10 × 1_000_000 = 10M → fails 50M
    _add_universe(db_session, "ILL", last_price=10.0, last_volume=1_000_000)
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"advMin": 50_000_000})
    assert resp.status_code == 200
    assert resp.json()["data"]["funnel"]["tradable"] == 1


# ── #7: sectors filter ────────────────────────────────────────────────────────

def test_sectors_filter_includes_only_matching(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#7: sectors=XLK,XLY → only those sector tickers enter tradable."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "TECH", sector="XLK")
    _add_universe(db_session, "CONS", sector="XLY")
    _add_universe(db_session, "ENRG", sector="XLE")
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"sectors": "XLK,XLY"})
    assert resp.status_code == 200
    assert resp.json()["data"]["funnel"]["tradable"] == 2


# ── #11: items sorted rsPercentile desc ───────────────────────────────────────

def test_items_sorted_by_rs_percentile_desc(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#11: items must be sorted by rsPercentile descending."""
    spy_b = _bars(260, base=100.0, final=110.0)
    # HIGH: stock final=150 → return=50%, ratio=5.0 (top)
    high_b = _bars(260, base=100.0, final=150.0)
    # LOW: stock final=105 → return=5%, ratio=0.5 (bottom)
    low_b = _bars(260, base=100.0, final=105.0)
    bars_map = {"SPY": spy_b, "HIGH": high_b, "LOW": low_b}

    def _bars_fn(symbol, *args):
        return bars_map.get(symbol, spy_b)

    fake_fmp.get_daily_bars = _bars_fn
    fake_fmp.get_financial_growth = lambda t: {"revenueGrowth": 0.3}

    _add_universe(db_session, "HIGH")
    _add_universe(db_session, "LOW")
    _add_breakout(db_session, "HIGH")
    _add_breakout(db_session, "LOW")
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"rsPercentileMin": 0})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    assert len(items) == 2
    percentiles = [i["rsPercentile"] for i in items]
    assert percentiles == sorted(percentiles, reverse=True)
    assert items[0]["ticker"] == "HIGH"


# ── #12: limit truncates items but action is pre-limit count ─────────────────

def test_limit_truncates_items_but_action_unchanged(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#12: limit=2 → items ≤ 2; funnel.action = pre-limit count of fundamental tickers."""
    _configure_fmp_passthrough(fake_fmp)
    for i in range(5):
        _add_universe(db_session, f"L{i:02d}")
        _add_breakout(db_session, f"L{i:02d}")
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"rsPercentileMin": 0, "limit": 2})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["items"]) == 2
    assert data["funnel"]["action"] == 5  # all 5 passed fundamental, only 2 returned


# ── #13: watchlist ticker fields ─────────────────────────────────────────────

def test_watchlist_ticker_has_setup_fields(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#13: watchlist ticker → inWatchlist=true, setupType/suggestedAction/trendScore from snapshots."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "WL1")
    _add_breakout(db_session, "WL1")
    _add_stock(db_session, "WL1")
    _add_setup_snapshot(db_session, "WL1", setup_type="BREAKOUT", trend_score=5, suggested_action="enter")
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"rsPercentileMin": 0})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    wl_item = next((i for i in items if i["ticker"] == "WL1"), None)
    assert wl_item is not None
    assert wl_item["inWatchlist"] is True
    assert wl_item["setupType"] == "BREAKOUT"
    assert wl_item["trendScore"] == 5
    assert wl_item["suggestedAction"] == "enter"


# ── #14: non-watchlist ticker fields ─────────────────────────────────────────

def test_non_watchlist_ticker_has_null_setup_fields(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#14: non-watchlist → inWatchlist=false, setupType=null, trendScore=null, suggestedAction='watch'."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "NWL")
    _add_breakout(db_session, "NWL")
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"rsPercentileMin": 0})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    item = next((i for i in items if i["ticker"] == "NWL"), None)
    assert item is not None
    assert item["inWatchlist"] is False
    assert item["setupType"] is None
    assert item["trendScore"] is None
    assert item["suggestedAction"] == "watch"


# ── #15: earnings events ─────────────────────────────────────────────────────

def test_earnings_date_populated_when_event_exists(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#15a: future earnings event → earningsDate / daysUntilEarnings non-null."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "ERN")
    _add_breakout(db_session, "ERN")
    future_date = _TODAY + timedelta(days=15)
    _add_earnings(db_session, "ERN", future_date)
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"rsPercentileMin": 0})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    item = next((i for i in items if i["ticker"] == "ERN"), None)
    assert item is not None
    assert item["earningsDate"] == future_date.isoformat()
    assert item["daysUntilEarnings"] == 15


def test_no_earnings_event_gives_null_fields(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#15b: no future earnings event → earningsDate=null, daysUntilEarnings=null."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "NOERN")
    _add_breakout(db_session, "NOERN")
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"rsPercentileMin": 0})
    assert resp.status_code == 200
    items = resp.json()["data"]["items"]
    item = next((i for i in items if i["ticker"] == "NOERN"), None)
    assert item is not None
    assert item["earningsDate"] is None
    assert item["daysUntilEarnings"] is None


# ── #19: limit=300 → 422 ─────────────────────────────────────────────────────

def test_limit_over_max_returns_422(client: TestClient) -> None:
    """#19: limit=300 → 422 VALIDATION_ERROR."""
    resp = client.get("/api/cockpit/pool", params={"limit": 300})
    assert resp.status_code == 422


# ── #20: rsPercentileMin=120 → 422 ───────────────────────────────────────────

def test_rs_percentile_min_over_100_returns_422(client: TestClient) -> None:
    """#20: rsPercentileMin=120 → 422 VALIDATION_ERROR."""
    resp = client.get("/api/cockpit/pool", params={"rsPercentileMin": 120})
    assert resp.status_code == 422


# ── #21: invalid sectors → 200, empty items ──────────────────────────────────

def test_invalid_sector_returns_200_empty(
    client: TestClient, db_session: Session, fake_fmp: Any
) -> None:
    """#21: sectors=XYZ (no match) → HTTP 200, items=[] (no error)."""
    _configure_fmp_passthrough(fake_fmp)
    _add_universe(db_session, "AAPL", sector="XLK")
    db_session.commit()

    resp = client.get("/api/cockpit/pool", params={"sectors": "XYZ"})
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["funnel"]["tradable"] == 0
    assert data["items"] == []
