from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import httpx
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock
from app.models.cockpit_pool_cache import CockpitPoolCache
from app.repositories.pullback_repository import PullbackRepository
from app.services.signal_service import SignalService
from app.services.stock_detail_service import _compute_p_fcf


def _seed_pool(db: Session, ticker: str) -> None:
    """F220-b: insert a trend-pool membership row (read by _is_pool_member)."""
    db.add(CockpitPoolCache(ticker=ticker, rs_percentile=90.0))
    db.commit()


def _cf_q(ocf, capex, sbc=None, *, ocf_key="operatingCashFlow"):
    """Build one FMP quarterly cash-flow row for P/FCF tests."""
    q: dict = {ocf_key: ocf, "capitalExpenditure": capex}
    if sbc is not None:
        q["stockBasedCompensation"] = sbc
    return q


def _seed_stock(db: Session, ticker: str, is_active: bool = True) -> Stock:
    stock = Stock(
        ticker=ticker,
        name=f"{ticker} Inc.",
        exchange="NASDAQ",
        is_active=is_active,
        added_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _seed_bars(db: Session, stock_id: int, closes: list[float]) -> None:
    start = date(2025, 1, 1)
    for i, c in enumerate(closes):
        db.add(
            DailyBar(
                stock_id=stock_id,
                date=start + timedelta(days=i),
                open=c,
                high=c + 0.5,
                low=c - 0.5,
                close=c,
                volume=1_000_000 + i,
            )
        )
    db.commit()


def _recompute(db: Session, stock_id: int) -> None:
    SignalService(db).recompute_for_stock(stock_id)


def test_chart_returns_bars_ascending_with_ma150_and_markers(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "AAPL")
    closes = [100.0 + i * 0.1 for i in range(180)]
    # create a pullback-inducing dip at the end
    closes[-3] = closes[-4] * 0.98
    _seed_bars(db_session, stock.id, closes)
    _recompute(db_session, stock.id)

    resp = client.get("/api/stocks/AAPL/chart")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["ticker"] == "AAPL"
    bars = data["bars"]
    assert len(bars) == 180
    dates = [b["date"] for b in bars]
    assert dates == sorted(dates)
    assert set(bars[0].keys()) == {"date", "open", "high", "low", "close", "volume"}

    ma150 = data["ma150"]
    assert len(ma150) == 180 - 149
    assert all(p["value"] is not None for p in ma150)
    assert ma150[0]["date"] >= bars[149]["date"]

    assert "pullbackMarkers" in data
    for m in data["pullbackMarkers"]:
        assert "date" in m and "distancePct" in m


def test_chart_empty_ma150_when_bars_below_150(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "BBB")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(120)])
    _recompute(db_session, stock.id)

    resp = client.get("/api/stocks/BBB/chart")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert len(data["bars"]) == 120
    assert data["ma150"] == []
    assert data["pullbackMarkers"] == []


def test_chart_returns_at_most_250_recent_bars(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "CCC")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(300)])
    _recompute(db_session, stock.id)

    resp = client.get("/api/stocks/CCC/chart")
    assert resp.status_code == 200
    bars = resp.json()["data"]["bars"]
    assert len(bars) == 250
    start = date(2025, 1, 1)
    first_expected = (start + timedelta(days=300 - 250)).isoformat()
    assert bars[0]["date"] == first_expected


def test_pullbacks_sorted_desc_with_nullable_returns(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "DDD")
    # Gentle uptrend (240 bars) — produces BUY_ZONE transitions near the end
    closes = [100.0 + i * 0.05 for i in range(240)]
    _seed_bars(db_session, stock.id, closes)
    _recompute(db_session, stock.id)

    resp = client.get("/api/stocks/DDD/pullbacks")
    assert resp.status_code == 200
    rows = resp.json()["data"]

    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)
    assert rows, "fixture should produce at least one pullback"
    row = rows[0]
    for field in (
        "date",
        "closePrice",
        "ma150Value",
        "distancePct",
        "return10d",
        "return20d",
        "return30d",
    ):
        assert field in row, f"missing field {field}; got {list(row.keys())}"


