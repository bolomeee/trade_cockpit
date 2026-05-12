"""F206-a §B: PositionRepository unit tests (SQLite in-memory)."""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.models.position import Position
from app.repositories.position_repository import PositionRepository


def _make_payload(**overrides) -> dict:
    base = dict(
        ticker="AAPL",
        entry_price=150.0,
        entry_date=date(2026, 4, 1),
        shares=100,
        stop_price=140.0,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# B1: create + get_by_id round-trip
# ---------------------------------------------------------------------------

def test_create_and_get_by_id(db_session):
    repo = PositionRepository(db_session)
    row = repo.create(_make_payload())

    assert row.id is not None
    assert row.ticker == "AAPL"
    assert row.status == "OPEN"
    assert row.created_at is not None

    fetched = repo.get_by_id(row.id)
    assert fetched is not None
    assert fetched.id == row.id
    assert fetched.entry_price == 150.0


# ---------------------------------------------------------------------------
# B2: list_by_status filters correctly
# ---------------------------------------------------------------------------

def test_list_by_status_open_closed(db_session):
    repo = PositionRepository(db_session)
    open_row = repo.create(_make_payload(ticker="NVDA"))
    closed_row = repo.create(_make_payload(ticker="MSFT"))

    # manually close second row
    repo.update(closed_row.id, {
        "status": "CLOSED",
        "close_price": 160.0,
        "closed_at": datetime.now(timezone.utc),
    })

    open_list = repo.list_by_status("open")
    closed_list = repo.list_by_status("closed")
    all_list = repo.list_by_status("all")

    assert len(open_list) == 1
    assert open_list[0].ticker == "NVDA"
    assert len(closed_list) == 1
    assert closed_list[0].ticker == "MSFT"
    assert len(all_list) == 2


# ---------------------------------------------------------------------------
# B3: update modifies fields and refreshes updated_at
# ---------------------------------------------------------------------------

def test_update_modifies_fields(db_session):
    repo = PositionRepository(db_session)
    row = repo.create(_make_payload())
    original_updated = row.updated_at

    updated = repo.update(row.id, {"stop_price": 145.0, "notes": "raised stop"})
    assert updated is not None
    assert updated.stop_price == 145.0
    assert updated.notes == "raised stop"
    # updated_at should be refreshed (or at least not earlier)
    assert updated.updated_at >= original_updated


# ---------------------------------------------------------------------------
# B4: delete removes row; get_by_id returns None afterwards
# ---------------------------------------------------------------------------

def test_delete_returns_true_and_removes_row(db_session):
    repo = PositionRepository(db_session)
    row = repo.create(_make_payload())

    result = repo.delete(row.id)
    assert result is True
    assert repo.get_by_id(row.id) is None


# ---------------------------------------------------------------------------
# B5: get_by_id / delete on non-existent id
# ---------------------------------------------------------------------------

def test_nonexistent_id_returns_none_false(db_session):
    repo = PositionRepository(db_session)
    assert repo.get_by_id(9999) is None
    assert repo.delete(9999) is False
    assert repo.update(9999, {"notes": "x"}) is None
