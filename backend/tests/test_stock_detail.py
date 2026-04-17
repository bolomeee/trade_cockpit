from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

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
    # Build bars that transition from uptrend then dip to trigger pullbacks
    closes = [100.0 + i * 0.2 for i in range(160)]
    for offset in (-5, -15):
        closes[offset] = closes[offset - 1] * 0.99
    _seed_bars(db_session, stock.id, closes)
    _recompute(db_session, stock.id)

    resp = client.get("/api/stocks/DDD/pullbacks")
    assert resp.status_code == 200
    rows = resp.json()["data"]

    dates = [r["date"] for r in rows]
    assert dates == sorted(dates, reverse=True)
    if rows:
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
            assert field in row


def test_fundamentals_returns_mock_payload(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "EEE")

    resp = client.get("/api/stocks/EEE/fundamentals")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "EEE"
    assert data["source"] == "mock"
    for field in (
        "priceToEarnings",
        "priceToSales",
        "peg",
        "freeCashFlow",
        "marketCap",
        "updatedAt",
    ):
        assert field in data
    assert isinstance(data["priceToEarnings"], (int, float))


def test_fundamentals_deterministic_per_ticker(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "FFF")
    r1 = client.get("/api/stocks/FFF/fundamentals").json()["data"]
    r2 = client.get("/api/stocks/FFF/fundamentals").json()["data"]
    assert r1["priceToEarnings"] == r2["priceToEarnings"]
    assert r1["marketCap"] == r2["marketCap"]


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