def test_fundamentals_merges_ratios_and_key_metrics(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    _seed_stock(db_session, "EEE")
    fake_fmp.ratios_results["EEE"] = {
        "symbol": "EEE",
        "priceToEarningsRatioTTM": 33.84,
        "priceToSalesRatioTTM": 9.12,
        "priceToEarningsGrowthRatioTTM": 5.75,
        "freeCashFlowPerShareTTM": 8.36,
    }
    fake_fmp.key_metrics_results["EEE"] = {
        "symbol": "EEE",
        "marketCap": 3_200_000_000_000,
        "returnOnCapitalEmployedTTM": 0.6503,
        "freeCashFlowYieldTTM": 0.031,  # FCF = 3.2T × 0.031 = 99.2B
    }

    resp = client.get("/api/stocks/EEE/fundamentals")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["ticker"] == "EEE"
    assert data["source"] == "fmp"
    assert data["priceToEarnings"] == 33.84
    assert data["priceToSales"] == 9.12
    assert data["peg"] == 5.75
    assert data["roce"] == 0.6503
    assert data["marketCap"] == 3_200_000_000_000
    assert data["freeCashFlow"] == pytest.approx(3_200_000_000_000 * 0.031)
    assert data["updatedAt"]
    assert fake_fmp.ratios_calls == ["EEE"]
    assert fake_fmp.key_metrics_calls == ["EEE"]


def test_fundamentals_nullifies_missing_fields(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    _seed_stock(db_session, "FFF")
    # Only marketCap present; ratios missing entirely; no FCF yield
    fake_fmp.key_metrics_results["FFF"] = {
        "symbol": "FFF",
        "marketCap": 50_000_000,
    }

    resp = client.get("/api/stocks/FFF/fundamentals")
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert data["priceToEarnings"] is None
    assert data["priceToSales"] is None
    assert data["peg"] is None
    assert data["roce"] is None
    assert data["freeCashFlow"] is None  # marketCap present but yield missing
    assert data["marketCap"] == 50_000_000
    assert data["source"] == "fmp"


def test_fundamentals_nullifies_all_when_fmp_empty(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    _seed_stock(db_session, "GGH")
    # Both endpoints return no record
    resp = client.get("/api/stocks/GGH/fundamentals")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["source"] == "fmp"
    for field in ("priceToEarnings", "priceToSales", "peg", "roce", "freeCashFlow", "marketCap"):
        assert data[field] is None


def test_fundamentals_502_when_fmp_http_error(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    import httpx as _httpx

    _seed_stock(db_session, "HHE")

    def _boom(symbol):
        raise _httpx.ConnectError("network down")

    fake_fmp.get_ratios_ttm = _boom  # type: ignore[assignment]

    resp = client.get("/api/stocks/HHE/fundamentals")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "EXTERNAL_API_ERROR"


def test_detail_endpoints_404_when_ticker_missing(client: TestClient) -> None:
    # chart: non-watchlist + no FMP bars → still 404
    resp = client.get("/api/stocks/ZZZZ/chart")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"
    # F108: pullbacks + fundamentals are now open to any ticker
    assert client.get("/api/stocks/ZZZZ/pullbacks").status_code == 200
    assert client.get("/api/stocks/ZZZZ/fundamentals").status_code == 200


def test_detail_endpoints_404_when_ticker_inactive(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "INAC", is_active=False)
    # chart: inactive ticker → still 404
    resp = client.get("/api/stocks/INAC/chart")
    assert resp.status_code == 404
    # F108: pullbacks + fundamentals return 200 for inactive tickers
    assert client.get("/api/stocks/INAC/pullbacks").status_code == 200
    assert client.get("/api/stocks/INAC/fundamentals").status_code == 200


def test_detail_endpoints_are_case_insensitive(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "GGG")
    for path in ("chart", "pullbacks", "fundamentals"):
        resp = client.get(f"/api/stocks/ggg/{path}")
        assert resp.status_code == 200, path


# ---------- F105-b: /chart on-demand fallback ----------


def _make_fmp_bars(start: date, closes: list[float]) -> list[dict]:
    # FMP returns descending-by-date list; service layer sorts ascending
    bars = [
        {
            "date": (start + timedelta(days=i)).isoformat(),
            "open": c,
            "high": c + 0.5,
            "low": c - 0.5,
            "close": c,
            "volume": 1_000_000 + i,
        }
        for i, c in enumerate(closes)
    ]
    return list(reversed(bars))


def test_chart_fallback_for_unknown_ticker(
    client: TestClient, fake_fmp
) -> None:
    closes = [100.0 + i * 0.2 for i in range(200)]
    fake_fmp.daily_bars_results = _make_fmp_bars(date(2025, 1, 1), closes)

    resp = client.get("/api/stocks/pltr/chart")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "PLTR"
    assert len(data["bars"]) == 200
    dates = [b["date"] for b in data["bars"]]
    assert dates == sorted(dates)
    assert len(data["ma150"]) == 200 - 149
    assert data["pullbackMarkers"] == []
    # FMP called once with upper-cased ticker
    assert fake_fmp.daily_bars_calls[0][0] == "PLTR"


def test_chart_fallback_for_inactive_ticker(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    _seed_stock(db_session, "INAC", is_active=False)
    fake_fmp.daily_bars_results = _make_fmp_bars(
        date(2025, 1, 1), [50.0 + i * 0.1 for i in range(160)]
    )

    resp = client.get("/api/stocks/INAC/chart")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "INAC"
    assert len(data["bars"]) == 160
    assert data["pullbackMarkers"] == []


def test_chart_fallback_empty_fmp_returns_404(
    client: TestClient, fake_fmp
) -> None:
    fake_fmp.daily_bars_results = []
    resp = client.get("/api/stocks/ZZZZ/chart")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_chart_fallback_fmp_http_error_returns_502(
    client: TestClient, fake_fmp
) -> None:
    fake_fmp.daily_bars_exc = httpx.ConnectError("boom")
    resp = client.get("/api/stocks/AAPL/chart")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "EXTERNAL_API_ERROR"


# ---------- F107-b1: shares_float on /chart ----------


def test_chart_includes_shares_float_from_fmp_profile_and_caches(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    """Watchlist path: first /chart call hits FMP /shares-float and writes DB cache."""
    stock = _seed_stock(db_session, "AAPL")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(10)])
    fake_fmp.shares_float_results["AAPL"] = {
        "symbol": "AAPL",
        "floatShares": 15_200_000_000,
    }

    resp = client.get("/api/stocks/AAPL/chart")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["sharesFloat"] == 15_200_000_000
    assert fake_fmp.shares_float_calls == ["AAPL"]

    db_session.expire_all()
    refreshed = db_session.query(Stock).filter_by(ticker="AAPL").one()
    assert refreshed.shares_float == 15_200_000_000
    assert refreshed.shares_float_refreshed_at is not None


def test_chart_uses_db_cache_within_24h(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    stock = _seed_stock(db_session, "MSFT")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(10)])
    # Seed a fresh cache (1 hour old)
    stock.shares_float = 7_400_000_000
    stock.shares_float_refreshed_at = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=1)
    )
    db_session.commit()

    resp = client.get("/api/stocks/MSFT/chart")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] == 7_400_000_000
    assert fake_fmp.shares_float_calls == []  # cache hit, no FMP call


