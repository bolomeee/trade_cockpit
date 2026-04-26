"""F206-b1 §C: PendingOrderService unit tests."""
from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

import pytest

from app.models.pending_order import PendingOrder
from app.repositories.pending_order_repository import PendingOrderRepository
from app.services.cockpit.pending_order_service import PendingOrderService
from app.services.watchlist_service import APIError


def _make_order_row(**overrides) -> PendingOrder:
    row = PendingOrder()
    row.id = overrides.get("id", 1)
    row.ticker = overrides.get("ticker", "NVDA")
    row.setup_type = overrides.get("setup_type", "BREAKOUT")
    row.entry_price = overrides.get("entry_price", 180.0)
    row.stop_price = overrides.get("stop_price", 173.0)
    row.shares = overrides.get("shares", 40)
    row.target_2r = overrides.get("target_2r", None)
    row.target_3r = overrides.get("target_3r", None)
    row.expiration_date = overrides.get("expiration_date", None)
    row.status = overrides.get("status", "ACTIVE")
    row.notes = overrides.get("notes", None)
    row.created_at = overrides.get("created_at", datetime.now(timezone.utc))
    row.updated_at = overrides.get("updated_at", datetime.now(timezone.utc))
    return row


def _make_service(db_session) -> PendingOrderService:
    fmp = MagicMock()
    fmp.get_daily_bars.return_value = []
    svc = PendingOrderService(db=db_session, fmp=fmp)
    return svc


def _repo_create(db_session, **overrides) -> PendingOrder:
    repo = PendingOrderRepository(db_session)
    base = dict(
        ticker="NVDA",
        setup_type="BREAKOUT",
        entry_price=180.0,
        stop_price=173.0,
        shares=40,
    )
    base.update(overrides)
    return repo.create(base)


# ---------------------------------------------------------------------------
# C1: status query param is case-insensitive
# ---------------------------------------------------------------------------

def test_normalize_status_case_insensitive(db_session):
    svc = _make_service(db_session)
    # "active" → "ACTIVE", "ACTIVE" → "ACTIVE", "All" → "all"
    assert svc._normalize_status("active") == "ACTIVE"
    assert svc._normalize_status("ACTIVE") == "ACTIVE"
    assert svc._normalize_status("All") == "all"
    assert svc._normalize_status("TRIGGERED") == "TRIGGERED"


# ---------------------------------------------------------------------------
# C2: invalid status → 422 APIError
# ---------------------------------------------------------------------------

def test_normalize_status_invalid_raises_422(db_session):
    svc = _make_service(db_session)
    with pytest.raises(APIError) as exc_info:
        svc._normalize_status("BOGUS")
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# C3: ACTIVE → TRIGGERED is allowed
# ---------------------------------------------------------------------------

def test_state_machine_active_to_triggered(db_session):
    svc = _make_service(db_session)
    row = _repo_create(db_session)

    from app.schemas.cockpit.pending_order import PendingOrderUpdate
    patch = PendingOrderUpdate(status="TRIGGERED")
    result = svc.update_pending_order(row.id, patch)

    assert result is not None
    assert result.status == "TRIGGERED"


# ---------------------------------------------------------------------------
# C4: TRIGGERED → ACTIVE → 422
# ---------------------------------------------------------------------------

def test_state_machine_triggered_to_active_422(db_session):
    svc = _make_service(db_session)
    row = _repo_create(db_session)
    repo = PendingOrderRepository(db_session)
    repo.update(row.id, {"status": "TRIGGERED"})

    from app.schemas.cockpit.pending_order import PendingOrderUpdate
    patch = PendingOrderUpdate(status="ACTIVE")
    with pytest.raises(APIError) as exc_info:
        svc.update_pending_order(row.id, patch)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# C5: CANCELLED → ACTIVE → 422
# ---------------------------------------------------------------------------

