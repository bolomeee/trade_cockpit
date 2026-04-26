"""F206-b1 §A: PendingOrder schema validation tests."""
from __future__ import annotations

from datetime import date, timedelta

import pytest
from pydantic import ValidationError

from app.schemas.cockpit.pending_order import PendingOrderCreate, PendingOrderUpdate, PendingOrderItem


def _valid_create(**overrides) -> dict:
    base = dict(
        ticker="NVDA",
        setupType="BREAKOUT",
        entryPrice=180.0,
        stopPrice=173.0,
        shares=40,
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# A1: missing required fields each trigger validation error
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("missing_field", ["ticker", "setupType", "entryPrice", "stopPrice", "shares"])
def test_create_missing_required_field(missing_field):
    payload = _valid_create()
    del payload[missing_field]
    with pytest.raises(ValidationError):
        PendingOrderCreate(**payload)


# ---------------------------------------------------------------------------
# A2: entry_price <= stop_price → validation error
# ---------------------------------------------------------------------------

def test_create_entry_le_stop():
    with pytest.raises(ValidationError, match="entryPrice"):
        PendingOrderCreate(**_valid_create(entryPrice=170.0, stopPrice=173.0))


# ---------------------------------------------------------------------------
# A3: shares <= 0 → validation error
# ---------------------------------------------------------------------------

def test_create_shares_not_positive():
    with pytest.raises(ValidationError):
        PendingOrderCreate(**_valid_create(shares=0))


# ---------------------------------------------------------------------------
# A4: expirationDate < today → validation error (Q4 default: reject past dates)
# ---------------------------------------------------------------------------

def test_create_expiration_date_in_past():
    past = date.today() - timedelta(days=1)
    with pytest.raises(ValidationError, match="expirationDate"):
        PendingOrderCreate(**_valid_create(expirationDate=str(past)))


# ---------------------------------------------------------------------------
# A5: invalid setupType → validation error
# ---------------------------------------------------------------------------

def test_create_invalid_setup_type():
    with pytest.raises(ValidationError):
        PendingOrderCreate(**_valid_create(setupType="INVALID_TYPE"))


# ---------------------------------------------------------------------------
# A6: PendingOrderUpdate with status=ACTIVE passes schema validation
#     (service layer, not schema, is responsible for state-machine enforcement)
# ---------------------------------------------------------------------------

def test_update_status_active_passes_schema():
    patch = PendingOrderUpdate(status="ACTIVE")
    assert patch.status == "ACTIVE"


# ---------------------------------------------------------------------------
# A7: PendingOrderUpdate paired entry/stop validation when both present
# ---------------------------------------------------------------------------

def test_update_paired_entry_stop_validation():
    with pytest.raises(ValidationError, match="entryPrice"):
        PendingOrderUpdate(entryPrice=170.0, stopPrice=175.0)


# ---------------------------------------------------------------------------
# A8: D074 camelCase serialization — dump produces aliased keys
# ---------------------------------------------------------------------------

def test_camel_case_serialization():
    item = PendingOrderItem(
        id=1,
        ticker="NVDA",
        setup_type="BREAKOUT",
        entry_price=180.0,
        stop_price=173.0,
        shares=40,
        target_2r=None,
        target_3r=None,
        expiration_date=None,
        status="ACTIVE",
        notes=None,
        created_at="2026-04-26T00:00:00+00:00",
        updated_at="2026-04-26T00:00:00+00:00",
        last_close=176.5,
        distance_to_trigger_pct=1.98,
        risk_pct=0.28,
    )
    dumped = item.model_dump(by_alias=True)
    assert "entryPrice" in dumped
    assert "stopPrice" in dumped
    assert "setupType" in dumped
    assert "distanceToTriggerPct" in dumped
    assert "riskPct" in dumped
    assert "lastClose" in dumped
    # snake_case keys should not appear
    assert "entry_price" not in dumped
    assert "distance_to_trigger_pct" not in dumped
