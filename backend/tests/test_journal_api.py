"""Integration tests for F007-a Journal API."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import JournalEntry, Stock


def _mk_stock(db: Session, ticker: str, name: str | None = None, is_active: bool = True) -> Stock:
    stock = Stock(
        ticker=ticker.upper(),
        name=name or f"{ticker.upper()} Inc.",
        exchange="NASDAQ",
        is_active=is_active,
        added_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _mk_entry(
    db: Session,
    stock_id: int,
    action: str = "BUY",
    price: float = 100.0,
    d: date | None = None,
    **extra,
) -> JournalEntry:
    entry = JournalEntry(
        stock_id=stock_id,
        action=action,
        price=price,
        date=d or date(2026, 4, 10),
        **extra,
    )
    db.add(entry)
    db.commit()
    db.refresh(entry)
    return entry


def _valid_payload(ticker: str = "AAPL", **overrides) -> dict:
    payload = {
        "ticker": ticker,
        "action": "BUY",
        "price": 182.50,
        "date": "2026-04-10",
        "positionSize": 50,
        "stopLoss": 175.00,
        "targetPrice": 200.00,
        "reason": "MA150 bounce",
        "reference": "detailed notes",
    }
    payload.update(overrides)
    return payload


# --- T1: empty list --------------------------------------------------------

def test_t1_get_empty(client: TestClient) -> None:
    r = client.get("/api/journal")
    assert r.status_code == 200
    data = r.json()["data"]
    assert data == {"items": [], "total": 0, "limit": 50, "offset": 0}


# --- T2: list ordering + camelCase + stockName -----------------------------

def test_t2_list_order_and_fields(client: TestClient, db_session: Session) -> None:
    aapl = _mk_stock(db_session, "AAPL", "Apple Inc.")
    nvda = _mk_stock(db_session, "NVDA", "NVIDIA Corp.")
    _mk_entry(db_session, aapl.id, d=date(2026, 4, 1))
    _mk_entry(db_session, nvda.id, d=date(2026, 4, 10))
    _mk_entry(db_session, aapl.id, d=date(2026, 4, 5))

    r = client.get("/api/journal")
    assert r.status_code == 200
    items = r.json()["data"]["items"]
    assert [i["date"] for i in items] == ["2026-04-10", "2026-04-05", "2026-04-01"]
    assert items[0]["ticker"] == "NVDA"
    assert items[0]["stockName"] == "NVIDIA Corp."
    assert "positionSize" in items[0]
    assert "createdAt" in items[0]


# --- T3: ticker filter -----------------------------------------------------

def test_t3_filter_by_ticker(client: TestClient, db_session: Session) -> None:
    aapl = _mk_stock(db_session, "AAPL")
    nvda = _mk_stock(db_session, "NVDA")
    _mk_entry(db_session, aapl.id)
    _mk_entry(db_session, nvda.id)

    r = client.get("/api/journal?ticker=AAPL")
    data = r.json()["data"]
    assert data["total"] == 1
    assert all(i["ticker"] == "AAPL" for i in data["items"])


# --- T4: action filter -----------------------------------------------------

def test_t4_filter_by_action(client: TestClient, db_session: Session) -> None:
    aapl = _mk_stock(db_session, "AAPL")
    _mk_entry(db_session, aapl.id, action="BUY")
    _mk_entry(db_session, aapl.id, action="SELL")
    _mk_entry(db_session, aapl.id, action="BUY")

    r = client.get("/api/journal?action=BUY")
    data = r.json()["data"]
    assert data["total"] == 2
    assert all(i["action"] == "BUY" for i in data["items"])


# --- T5: pagination --------------------------------------------------------

def test_t5_pagination(client: TestClient, db_session: Session) -> None:
    aapl = _mk_stock(db_session, "AAPL")
    for i in range(5):
        _mk_entry(db_session, aapl.id, d=date(2026, 4, 1 + i))

    r = client.get("/api/journal?limit=2&offset=1")
    data = r.json()["data"]
    assert data["total"] == 5
    assert data["limit"] == 2
    assert data["offset"] == 1
    assert len(data["items"]) == 2
    # date-desc sorted: indices 0..4 -> 4/5, 4/4, 4/3, 4/2, 4/1; offset=1 → 4/4, 4/3
    assert [i["date"] for i in data["items"]] == ["2026-04-04", "2026-04-03"]


# --- T6: POST creates 201 with full entry ---------------------------------

def test_t6_post_creates(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", "Apple Inc.")
    r = client.post("/api/journal", json=_valid_payload())
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["ticker"] == "AAPL"
    assert data["stockName"] == "Apple Inc."
    assert data["action"] == "BUY"
    assert data["positionSize"] == 50
    assert data["stopLoss"] == 175.00
    assert data["targetPrice"] == 200.00
    assert "createdAt" in data
    assert "updatedAt" in data


# --- T7: POST ticker not in watchlist → 404 -------------------------------

def test_t7_post_unknown_ticker_404(client: TestClient) -> None:
    r = client.post("/api/journal", json=_valid_payload(ticker="ZZZZ"))
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


def test_t7b_post_inactive_ticker_404(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "OLD", is_active=False)
    r = client.post("/api/journal", json=_valid_payload(ticker="OLD"))
    assert r.status_code == 404


# --- T8: action illegal → 422 ---------------------------------------------

def test_t8_post_bad_action(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL")
    r = client.post("/api/journal", json=_valid_payload(action="INVALID"))
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- T9: missing required fields → 422 ------------------------------------

@pytest.mark.parametrize("missing", ["ticker", "action", "price", "date"])
def test_t9_post_missing_required(client: TestClient, db_session: Session, missing: str) -> None:
    _mk_stock(db_session, "AAPL")
    payload = _valid_payload()
    payload.pop(missing)
    r = client.post("/api/journal", json=payload)
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- T10: PUT partial update --------------------------------------------

def test_t10_put_partial_update(client: TestClient, db_session: Session) -> None:
    aapl = _mk_stock(db_session, "AAPL")
    entry = _mk_entry(db_session, aapl.id, action="BUY", price=100.0, reason="old")
    original_updated = entry.updated_at

    r = client.put(f"/api/journal/{entry.id}", json={"price": 150.0})
    assert r.status_code == 200
    data = r.json()["data"]
    assert data["price"] == 150.0
    assert data["action"] == "BUY"  # unchanged
    assert data["reason"] == "old"  # unchanged

    db_session.expire_all()
    refreshed = db_session.query(JournalEntry).filter_by(id=entry.id).one()
    assert refreshed.updated_at >= original_updated


# --- T11: PUT non-existent id → 404 --------------------------------------

def test_t11_put_not_found(client: TestClient) -> None:
    r = client.put("/api/journal/9999", json={"price": 150.0})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# --- T12: DELETE success --------------------------------------------------

def test_t12_delete_success(client: TestClient, db_session: Session) -> None:
    aapl = _mk_stock(db_session, "AAPL")
    entry = _mk_entry(db_session, aapl.id)
    r = client.delete(f"/api/journal/{entry.id}")
    assert r.status_code == 200
    assert r.json()["data"] == {"id": entry.id, "deleted": True}
    assert db_session.query(JournalEntry).filter_by(id=entry.id).count() == 0


# --- T13: DELETE non-existent → 404 --------------------------------------

def test_t13_delete_not_found(client: TestClient) -> None:
    r = client.delete("/api/journal/9999")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# --- extra: ticker case-insensitive lookup -------------------------------

def test_ticker_case_insensitive(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL")
    r = client.post("/api/journal", json=_valid_payload(ticker="aapl"))
    assert r.status_code == 201
    assert r.json()["data"]["ticker"] == "AAPL"


# --- extra: action enum accepted in filter -------------------------------

def test_filter_action_case_insensitive(client: TestClient, db_session: Session) -> None:
    aapl = _mk_stock(db_session, "AAPL")
    _mk_entry(db_session, aapl.id, action="BUY")
    r = client.get("/api/journal?action=buy")
    assert r.status_code == 200
    assert r.json()["data"]["total"] == 1