def test_state_machine_cancelled_to_active_422(db_session):
    svc = _make_service(db_session)
    row = _repo_create(db_session)
    repo = PendingOrderRepository(db_session)
    repo.update(row.id, {"status": "CANCELLED"})

    from app.schemas.cockpit.pending_order import PendingOrderUpdate
    patch = PendingOrderUpdate(status="ACTIVE")
    with pytest.raises(APIError) as exc_info:
        svc.update_pending_order(row.id, patch)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# C6: CANCELLED → EXPIRED → 422 (terminal→terminal forbidden)
# ---------------------------------------------------------------------------

def test_state_machine_cancelled_to_expired_422(db_session):
    svc = _make_service(db_session)
    row = _repo_create(db_session)
    repo = PendingOrderRepository(db_session)
    repo.update(row.id, {"status": "CANCELLED"})

    from app.schemas.cockpit.pending_order import PendingOrderUpdate
    patch = PendingOrderUpdate(status="EXPIRED")
    with pytest.raises(APIError) as exc_info:
        svc.update_pending_order(row.id, patch)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# C7: distanceToTriggerPct calculation: entry=180, last_close=176.5 → 1.98
# ---------------------------------------------------------------------------

def test_distance_to_trigger_pct_calculation(db_session):
    svc = _make_service(db_session)
    row = _make_order_row(entry_price=180.0, stop_price=173.0, shares=40)
    account_size = 100_000.0
    item = svc._enrich(row, last_close=176.5, account_size=account_size)

    assert item.distance_to_trigger_pct == 1.98  # (180-176.5)/176.5*100


# ---------------------------------------------------------------------------
# C8: distanceToTriggerPct is None when last_close is None
# ---------------------------------------------------------------------------

def test_distance_to_trigger_pct_none_when_no_close(db_session):
    svc = _make_service(db_session)
    row = _make_order_row()
    item = svc._enrich(row, last_close=None, account_size=100_000.0)
    assert item.distance_to_trigger_pct is None


# ---------------------------------------------------------------------------
# C9: riskPct calculation: (180-173)*40/100000*100 = 0.28
# ---------------------------------------------------------------------------

def test_risk_pct_calculation(db_session):
    svc = _make_service(db_session)
    row = _make_order_row(entry_price=180.0, stop_price=173.0, shares=40)
    item = svc._enrich(row, last_close=176.5, account_size=100_000.0)
    assert item.risk_pct == 0.28  # 7*40/100000*100


# ---------------------------------------------------------------------------
# C10: riskPct is computed even when last_close is None (no market price needed)
# ---------------------------------------------------------------------------

def test_risk_pct_computed_without_last_close(db_session):
    svc = _make_service(db_session)
    row = _make_order_row(entry_price=180.0, stop_price=173.0, shares=40)
    item = svc._enrich(row, last_close=None, account_size=100_000.0)
    assert item.risk_pct == 0.28
    assert item.last_close is None


# ---------------------------------------------------------------------------
# C11: patch only entry_price — service merges with DB stop, validates entry>stop
# ---------------------------------------------------------------------------

def test_patch_only_entry_merges_with_db_stop_422(db_session):
    svc = _make_service(db_session)
    # DB: entry=180, stop=173
    row = _repo_create(db_session, entry_price=180.0, stop_price=173.0)

    from app.schemas.cockpit.pending_order import PendingOrderUpdate
    # Only patching entry to 170, which is < DB stop 173 → 422
    patch = PendingOrderUpdate(entryPrice=170.0)
    with pytest.raises(APIError) as exc_info:
        svc.update_pending_order(row.id, patch)
    assert exc_info.value.status_code == 422


# ---------------------------------------------------------------------------
# C12: last_close_loader refactor regression — PositionService still loads closes
# ---------------------------------------------------------------------------

def test_position_service_loader_regression(db_session):
    """Ensure PositionService still works via LastCloseLoader after refactor."""
    from app.services.cockpit.position_service import PositionService

    fmp = MagicMock()
    fmp.get_daily_bars.return_value = []
    svc = PositionService(db=db_session, fmp=fmp)

    # No positions → should return empty items without error
    summary, items = svc.list_positions(status="open")
    assert items == []
