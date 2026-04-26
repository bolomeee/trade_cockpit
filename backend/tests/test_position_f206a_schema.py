"""F206-a §A: Pydantic schema unit tests."""
from __future__ import annotations

from datetime import date, datetime, timezone, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.cockpit.position import PositionCreate, PositionItem, PositionUpdate


# ---------------------------------------------------------------------------
# A1: PositionCreate valid case
# ---------------------------------------------------------------------------

def test_position_create_valid():
    p = PositionCreate(
        ticker="NVDA",
        entryPrice=850.0,
        entryDate=date(2026, 4, 1),
        shares=33,
        stopPrice=820.0,
        setupType="BREAKOUT",
    )
    assert p.ticker == "NVDA"
    assert p.entry_price == 850.0
    assert p.shares == 33


# ---------------------------------------------------------------------------
# A2: Required fields — missing ticker should raise
# ---------------------------------------------------------------------------

def test_position_create_missing_required():
    with pytest.raises(ValidationError):
        PositionCreate(
            entryPrice=850.0,
            entryDate=date(2026, 4, 1),
            shares=33,
            stopPrice=820.0,
        )


# ---------------------------------------------------------------------------
# A3: entry_price <= stop_price raises ValidationError
# ---------------------------------------------------------------------------

def test_position_create_entry_le_stop():
    with pytest.raises(ValidationError, match="entryPrice must be greater than stopPrice"):
        PositionCreate(
            ticker="NVDA",
            entryPrice=800.0,   # <= stopPrice
            entryDate=date(2026, 4, 1),
            shares=33,
            stopPrice=820.0,
        )


# ---------------------------------------------------------------------------
# A4: shares <= 0 raises ValidationError
# ---------------------------------------------------------------------------

def test_position_create_shares_zero():
    with pytest.raises(ValidationError):
        PositionCreate(
            ticker="NVDA",
            entryPrice=850.0,
            entryDate=date(2026, 4, 1),
            shares=0,
            stopPrice=820.0,
        )


# ---------------------------------------------------------------------------
# A5: PositionUpdate status=CLOSED without closedAt/closePrice raises
# ---------------------------------------------------------------------------

def test_position_update_closed_missing_metadata():
    with pytest.raises(ValidationError, match="closedAt and closePrice"):
        PositionUpdate(status="CLOSED")


def test_position_update_closed_with_metadata():
    u = PositionUpdate(
        status="CLOSED",
        closedAt=datetime.now(timezone.utc),
        closePrice=900.0,
    )
    assert u.status == "CLOSED"


# ---------------------------------------------------------------------------
# A6: D074 camelCase serialization
# ---------------------------------------------------------------------------

def test_position_create_camel_serialization():
    p = PositionCreate(
        ticker="AAPL",
        entryPrice=150.0,
        entryDate=date(2026, 4, 1),
        shares=100,
        stopPrice=140.0,
    )
    dumped = p.model_dump(by_alias=True)
    assert "entryPrice" in dumped
    assert "stopPrice" in dumped
    assert "entryDate" in dumped
    assert "entry_price" not in dumped


# ---------------------------------------------------------------------------
# A7: entry_date future date raises ValidationError
# ---------------------------------------------------------------------------

def test_position_create_future_date():
    future = date.today() + timedelta(days=1)
    with pytest.raises(ValidationError, match="future date"):
        PositionCreate(
            ticker="AAPL",
            entryPrice=150.0,
            entryDate=future,
            shares=100,
            stopPrice=140.0,
        )
