from __future__ import annotations

from datetime import date

from app.repositories.market_index_repository import MarketIndexRepository


def test_overview_empty(client):
    resp = client.get("/api/market/overview")
    assert resp.status_code == 200
    body = resp.json()
    assert body == {"data": [], "message": "success"}


def test_overview_returns_three_in_order(client, db_session):
    repo = MarketIndexRepository(db_session)
    # Insert in non-canonical order to verify API ordering.
    repo.upsert("TNX", "10-Year Treasury Yield", date(2026, 4, 15), 4.25, 4.22, 0.71)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 15), 5200.5, 5180.2, 0.39)
    repo.upsert("NDX", "NASDAQ 100", date(2026, 4, 15), 18200.3, 18050.1, 0.83)

    resp = client.get("/api/market/overview")
    assert resp.status_code == 200
    data = resp.json()["data"]
    assert [d["symbol"] for d in data] == ["SPX", "NDX", "TNX"]

    spx = data[0]
    assert set(spx.keys()) == {"symbol", "name", "close", "prevClose", "changePct", "date"}
    assert spx["name"] == "S&P 500"
    assert spx["close"] == 5200.5
    assert spx["prevClose"] == 5180.2
    assert spx["changePct"] == 0.39
    assert spx["date"] == "2026-04-15"


def test_overview_partial_symbols(client, db_session):
    MarketIndexRepository(db_session).upsert(
        "SPX", "S&P 500", date(2026, 4, 15), 5200.5, None, None
    )
    resp = client.get("/api/market/overview")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["symbol"] == "SPX"
    assert data[0]["prevClose"] is None
    assert data[0]["changePct"] is None


def test_overview_latest_per_symbol(client, db_session):
    repo = MarketIndexRepository(db_session)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 14), 5100.0, 5090.0, 0.2)
    repo.upsert("SPX", "S&P 500", date(2026, 4, 15), 5200.0, 5100.0, 1.96)
    resp = client.get("/api/market/overview")
    data = resp.json()["data"]
    assert len(data) == 1
    assert data[0]["date"] == "2026-04-15"
    assert data[0]["close"] == 5200.0
