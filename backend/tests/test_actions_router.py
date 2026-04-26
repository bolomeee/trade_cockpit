"""F207-a: integration tests for GET /api/cockpit/actions/today."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from app.models.daily_bar import DailyBar
from app.models.earnings_event import EarningsEvent
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock

_URL = "/api/cockpit/actions/today"

_POS_BASE = {
    "entryDate": "2026-01-01",
    "shares": 100,
}

_ORDER_BASE = {
    "setupType": "BREAKOUT",
    "shares": 50,
}


def _create_pos(client, **kw) -> dict:
    payload = {**_POS_BASE, **kw}
    resp = client.post("/api/cockpit/positions", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _create_order(client, **kw) -> dict:
    payload = {**_ORDER_BASE, **kw}
    resp = client.post("/api/cockpit/pending-orders", json=payload)
    assert resp.status_code == 201, resp.text
    return resp.json()["data"]


def _seed_last_close(db_session, ticker: str, close: float) -> None:
    """Insert a stock + latest daily_bar so LastCloseLoader picks it up via SQL."""
    stock = Stock(ticker=ticker, name=ticker)
    db_session.add(stock)
    db_session.flush()
    bar = DailyBar(
        stock_id=stock.id, date=date.today(),
        open=close, high=close, low=close, close=close, volume=1_000_000,
    )
    db_session.add(bar)
    db_session.commit()


def _seed_regime(db_session, regime: str) -> None:
    row = MarketRegimeSnapshot(regime=regime, recorded_date=date.today())
    db_session.add(row)
    db_session.commit()


def _seed_setup(db_session, ticker: str, setup_type: str) -> None:
    row = SetupSnapshot(
        ticker=ticker,
        setup_type=setup_type,
        scan_date=date.today(),
        earnings_risk="LOW",
        ready_signal=False,
    )
    db_session.add(row)
    db_session.commit()


def _seed_earnings(db_session, ticker: str, days: int) -> None:
    row = EarningsEvent(
        ticker=ticker,
        earnings_date=date.today() + timedelta(days=days),
    )
    db_session.add(row)
    db_session.commit()


# ── I1: GET empty DB → 200 + all lists empty + asOfDate is ISO date ──────────

def test_i1_empty_db_returns_200_with_empty_lists(client):
    resp = client.get(_URL)
    assert resp.status_code == 200
    body = resp.json()
    assert body["message"] == "success"
    data = body["data"]
    assert data["mustAct"] == []
    assert data["monitor"] == []
    assert data["noAction"] == []
    # asOfDate is a valid ISO date string
    assert len(data["asOfDate"]) == 10  # YYYY-MM-DD
    date.fromisoformat(data["asOfDate"])  # must not raise


# ── I2: 2 OPEN positions → mustAct raise_stop / noAction stable ───────────────

def test_i2_two_positions_stable_and_raise(client, db_session):
    # AAPL: entry=150, stop=140, last_close=175 → R=2.5 → raise_stop
    # MSFT: entry=150, stop=140, last_close=158 → R=0.8 → stable
    _seed_last_close(db_session, "AAPL", 175.0)
    _seed_last_close(db_session, "MSFT", 158.0)

    _create_pos(client, ticker="AAPL", entryPrice=150.0, stopPrice=140.0)
    _create_pos(client, ticker="MSFT", entryPrice=150.0, stopPrice=140.0)

    resp = client.get(_URL)
    assert resp.status_code == 200
    data = resp.json()["data"]

    must_types = {x["actionType"] for x in data["mustAct"]}
    no_types = {x["actionType"] for x in data["noAction"]}

    assert "raise_stop" in must_types
    assert "stable_position" in no_types
    assert data["monitor"] == []


# ── I3: ACTIVE pending order distance≈1% → monitor approaching_trigger ────────

def test_i3_approaching_trigger_in_monitor(client, db_session):
    # entry=100, last_close=99 → distance = (99-100)/100*100 = -1.0%
    _seed_last_close(db_session, "NVDA", 99.0)
    _create_order(client, ticker="NVDA", entryPrice=100.0, stopPrice=90.0)

    resp = client.get(_URL)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert len(data["monitor"]) == 1
    item = data["monitor"][0]
    assert item["actionType"] == "approaching_trigger"
    assert item["refs"]["distancePct"] < 0  # distance is negative


# ── I4: pending order + BROKEN setup → mustAct cancel_order ──────────────────

def test_i4_broken_setup_cancel_order(client, db_session):
    _create_order(client, ticker="TSLA", entryPrice=300.0, stopPrice=270.0)
    _seed_setup(db_session, "TSLA", "BROKEN")

    resp = client.get(_URL)
    assert resp.status_code == 200
    data = resp.json()["data"]

    assert len(data["mustAct"]) >= 1
    assert data["mustAct"][0]["actionType"] == "cancel_order"


# ── I5: schema — camelCase fields, 4 item fields present ─────────────────────

def test_i5_response_schema_camel_case(client, db_session):
    _seed_last_close(db_session, "GOOG", 155.0)
    _create_pos(client, ticker="GOOG", entryPrice=150.0, stopPrice=140.0)

    resp = client.get(_URL)
    assert resp.status_code == 200
    body = resp.json()

    # Top-level keys
    assert "data" in body
    assert "message" in body

    data = body["data"]
    assert "asOfDate" in data
    assert "mustAct" in data
    assert "monitor" in data
    assert "noAction" in data

    # stable position → noAction has 1 item with 4 required fields
    for item in data["noAction"]:
        assert "ticker" in item
        assert "actionType" in item
        assert "rationale" in item
        assert "refs" in item


# ── I6: DB error → 500 + standard APIError body ───────────────────────────────

def test_i6_db_error_returns_500(client):
    with patch(
        "app.services.cockpit.action_service.ActionService.build_today_actions",
        side_effect=SQLAlchemyError("forced db error"),
    ):
        resp = client.get(_URL)

    assert resp.status_code == 500
    body = resp.json()
    assert "error" in body or "detail" in body  # APIError standard body
