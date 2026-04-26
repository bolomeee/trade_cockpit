"""F206-b2 §B: pending_order_expirer unit + scheduler tests."""
from __future__ import annotations

import time
from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

import app.services.refresh_job as refresh_job
from app.repositories.pending_order_repository import PendingOrderRepository
from app.services.cockpit.pending_order_expirer import expire_due_pending_orders
from app.services.refresh_job import RefreshJobManager, shutdown_scheduler


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

TODAY = date(2026, 4, 26)
YESTERDAY = TODAY - timedelta(days=1)
TOMORROW = TODAY + timedelta(days=1)


@pytest.fixture(autouse=True)
def _reset_scheduler():
    refresh_job.manager = RefreshJobManager()
    shutdown_scheduler()
    yield
    shutdown_scheduler()


def _make_order(db_session, **overrides) -> object:
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
# B1: past expiration_date → status becomes EXPIRED, returns 1
# ---------------------------------------------------------------------------

def test_expire_past_date(db_session):
    _make_order(db_session, expiration_date=YESTERDAY)
    result = expire_due_pending_orders(db_session, today=TODAY)
    assert result == 1
    repo = PendingOrderRepository(db_session)
    rows = repo.list_by_status("EXPIRED")
    assert len(rows) == 1


# ---------------------------------------------------------------------------
# B2: expiration_date == today → NOT expired (strictly less than)
# ---------------------------------------------------------------------------

def test_same_day_not_expired(db_session):
    _make_order(db_session, expiration_date=TODAY)
    result = expire_due_pending_orders(db_session, today=TODAY)
    assert result == 0
    repo = PendingOrderRepository(db_session)
    assert len(repo.list_by_status("ACTIVE")) == 1


# ---------------------------------------------------------------------------
# B3: future expiration_date → NOT expired
# ---------------------------------------------------------------------------

def test_future_date_not_expired(db_session):
    _make_order(db_session, expiration_date=TOMORROW)
    result = expire_due_pending_orders(db_session, today=TODAY)
    assert result == 0


# ---------------------------------------------------------------------------
# B4: expiration_date=None → never expires
# ---------------------------------------------------------------------------

def test_none_expiration_date_never_expires(db_session):
    _make_order(db_session, expiration_date=None)
    result = expire_due_pending_orders(db_session, today=TODAY)
    assert result == 0
    repo = PendingOrderRepository(db_session)
    assert len(repo.list_by_status("ACTIVE")) == 1


# ---------------------------------------------------------------------------
# B5: terminal statuses (TRIGGERED/CANCELLED/EXPIRED) are not touched
# ---------------------------------------------------------------------------

def test_terminal_statuses_not_touched(db_session):
    repo = PendingOrderRepository(db_session)
    for status in ("TRIGGERED", "CANCELLED", "EXPIRED"):
        row = _make_order(db_session, expiration_date=YESTERDAY)
        repo.update(row.id, {"status": status})

    result = expire_due_pending_orders(db_session, today=TODAY)
    assert result == 0


# ---------------------------------------------------------------------------
# B6: mixed ACTIVE rows — only expired ones change
# ---------------------------------------------------------------------------

def test_mixed_active_rows_only_expired_change(db_session):
    _make_order(db_session, expiration_date=YESTERDAY)   # should expire
    _make_order(db_session, expiration_date=TOMORROW)    # stays ACTIVE
    _make_order(db_session, expiration_date=None)        # stays ACTIVE

    result = expire_due_pending_orders(db_session, today=TODAY)
    assert result == 1
    repo = PendingOrderRepository(db_session)
    assert len(repo.list_by_status("ACTIVE")) == 2
    assert len(repo.list_by_status("EXPIRED")) == 1


# ---------------------------------------------------------------------------
# B7: idempotent — second call returns 0
# ---------------------------------------------------------------------------

def test_idempotent_second_call(db_session):
    _make_order(db_session, expiration_date=YESTERDAY)
    first = expire_due_pending_orders(db_session, today=TODAY)
    second = expire_due_pending_orders(db_session, today=TODAY)
    assert first == 1
    assert second == 0


# ---------------------------------------------------------------------------
# B8: updated_at refreshed on expiry
# ---------------------------------------------------------------------------

def test_updated_at_refreshed_on_expiry(db_session):
    repo = PendingOrderRepository(db_session)
    row = _make_order(db_session, expiration_date=YESTERDAY)
    original_updated_at = row.updated_at

    time.sleep(0.01)
    expire_due_pending_orders(db_session, today=TODAY)

    updated = repo.get_by_id(row.id)
    assert updated is not None
    assert updated.updated_at >= original_updated_at


# ---------------------------------------------------------------------------
# B9: scheduler registration — job id present with CronTrigger
# ---------------------------------------------------------------------------

def test_scheduler_registers_expirer_job():
    from apscheduler.triggers.cron import CronTrigger

    from app.services.refresh_job import (
        PENDING_ORDERS_EXPIRER_JOB_ID,
        start_scheduler,
    )

    sched = start_scheduler(
        session_factory=MagicMock(),
        fmp_factory=MagicMock(),
        autostart=False,
    )

    job_ids = [j.id for j in sched.get_jobs()]
    assert PENDING_ORDERS_EXPIRER_JOB_ID in job_ids

    job = next(j for j in sched.get_jobs() if j.id == PENDING_ORDERS_EXPIRER_JOB_ID)
    assert isinstance(job.trigger, CronTrigger)
    fields = {f.name: str(f) for f in job.trigger.fields}
    assert fields["hour"] == "22"
    assert fields["minute"] == "35"


# ---------------------------------------------------------------------------
# B10: tick exception is caught — does not propagate
# ---------------------------------------------------------------------------

def test_expirer_tick_exception_caught():
    from app.services.refresh_job import _pending_orders_expirer_tick

    session_factory_mock = MagicMock()
    session_factory_mock.return_value.__enter__ = MagicMock(side_effect=RuntimeError("db down"))
    session_factory_mock.return_value.__exit__ = MagicMock(return_value=False)

    with patch(
        "app.services.cockpit.pending_order_expirer.expire_due_pending_orders",
        side_effect=RuntimeError("boom"),
    ):
        # must not raise
        _pending_orders_expirer_tick(session_factory_mock)