def test_chart_refreshes_shares_float_after_24h(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    stock = _seed_stock(db_session, "TSLA")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(10)])
    stock.shares_float = 3_000_000_000  # stale value
    stock.shares_float_refreshed_at = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=25)
    )
    db_session.commit()
    fake_fmp.shares_float_results["TSLA"] = {
        "symbol": "TSLA",
        "floatShares": 2_900_000_000,  # updated value
    }

    resp = client.get("/api/stocks/TSLA/chart")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] == 2_900_000_000
    assert fake_fmp.shares_float_calls == ["TSLA"]


def test_chart_falls_back_to_sharesFloat_field_name(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    """D051 double-field: legacy payload shipping `sharesFloat` still resolves."""
    stock = _seed_stock(db_session, "NVDA")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(10)])
    fake_fmp.shares_float_results["NVDA"] = {
        "symbol": "NVDA",
        "sharesFloat": 24_500_000_000,  # only legacy field present
    }

    resp = client.get("/api/stocks/NVDA/chart")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] == 24_500_000_000


def test_chart_shares_float_null_when_fmp_empty(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    stock = _seed_stock(db_session, "SPY")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(10)])
    # fake_fmp.shares_float_results["SPY"] omitted → returns None (FMP empty)

    resp = client.get("/api/stocks/SPY/chart")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] is None
    assert fake_fmp.shares_float_calls == ["SPY"]

    # Even on null, refreshed_at is stamped so we don't re-hit FMP next call.
    db_session.expire_all()
    refreshed = db_session.query(Stock).filter_by(ticker="SPY").one()
    assert refreshed.shares_float is None
    assert refreshed.shares_float_refreshed_at is not None


