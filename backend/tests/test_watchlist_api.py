"""Integration tests for F001-a Watchlist + Stock Search API (T1–T17), F110-a bulk add (TB1–TB9),
and F222-b color tag write path (TC1–TC7)."""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock


def _mk_stock(db: Session, ticker: str, is_active: bool = True) -> Stock:
    stock = Stock(
        ticker=ticker.upper(),
        name=f"{ticker.upper()} Inc.",
        exchange="NASDAQ",
        is_active=is_active,
        added_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _mk_bars(db: Session, stock_id: int, n: int) -> None:
    start = date(2025, 1, 1)
    for i in range(n):
        db.add(
            DailyBar(
                stock_id=stock_id,
                date=start + timedelta(days=i),
                open=100.0,
                high=101.0,
                low=99.0,
                close=100.0,
                volume=1_000_000,
            )
        )
    db.commit()


def _fmp_hit(ticker: str, name: str = "Apple Inc.", exchange: str = "NASDAQ", type_: str = "stock"):
    return {
        "symbol": ticker,
        "name": name,
        "exchangeShortName": exchange,
        "exchangeFullName": f"{exchange} Stock Exchange",
        "currency": "USD",
        "type": type_,
    }


# --- T1 ----------------------------------------------------------------------

def test_t1_get_empty_watchlist(client: TestClient) -> None:
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    body = r.json()
    assert body["data"] == []
    assert body["message"] == "success"


# --- T2 ----------------------------------------------------------------------

def test_t2_post_new_ticker(client: TestClient, fake_fmp, db_session: Session) -> None:
    fake_fmp.search_results = [_fmp_hit("AAPL")]
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 201
    data = r.json()["data"]
    assert data["ticker"] == "AAPL"
    assert data["dataStatus"] == "loading"

    stored = db_session.query(Stock).filter_by(ticker="AAPL").one()
    assert stored.is_active is True


# --- T3 ----------------------------------------------------------------------

def test_t3_post_lowercase_stored_as_upper(client: TestClient, fake_fmp, db_session: Session) -> None:
    fake_fmp.search_results = [_fmp_hit("AAPL")]
    r = client.post("/api/watchlist", json={"ticker": "aapl"})
    assert r.status_code == 201
    assert r.json()["data"]["ticker"] == "AAPL"
    assert db_session.query(Stock).filter_by(ticker="AAPL").count() == 1


# --- T4 ----------------------------------------------------------------------

def test_t4_post_duplicate_active(client: TestClient, fake_fmp, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    fake_fmp.search_results = [_fmp_hit("AAPL")]
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 409
    assert r.json()["error"]["code"] == "DUPLICATE"


# --- T5 ----------------------------------------------------------------------

def test_t5_post_reactivates_soft_deleted(client: TestClient, fake_fmp, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=False)
    fake_fmp.search_results = [_fmp_hit("AAPL")]
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 201

    db_session.expire_all()
    stored = db_session.query(Stock).filter_by(ticker="AAPL").one()
    assert stored.is_active is True


# --- T6 ----------------------------------------------------------------------

def test_t6_post_fmp_miss(client: TestClient, fake_fmp) -> None:
    fake_fmp.search_results = [_fmp_hit("MSFT")]  # wrong ticker
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# --- T7 ----------------------------------------------------------------------

def test_t7_post_fmp_raises(client: TestClient, fake_fmp) -> None:
    fake_fmp.search_exc = RuntimeError("boom")
    r = client.post("/api/watchlist", json={"ticker": "AAPL"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "EXTERNAL_API_ERROR"


# --- T8 ----------------------------------------------------------------------

def test_t8_post_missing_ticker_field(client: TestClient) -> None:
    r = client.post("/api/watchlist", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- T9 ----------------------------------------------------------------------

def test_t9_get_hides_soft_deleted_and_latest_signal_null(
    client: TestClient, db_session: Session
) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    _mk_stock(db_session, "MSFT", is_active=False)
    r = client.get("/api/watchlist")
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data) == 1
    assert data[0]["ticker"] == "AAPL"
    assert data[0]["latestSignal"] is None


# --- T10 ---------------------------------------------------------------------

@pytest.mark.parametrize(
    "n_bars,expected",
    [(0, "loading"), (100, "insufficient"), (200, "ready")],
)
def test_t10_data_status_derivation(
    client: TestClient, db_session: Session, n_bars: int, expected: str
) -> None:
    stock = _mk_stock(db_session, "AAPL", is_active=True)
    _mk_bars(db_session, stock.id, n_bars)

    r = client.get("/api/watchlist")
    assert r.status_code == 200
    assert r.json()["data"][0]["dataStatus"] == expected


# --- T11 ---------------------------------------------------------------------

def test_t11_delete_active_ticker(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    r = client.delete("/api/watchlist/AAPL")
    assert r.status_code == 200
    assert r.json()["data"] == {"ticker": "AAPL", "removed": True}

    db_session.expire_all()
    stored = db_session.query(Stock).filter_by(ticker="AAPL").one()
    assert stored.is_active is False


# --- T12 ---------------------------------------------------------------------

def test_t12_delete_case_insensitive(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    r = client.delete("/api/watchlist/aapl")
    assert r.status_code == 200


# --- T13 ---------------------------------------------------------------------

def test_t13_delete_nonexistent(client: TestClient) -> None:
    r = client.delete("/api/watchlist/XXX")
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# --- T14 ---------------------------------------------------------------------

def test_t14_search_forwards_results(client: TestClient, fake_fmp) -> None:
    fake_fmp.search_results = [
        _fmp_hit("AAPL", "Apple Inc.", "XNAS", "CS"),
        _fmp_hit("AA", "Alcoa Corp", "XNYS", "CS"),
    ]
    r = client.get("/api/stocks/search", params={"q": "AA"})
    assert r.status_code == 200
    data = r.json()["data"]
    assert [d["ticker"] for d in data] == ["AAPL", "AA"]
    assert fake_fmp.search_calls[-1][0] == "AA"


# --- T15 ---------------------------------------------------------------------

def test_t15_search_missing_q(client: TestClient) -> None:
    r = client.get("/api/stocks/search")
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- T16 ---------------------------------------------------------------------

def test_t16_search_limit_capped_to_20(client: TestClient, fake_fmp) -> None:
    fake_fmp.search_results = []
    r = client.get("/api/stocks/search", params={"q": "AA", "limit": 50})
    assert r.status_code == 200
    assert fake_fmp.search_calls[-1][1] == 20


# --- T17 ---------------------------------------------------------------------

def test_t17_search_fmp_raises(client: TestClient, fake_fmp) -> None:
    fake_fmp.search_exc = RuntimeError("boom")
    r = client.get("/api/stocks/search", params={"q": "AA"})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "EXTERNAL_API_ERROR"


# =============================================================================
# F110-a: POST /api/watchlist/bulk  (TB1–TB9)
# =============================================================================

# --- TB1 ---------------------------------------------------------------------

def test_tb1_bulk_add_all_new(client: TestClient, fake_fmp, db_session: Session) -> None:
    fake_fmp.search_results = [_fmp_hit("AAPL"), _fmp_hit("MSFT"), _fmp_hit("GOOGL")]
    r = client.post("/api/watchlist/bulk", json={"tickers": ["AAPL", "MSFT", "GOOGL"]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["added"]) == 3
    assert data["skippedDuplicate"] == []
    assert data["notFound"] == []
    assert {s["ticker"] for s in data["added"]} == {"AAPL", "MSFT", "GOOGL"}


# --- TB2 ---------------------------------------------------------------------

def test_tb2_bulk_one_duplicate(client: TestClient, fake_fmp, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    fake_fmp.search_results = [_fmp_hit("MSFT"), _fmp_hit("GOOGL")]
    r = client.post("/api/watchlist/bulk", json={"tickers": ["AAPL", "MSFT", "GOOGL"]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["added"]) == 2
    assert data["skippedDuplicate"] == ["AAPL"]
    assert data["notFound"] == []


# --- TB3 ---------------------------------------------------------------------

def test_tb3_bulk_one_not_found(client: TestClient, fake_fmp, db_session: Session) -> None:
    fake_fmp.search_results = [_fmp_hit("AAPL")]
    r = client.post("/api/watchlist/bulk", json={"tickers": ["AAPL", "FAKE"]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["added"]) == 1
    assert data["notFound"] == ["FAKE"]


# --- TB4 ---------------------------------------------------------------------

def test_tb4_bulk_mixed_all_buckets(client: TestClient, fake_fmp, db_session: Session) -> None:
    _mk_stock(db_session, "MSFT", is_active=True)
    fake_fmp.search_results = [_fmp_hit("AAPL")]
    r = client.post("/api/watchlist/bulk", json={"tickers": ["AAPL", "MSFT", "FAKE"]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["added"]) == 1
    assert data["added"][0]["ticker"] == "AAPL"
    assert data["skippedDuplicate"] == ["MSFT"]
    assert data["notFound"] == ["FAKE"]


# --- TB5 ---------------------------------------------------------------------

def test_tb5_bulk_case_insensitive(client: TestClient, fake_fmp, db_session: Session) -> None:
    fake_fmp.search_results = [_fmp_hit("AAPL"), _fmp_hit("MSFT")]
    r = client.post("/api/watchlist/bulk", json={"tickers": ["aapl", "msft"]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["added"]) == 2
    tickers = {s["ticker"] for s in data["added"]}
    assert tickers == {"AAPL", "MSFT"}


# --- TB6 ---------------------------------------------------------------------

def test_tb6_bulk_deduplicates_within_request(client: TestClient, fake_fmp, db_session: Session) -> None:
    fake_fmp.search_results = [_fmp_hit("AAPL")]
    r = client.post("/api/watchlist/bulk", json={"tickers": ["AAPL", "aapl", "AAPL"]})
    assert r.status_code == 200
    data = r.json()["data"]
    assert len(data["added"]) == 1
    assert db_session.query(__import__("app.models", fromlist=["Stock"]).Stock).filter_by(ticker="AAPL").count() == 1


# --- TB7 ---------------------------------------------------------------------

def test_tb7_bulk_empty_array_rejected(client: TestClient) -> None:
    r = client.post("/api/watchlist/bulk", json={"tickers": []})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- TB8 ---------------------------------------------------------------------

def test_tb8_bulk_over_200_rejected(client: TestClient) -> None:
    tickers = [f"T{i:04d}" for i in range(201)]
    r = client.post("/api/watchlist/bulk", json={"tickers": tickers})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- TB9 ---------------------------------------------------------------------

def test_tb9_bulk_fmp_error_aborts_batch(client: TestClient, fake_fmp, db_session: Session) -> None:
    fake_fmp.search_exc = RuntimeError("network failure")
    r = client.post("/api/watchlist/bulk", json={"tickers": ["AAPL", "MSFT"]})
    assert r.status_code == 502
    assert r.json()["error"]["code"] == "EXTERNAL_API_ERROR"


# =============================================================================
# F222-b: PUT /api/watchlist/{ticker}/color (TC1–TC7)
# =============================================================================

# --- TC1 ---------------------------------------------------------------------

def test_tc1_put_color_sets_red(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    r = client.put("/api/watchlist/AAPL/color", json={"color": "red"})
    assert r.status_code == 200
    assert r.json()["data"] == {"ticker": "AAPL", "labelColor": "red"}

    db_session.expire_all()
    stored = db_session.query(Stock).filter_by(ticker="AAPL").one()
    assert stored.label_color == "red"


# --- TC2 ---------------------------------------------------------------------

def test_tc2_put_color_null_clears(client: TestClient, db_session: Session) -> None:
    stock = _mk_stock(db_session, "AAPL", is_active=True)
    stock.label_color = "blue"
    db_session.commit()

    r = client.put("/api/watchlist/AAPL/color", json={"color": None})
    assert r.status_code == 200
    assert r.json()["data"]["labelColor"] is None

    db_session.expire_all()
    stored = db_session.query(Stock).filter_by(ticker="AAPL").one()
    assert stored.label_color is None


# --- TC3 ---------------------------------------------------------------------

def test_tc3_put_color_case_insensitive(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    r = client.put("/api/watchlist/aapl/color", json={"color": "yellow"})
    assert r.status_code == 200
    assert r.json()["data"]["ticker"] == "AAPL"


# --- TC4 ---------------------------------------------------------------------

def test_tc4_put_color_invalid_enum(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    r = client.put("/api/watchlist/AAPL/color", json={"color": "green"})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"


# --- TC5 ---------------------------------------------------------------------

def test_tc5_put_color_ticker_never_added(client: TestClient) -> None:
    r = client.put("/api/watchlist/XXX/color", json={"color": "red"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# --- TC6 ---------------------------------------------------------------------

def test_tc6_put_color_soft_deleted_ticker(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=False)
    r = client.put("/api/watchlist/AAPL/color", json={"color": "red"})
    assert r.status_code == 404
    assert r.json()["error"]["code"] == "NOT_FOUND"


# --- TC7 ---------------------------------------------------------------------

def test_tc7_put_color_missing_color_field(client: TestClient, db_session: Session) -> None:
    _mk_stock(db_session, "AAPL", is_active=True)
    r = client.put("/api/watchlist/AAPL/color", json={})
    assert r.status_code == 422
    assert r.json()["error"]["code"] == "VALIDATION_ERROR"
