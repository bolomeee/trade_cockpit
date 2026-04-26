"""F206-b1 §B: PendingOrderRepository unit tests (SQLite in-memory)."""
from __future__ import annotations

import time
from datetime import date, datetime, timezone

import pytest

from app.repositories.pending_order_repository import PendingOrderRepository


def _make_payload(**overrides) -> dict:
    base = dict(
        ticker="NVDA",
        setup_type="BREAKOUT",
        entry_price=180.0,
        stop_price=173.0,
        shares=40,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# B1: create + get_by_id round-trip
# ---------------------------------------------------------------------------

def test_create_and_get_by_id(db_session):
    repo = PendingOrderRepository(db_session)
    row = repo.create(_make_payload())

    assert row.id is not None
    assert row.ticker == "NVDA"
    assert row.status == "ACTIVE"
    assert row.created_at is not None

    fetched = repo.get_by_id(row.id)
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.entry_price == 180.0


# ---------------------------------------------------------------------------
# B2: list_by_status("active") returns only ACTIVE rows
# ---------------------------------------------------------------------------

def test_list_by_status_active_only(db_session):
    repo = PendingOrderRepository(db_session)
    active_row = repo.create(_make_payload(ticker="NVDA"))
    triggered_row = repo.create(_make_payload(ticker="AAPL"))
    repo.update(triggered_row.id, {"status": "TRIGGERED"})

    active_list = repo.list_by_status("ACTIVE")
    assert len(active_list) == 1
    assert active_list[0].ticker == "NVDA"


# ---------------------------------------------------------------------------
# B3: list_by_status("all") returns all rows regardless of status
# ---------------------------------------------------------------------------

def test_list_by_status_all_returns_all(db_session):
    repo = PendingOrderRepository(db_session)
    r1 = repo.create(_make_payload(ticker="NVDA"))
    r2 = repo.create(_make_payload(ticker="AAPL"))
    repo.update(r2.id, {"status": "EXPIRED"})
    r3 = repo.create(_make_payload(ticker="MSFT"))
    repo.update(r3.id, {"status": "CANCELLED"})

    all_rows = repo.list_by_status("all")
    assert len(all_rows) == 3


# ---------------------------------------------------------------------------
# B4: list_by_status filters specific non-ACTIVE statuses
# ---------------------------------------------------------------------------

def test_list_by_status_specific_status(db_session):
    repo = PendingOrderRepository(db_session)
    r1 = repo.create(_make_payload(ticker="NVDA"))
    repo.update(r1.id, {"status": "TRIGGERED"})

    r2 = repo.create(_make_payload(ticker="AAPL"))
    repo.update(r2.id, {"status": "EXPIRED"})

    repo.create(_make_payload(ticker="MSFT"))  # stays ACTIVE

    triggered = repo.list_by_status("TRIGGERED")
    assert len(triggered) == 1
    assert triggered[0].ticker == "NVDA"

    expired = repo.list_by_status("EXPIRED")
    assert len(expired) == 1
    assert expired[0].ticker == "AAPL"


# ---------------------------------------------------------------------------
# B5: update auto-refreshes updated_at
# ---------------------------------------------------------------------------

def test_update_refreshes_updated_at(db_session):
    repo = PendingOrderRepository(db_session)
    row = repo.create(_make_payload())
    original_updated = row.updated_at

    # Brief pause ensures a measurable time difference
    time.sleep(0.01)

    updated = repo.update(row.id, {"stop_price": 175.0, "notes": "tighter stop"})
    assert updated is not None
    assert updated.stop_price == 175.0
    assert updated.notes == "tighter stop"
    assert updated.updated_at > original_updated