def test_chart_fallback_path_includes_shares_float(
    client: TestClient, fake_fmp
) -> None:
    """Non-watchlist ticker fallback: shares_float via FMP, no DB cache."""
    closes = [100.0 + i * 0.2 for i in range(200)]
    fake_fmp.daily_bars_results = _make_fmp_bars(date(2025, 1, 1), closes)
    fake_fmp.shares_float_results["PLTR"] = {"floatShares": 2_100_000_000}

    resp = client.get("/api/stocks/pltr/chart")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] == 2_100_000_000
    assert fake_fmp.shares_float_calls == ["PLTR"]


def test_chart_swallows_fmp_profile_http_error(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    """FMP profile HTTP failure must not break /chart — sharesFloat goes null."""
    stock = _seed_stock(db_session, "AMD")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(10)])
    fake_fmp.shares_float_exc = httpx.ConnectError("shares-float network down")

    resp = client.get("/api/stocks/AMD/chart")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] is None


# ---------- F107-b3: shares_float on /fundamentals ----------


def test_fundamentals_uses_db_cache_within_24h(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    stock = _seed_stock(db_session, "CSCO")
    stock.shares_float = 4_100_000_000
    stock.shares_float_refreshed_at = (
        datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(hours=2)
    )
    db_session.commit()

    resp = client.get("/api/stocks/CSCO/fundamentals")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] == 4_100_000_000
    assert fake_fmp.shares_float_calls == []  # cache hit, no FMP call


