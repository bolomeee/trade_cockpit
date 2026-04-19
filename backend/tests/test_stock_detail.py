from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock
from app.repositories.pullback_repository import PullbackRepository
from app.services.signal_service import SignalService


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
    for path in ("chart", "pullbacks", "fundamentals"):
        resp = client.get(f"/api/stocks/ZZZZ/{path}")
        assert resp.status_code == 404, path
        assert resp.json()["error"]["code"] == "NOT_FOUND"


def test_detail_endpoints_404_when_ticker_inactive(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "INAC", is_active=False)
    for path in ("chart", "pullbacks", "fundamentals"):
        resp = client.get(f"/api/stocks/INAC/{path}")
        assert resp.status_code == 404, path


def test_detail_endpoints_are_case_insensitive(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "GGG")
    for path in ("chart", "pullbacks", "fundamentals"):
        resp = client.get(f"/api/stocks/ggg/{path}")
        assert resp.status_code == 200, path


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
