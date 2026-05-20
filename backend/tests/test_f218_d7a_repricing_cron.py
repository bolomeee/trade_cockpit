"""Tests for F218-d7a repricing trigger scheduler cron.

Sprint Contract 标准 S1–S2b:
  S1. start_scheduler 注册 REPRICING_TRIGGER_JOB_ID (22:40 UTC, mon-fri)
  S2a. _repricing_trigger_tick 调用 RepricingTriggerService.compute_and_store_all_triggers
  S2b. _repricing_trigger_tick 异常不向上抛
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.services import refresh_job
from app.services.refresh_job import (
    REPRICING_TRIGGER_JOB_ID,
    RefreshJobManager,
    _repricing_trigger_tick,
    shutdown_scheduler,
    start_scheduler,
)


@pytest.fixture(autouse=True)
def _reset_scheduler():
    refresh_job.manager = RefreshJobManager()
    shutdown_scheduler()
    yield
    shutdown_scheduler()


# ── S1: Scheduler registration ────────────────────────────────────────────────


class TestRepricingTriggerScheduler:
    def test_s1_repricing_trigger_job_registered_with_correct_schedule(self):
        """S1: start_scheduler 注册 REPRICING_TRIGGER_JOB_ID (22:40 UTC, mon-fri)."""
        sched = start_scheduler(
            session_factory=lambda: None,
            fmp_factory=lambda: None,
            autostart=False,
        )
        job_ids = {j.id for j in sched.get_jobs()}
        assert REPRICING_TRIGGER_JOB_ID in job_ids

        job = next(j for j in sched.get_jobs() if j.id == REPRICING_TRIGGER_JOB_ID)
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["hour"] == "22"
        assert fields["minute"] == "40"
        assert fields["day_of_week"] in ("mon-fri", "1-5")  # from_crontab stores numeric
        assert str(job.trigger.timezone) == "UTC"


# ── S2: tick unit tests ───────────────────────────────────────────────────────


class TestRepricingTriggerTick:
    def test_s2a_tick_calls_compute_and_store_all_triggers(self):
        """S2a: _repricing_trigger_tick 正常执行时调用 RepricingTriggerService.compute_and_store_all_triggers。"""
        mock_service = MagicMock()
        mock_db = MagicMock()

        with patch(
            "app.services.refresh_job.RepricingTriggerService",
            return_value=mock_service,
        ) as MockRTS:
            _repricing_trigger_tick(lambda: mock_db, lambda: None)
            MockRTS.assert_called_once_with(mock_db)
            mock_service.compute_and_store_all_triggers.assert_called_once()

    def test_s2b_tick_swallows_exception(self):
        """S2b: _repricing_trigger_tick 内部异常不向上抛（与其他 tick 行为一致）。"""
        with patch(
            "app.services.refresh_job.RepricingTriggerService",
            side_effect=RuntimeError("DB down"),
        ):
            _repricing_trigger_tick(lambda: MagicMock(), lambda: None)
