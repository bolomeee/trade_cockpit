from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock
from app.services.signal_engine import (
    SIGNAL_BUY_ZONE,
    SIGNAL_NEUTRAL,
)
from app.services.signal_service import SignalService


def _seed_stock(db: Session, ticker: str) -> Stock:
    stock = Stock(
        ticker=ticker,
        name=f"{ticker} Inc.",
        exchange="NASDAQ",
        is_active=True,
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
                high=c,
                low=c,
                close=c,
                volume=1000,
            )
        )
    db.commit()


def _recompute_all(db: Session) -> None:
    service = SignalService(db)
    for stock in db.query(Stock).all():
        service.recompute_for_stock(stock.id)


def test_get_signals_returns_sorted_board(
    client: TestClient, db_session: Session
) -> None:
    bz = _seed_stock(db_session, "AAA")
    neu = _seed_stock(db_session, "BBB")
    _seed_bars(db_session, bz.id, [100.0 + i * 0.05 for i in range(200)])
    _seed_bars(db_session, neu.id, [200.0 - i * 0.1 for i in range(200)])
    _recompute_all(db_session)

    resp = client.get("/api/signals")
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "success"
    tickers = [item["ticker"] for item in body["data"]]
    assert tickers == ["AAA", "BBB"]
    first = body["data"][0]
    assert first["signalType"] == SIGNAL_BUY_ZONE
    assert "closePrice" in first
    assert "ma150Value" in first
    assert "distancePct" in first
    assert "slopePositive" in first
    assert body["data"][1]["signalType"] == SIGNAL_NEUTRAL


def test_get_signals_empty_when_no_stocks(client: TestClient) -> None:
    resp = client.get("/api/signals")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_signals_skips_stocks_without_signals(
    client: TestClient, db_session: Session
) -> None:
    _seed_stock(db_session, "AAA")
    resp = client.get("/api/signals")
    assert resp.status_code == 200
    assert resp.json()["data"] == []


def test_get_ticker_signal_returns_latest_and_history(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "AAPL")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(200)])
    _recompute_all(db_session)

    resp = client.get("/api/signals/AAPL?days=5")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert data["ticker"] == "AAPL"
    assert data["name"] == "AAPL Inc."
    assert data["latest"] is not None
    assert len(data["history"]) == 5
    entry = data["history"][0]
    for field in ("date", "signalType", "closePrice", "ma150Value", "distancePct"):
        assert field in entry


def test_get_ticker_signal_defaults_to_30_days(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "AAPL")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(200)])
    _recompute_all(db_session)

    resp = client.get("/api/signals/AAPL")
    assert resp.status_code == 200
    assert len(resp.json()["data"]["history"]) == 30


def test_get_ticker_signal_is_case_insensitive(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "AAPL")
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(200)])
    _recompute_all(db_session)

    resp = client.get("/api/signals/aapl")
    assert resp.status_code == 200


def test_get_ticker_signal_404_when_missing(client: TestClient) -> None:
    resp = client.get("/api/signals/ZZZZ")
    assert resp.status_code == 404
    body = resp.json()
    assert body["error"]["code"] == "NOT_FOUND"


def test_get_ticker_signal_404_when_inactive(
    client: TestClient, db_session: Session
) -> None:
    stock = _seed_stock(db_session, "XXX")
    stock.is_active = False
    db_session.commit()
    resp = client.get("/api/signals/XXX")
    assert resp.status_code == 404


def test_get_ticker_signal_rejects_days_above_max(client: TestClient) -> None:
    resp = client.get("/api/signals/AAPL?days=300")
    assert resp.status_code == 422
    assert resp.json()["error"]["code"] == "VALIDATION_ERROR"


def test_get_ticker_signal_rejects_zero_days(client: TestClient) -> None:
    resp = client.get("/api/signals/AAPL?days=0")
    assert resp.status_code == 422