def test_fundamentals_misses_cache_then_fetches_fmp(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    _seed_stock(db_session, "ORCL")
    fake_fmp.shares_float_results["ORCL"] = {
        "symbol": "ORCL",
        "floatShares": 2_700_000_000,
    }

    resp = client.get("/api/stocks/ORCL/fundamentals")
    assert resp.status_code == 200
    assert resp.json()["data"]["sharesFloat"] == 2_700_000_000
    assert fake_fmp.shares_float_calls == ["ORCL"]

    db_session.expire_all()
    refreshed = db_session.query(Stock).filter_by(ticker="ORCL").one()
    assert refreshed.shares_float == 2_700_000_000
    assert refreshed.shares_float_refreshed_at is not None


def test_pullback_repository_returns_rows_desc(
    db_session: Session,
) -> None:
    stock = _seed_stock(db_session, "HHH")
    closes = [100.0 + i * 0.2 for i in range(160)]
    for offset in (-5, -15, -25):
        closes[offset] = closes[offset - 1] * 0.99
    _seed_bars(db_session, stock.id, closes)
    _recompute(db_session, stock.id)

    repo = PullbackRepository(db_session)
    rows = repo.list_by_stock(stock.id)
    dates = [r.date for r in rows]
    assert dates == sorted(dates, reverse=True)


# ---------- F108: /fundamentals + /pullbacks open to any ticker ----------


def test_fundamentals_for_unknown_ticker_hits_fmp(
    client: TestClient, fake_fmp
) -> None:
    fake_fmp.ratios_results["UKWN"] = {"priceToEarningsRatioTTM": 25.5}
    fake_fmp.key_metrics_results["UKWN"] = {"marketCap": 1_000_000_000}
    resp = client.get("/api/stocks/UKWN/fundamentals")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["priceToEarnings"] == pytest.approx(25.5)
    assert data["marketCap"] == pytest.approx(1_000_000_000)
    assert data["ticker"] == "UKWN"
    assert "UKWN" in fake_fmp.ratios_calls


def test_fundamentals_fmp_http_error_for_unknown_ticker(
    client: TestClient, fake_fmp
) -> None:
    def _boom(symbol: str) -> None:
        raise httpx.ConnectError("network down")

    fake_fmp.get_ratios_ttm = _boom  # type: ignore[assignment]
    resp = client.get("/api/stocks/UKWN2/fundamentals")
    assert resp.status_code == 502
    assert resp.json()["error"]["code"] == "EXTERNAL_API_ERROR"


def test_fundamentals_empty_ticker_returns_404(client: TestClient) -> None:
    resp = client.get("/api/stocks/%20/fundamentals")
    assert resp.status_code == 404
    assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_pullbacks_for_unknown_ticker_returns_empty(client: TestClient) -> None:
    resp = client.get("/api/stocks/NOTHERE/pullbacks")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_pullbacks_for_inactive_ticker_returns_empty(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "INAC2", is_active=False)
    resp = client.get("/api/stocks/INAC2/pullbacks")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


# ---------- F111-a: same-day on-demand payload cache ----------


def test_chart_fallback_cached_on_second_call(
    client: TestClient, fake_fmp
) -> None:
    """First call fetches from FMP; second call within same day hits DB cache (no FMP)."""
    closes = [100.0 + i * 0.2 for i in range(200)]
    fake_fmp.daily_bars_results = _make_fmp_bars(date(2025, 1, 1), closes)

    r1 = client.get("/api/stocks/NVME/chart")
    assert r1.status_code == 200
    assert len(fake_fmp.daily_bars_calls) == 1

    # Second call — FMP must NOT be called again
    r2 = client.get("/api/stocks/NVME/chart")
    assert r2.status_code == 200
    assert len(fake_fmp.daily_bars_calls) == 1  # still 1
    assert r2.json()["data"]["ticker"] == "NVME"
    assert len(r2.json()["data"]["bars"]) == len(r1.json()["data"]["bars"])


def test_chart_fallback_cache_miss_after_day_change(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    """Cache row dated yesterday is ignored; FMP is re-fetched today."""
    import json
    from datetime import timezone as _tz

    from app.models.daily_payload_cache import ENDPOINT_CHART, DailyPayloadCache

    yesterday = date.today() - timedelta(days=1)
    stale_row = DailyPayloadCache(
        ticker="STALE",
        endpoint=ENDPOINT_CHART,
        as_of_date=yesterday,
        payload_json=json.dumps({
            "ticker": "STALE", "bars": [], "ma150": [], "pullbackMarkers": [], "sharesFloat": None
        }),
        cached_at=datetime.now(_tz.utc).replace(tzinfo=None),
    )
    db_session.add(stale_row)
    db_session.commit()

    closes = [100.0 + i * 0.2 for i in range(200)]
    fake_fmp.daily_bars_results = _make_fmp_bars(date(2025, 1, 1), closes)

    resp = client.get("/api/stocks/STALE/chart")
    assert resp.status_code == 200
    assert len(fake_fmp.daily_bars_calls) == 1  # stale cache ignored → FMP called


def test_fundamentals_cached_on_second_call(
    client: TestClient, fake_fmp
) -> None:
    """First fundamentals call hits FMP; second call within same day hits DB cache."""
    fake_fmp.ratios_results["CACH"] = {"priceToEarningsRatioTTM": 20.0}
    fake_fmp.key_metrics_results["CACH"] = {"marketCap": 500_000_000}

    r1 = client.get("/api/stocks/CACH/fundamentals")
    assert r1.status_code == 200
    assert fake_fmp.ratios_calls == ["CACH"]
    assert fake_fmp.key_metrics_calls == ["CACH"]

    # Reset call tracking (do NOT reset results — cache should answer instead)
    fake_fmp.ratios_calls.clear()
    fake_fmp.key_metrics_calls.clear()

    r2 = client.get("/api/stocks/CACH/fundamentals")
    assert r2.status_code == 200
    assert fake_fmp.ratios_calls == []       # cache hit — no FMP
    assert fake_fmp.key_metrics_calls == []
    assert r2.json()["data"]["priceToEarnings"] == 20.0
    assert r2.json()["data"]["marketCap"] == 500_000_000


def test_fundamentals_fmp_error_not_cached(
    client: TestClient, fake_fmp
) -> None:
    """FMP error path must not write to cache; next successful call still hits FMP."""
    import httpx as _httpx

    def _boom(symbol: str):
        raise _httpx.ConnectError("network down")

    fake_fmp.get_ratios_ttm = _boom  # type: ignore[assignment]

    r1 = client.get("/api/stocks/ERRX/fundamentals")
    assert r1.status_code == 502

    # Restore FMP and verify it gets called again (cache was not written)
    fake_fmp.get_ratios_ttm = lambda symbol: fake_fmp.ratios_results.get(symbol)  # type: ignore[method-assign]
    fake_fmp.ratios_results["ERRX"] = {"priceToEarningsRatioTTM": 15.0}
    fake_fmp.key_metrics_results["ERRX"] = {"marketCap": 100_000_000}

    r2 = client.get("/api/stocks/ERRX/fundamentals")
    assert r2.status_code == 200
    assert r2.json()["data"]["priceToEarnings"] == 15.0


def test_chart_fmp_error_not_cached(client: TestClient, fake_fmp) -> None:
    """FMP httpx error on chart fallback must not write cache; chart stays 502."""
    fake_fmp.daily_bars_exc = httpx.ConnectError("boom")
    r1 = client.get("/api/stocks/ERRCH/chart")
    assert r1.status_code == 502

    # Fix FMP, verify next call hits FMP (not cache)
    fake_fmp.daily_bars_exc = None
    closes = [50.0 + i * 0.1 for i in range(160)]
    fake_fmp.daily_bars_results = _make_fmp_bars(date(2025, 1, 1), closes)
    fake_fmp.daily_bars_calls.clear()

    r2 = client.get("/api/stocks/ERRCH/chart")
    assert r2.status_code == 200
    assert len(fake_fmp.daily_bars_calls) == 1  # FMP called, not cache


# ───────────────────────── F220-b: P/(FCF−SBC) 双版本 ─────────────────────────


def test_compute_p_fcf_normal_four_quarters() -> None:
    # OCF=100, capex=-30 → 70/quarter → FCF=280; SBC=10/quarter → 40
    quarters = [_cf_q(100, -30, 10)] * 4
    raw, adj = _compute_p_fcf(quarters, market_cap=700)
    assert raw == pytest.approx(700 / 280)          # 2.5
    assert adj == pytest.approx(700 / (280 - 40))   # 700/240


def test_compute_p_fcf_capex_added_by_sign() -> None:
    # capex must be added by its (negative) sign, not abs / double-negated.
    # OCF=100, capex=-30 → FCF=70/quarter. abs would give 130 → FCF 520.
    raw, _ = _compute_p_fcf([_cf_q(100, -30)] * 4, market_cap=280)
    assert raw == pytest.approx(280 / 280)          # FCF=280 → 1.0, not 280/520


def test_compute_p_fcf_nonpositive_fcf_and_adj_independent() -> None:
    # FCF>0 but FCF−SBC<0 → raw has value, adj None (independent)
    quarters = [_cf_q(20, -10, 25)] * 4             # FCF=40, SBC=100 → adj denom -60
    raw, adj = _compute_p_fcf(quarters, market_cap=400)
    assert raw == pytest.approx(400 / 40)           # 10.0
    assert adj is None

    # FCF≤0 → raw None (and adj None too)
    raw2, adj2 = _compute_p_fcf([_cf_q(10, -20)] * 4, market_cap=400)  # FCF=-40
    assert raw2 is None
    assert adj2 is None


def test_compute_p_fcf_degrades_on_insufficient_or_missing() -> None:
    # < 4 quarters → (None, None)
    assert _compute_p_fcf([_cf_q(100, -30)] * 3, market_cap=700) == (None, None)
    # a quarter missing capex → (None, None)
    bad = [_cf_q(100, -30)] * 3 + [{"operatingCashFlow": 100}]
    assert _compute_p_fcf(bad, market_cap=700) == (None, None)
    # SBC missing → treated as 0 → adj == raw
    raw, adj = _compute_p_fcf([_cf_q(100, -30)] * 4, market_cap=700)
    assert raw == pytest.approx(2.5)
    assert adj == pytest.approx(2.5)


def test_compute_p_fcf_ocf_fallback_field() -> None:
    # operatingCashFlow absent → fall back to netCashProvidedByOperatingActivities
    quarters = [_cf_q(100, -30, ocf_key="netCashProvidedByOperatingActivities")] * 4
    raw, _ = _compute_p_fcf(quarters, market_cap=700)
    assert raw == pytest.approx(700 / 280)


def test_fundamentals_non_member_skips_cash_flow(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    # NMBR: not watchlist, not pool → pFcf null, cash flow never pulled
    fake_fmp.ratios_results["NMBR"] = {"priceToEarningsRatioTTM": 18.0}
    fake_fmp.key_metrics_results["NMBR"] = {"marketCap": 2_000_000_000}
    fake_fmp.cash_flow_results["NMBR"] = [_cf_q(100, -30, 10)] * 4  # present but ignored

    data = client.get("/api/stocks/NMBR/fundamentals").json()["data"]
    assert data["pFcfRaw"] is None
    assert data["pFcfAdj"] is None
    assert fake_fmp.cash_flow_calls == []           # gating short-circuits
    assert data["priceToEarnings"] == 18.0          # raw TTM metrics intact
    assert data["marketCap"] == 2_000_000_000


def test_fundamentals_pool_member_computes_p_fcf(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    # POOL: not in watchlist, but a trend-pool member → cash flow pulled
    _seed_pool(db_session, "POOL")
    fake_fmp.key_metrics_results["POOL"] = {"marketCap": 700}
    fake_fmp.cash_flow_results["POOL"] = [_cf_q(100, -30, 10)] * 4

    resp = client.get("/api/stocks/POOL/fundamentals")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["pFcfRaw"] == pytest.approx(700 / 280)
    assert data["pFcfAdj"] == pytest.approx(700 / 240)
    assert fake_fmp.cash_flow_calls == [("POOL", 4)]


def test_fundamentals_fail_open_on_cash_flow_error(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    # watchlist member but cash flow raises → pFcf null, endpoint still 200
    _seed_stock(db_session, "FAILX")
    fake_fmp.ratios_results["FAILX"] = {"priceToSalesRatioTTM": 9.0}
    fake_fmp.key_metrics_results["FAILX"] = {"marketCap": 1_000_000_000}
    fake_fmp.cash_flow_exc = httpx.HTTPError("boom")

    resp = client.get("/api/stocks/FAILX/fundamentals")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["pFcfRaw"] is None
    assert data["pFcfAdj"] is None
    assert data["priceToSales"] == 9.0              # raw metrics unaffected
    assert data["marketCap"] == 1_000_000_000


def test_fundamentals_fail_open_on_insufficient_quarters(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    _seed_stock(db_session, "SHRTQ")
    fake_fmp.key_metrics_results["SHRTQ"] = {"marketCap": 700}
    fake_fmp.cash_flow_results["SHRTQ"] = [_cf_q(100, -30, 10)] * 3  # only 3 quarters

    data = client.get("/api/stocks/SHRTQ/fundamentals").json()["data"]
    assert data["pFcfRaw"] is None
    assert data["pFcfAdj"] is None


def test_fundamentals_member_without_market_cap(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    # member but no marketCap → pFcf null, no division, cash flow not pulled
    _seed_stock(db_session, "NOMC")
    fake_fmp.ratios_results["NOMC"] = {"priceToEarningsRatioTTM": 12.0}
    fake_fmp.key_metrics_results["NOMC"] = {"returnOnCapitalEmployedTTM": 0.3}
    fake_fmp.cash_flow_results["NOMC"] = [_cf_q(100, -30, 10)] * 4

    data = client.get("/api/stocks/NOMC/fundamentals").json()["data"]
    assert data["marketCap"] is None
    assert data["pFcfRaw"] is None
    assert data["pFcfAdj"] is None
    assert fake_fmp.cash_flow_calls == []           # short-circuit on None market_cap
    assert data["priceToEarnings"] == 12.0


def test_fundamentals_response_has_camelcase_p_fcf_keys(
    client: TestClient, db_session: Session, fake_fmp
) -> None:
    _seed_stock(db_session, "CAML")
    fake_fmp.key_metrics_results["CAML"] = {"marketCap": 700}
    fake_fmp.cash_flow_results["CAML"] = [_cf_q(100, -30, 10)] * 4

    data = client.get("/api/stocks/CAML/fundamentals").json()["data"]
    assert "pFcfRaw" in data and "pFcfAdj" in data
    assert "sbcSensitiveFlag" not in data           # 砍掉，绝不出现
