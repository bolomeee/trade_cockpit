"""Tests for F204-b Earnings Calendar接入层.

Sprint Contract 标准 S1–S8:
  S1. GET /api/cockpit/earnings?ticker=AAPL → 200 + earnings data (DB 有记录)
  S2. GET /api/cockpit/earnings?ticker=AAPL → 200 + null 字段 + note (DB 无记录)
  S3. GET /api/cockpit/earnings (缺 ticker) → 422 VALIDATION_ERROR
  S4. ticker 大小写转换：?ticker=aapl → 响应 ticker 为 "AAPL"
  S5. start_scheduler 注册 earnings job (05:30 UTC, mon-fri)
  S6. _earnings_tick 调用 EarningsService.fetch_and_store，无异常时正常完成
  S7. _earnings_tick 异常时不抛出 (logger 兜底)
  S8. 全量回归通过（由 pytest 运行保证）
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models import EarningsEvent
from app.services import refresh_job
from app.services.refresh_job import (
    EARNINGS_JOB_ID,
    RefreshJobManager,
    _earnings_tick,
    shutdown_scheduler,
    start_scheduler,
)


@pytest.fixture(autouse=True)
def _reset_scheduler():
    refresh_job.manager = RefreshJobManager()
    shutdown_scheduler()
    yield
    shutdown_scheduler()


def _seed_earnings(db_session, ticker: str = "AAPL", days_from_now: int = 28) -> EarningsEvent:
    event = EarningsEvent(
        ticker=ticker,
        earnings_date=date(2026, 5, 22),
        eps_estimate=5.20,
        eps_actual=None,
        revenue_estimate=48_000_000_000,
        revenue_actual=None,
        time_of_day="AMC",
        fetched_at=datetime.now(timezone.utc),
    )
    db_session.add(event)
    db_session.commit()
    return event


# ─────────────────────────── S1–S4: API tests ───────────────────────────────


class TestEarningsApiEndpoint:
    def test_s1_returns_earnings_data_when_db_has_record(self, client, db_session):
        """S1: 200 + full earnings payload when a future event exists in DB."""
        _seed_earnings(db_session)
        resp = client.get("/api/cockpit/earnings?ticker=AAPL")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        data = body["data"]
        assert data["ticker"] == "AAPL"
        assert data["nextEarningsDate"] == "2026-05-22"
        assert data["daysUntil"] is not None
        assert data["timeOfDay"] == "AMC"
        assert data["epsEstimate"] == pytest.approx(5.20)
        assert data["revenueEstimate"] == 48_000_000_000

    def test_s2_returns_nulls_with_note_when_no_db_record(self, client):
        """S2: 200 + null fields + note when DB has no upcoming earnings."""
        resp = client.get("/api/cockpit/earnings?ticker=NVDA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        data = body["data"]
        assert data["nextEarningsDate"] is None
        assert data["daysUntil"] is None
        assert data["timeOfDay"] is None
        assert data["epsEstimate"] is None
        assert data["revenueEstimate"] is None
        assert "No upcoming earnings" in data["note"]

    def test_s3_missing_ticker_returns_422(self, client):
        """S3: ticker 参数缺失 → 422 VALIDATION_ERROR."""
        resp = client.get("/api/cockpit/earnings")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_s4_ticker_case_insensitive_response_is_uppercase(self, client, db_session):
        """S4: 传入小写 ticker → 响应 ticker 字段为大写。"""
        _seed_earnings(db_session, ticker="AAPL")
        resp = client.get("/api/cockpit/earnings?ticker=aapl")
        assert resp.status_code == 200
        assert resp.json()["data"]["ticker"] == "AAPL"


# ─────────────────────────── S5: Scheduler tests ────────────────────────────


class TestEarningsScheduler:
    def test_s5_earnings_job_registered_with_correct_schedule(self):
        """S5: start_scheduler 注册 earnings job (05:30 UTC, mon-fri)."""
        sched = start_scheduler(
            session_factory=lambda: None,
            fmp_factory=lambda: None,
            autostart=False,
        )
        job_ids = {j.id for j in sched.get_jobs()}
        assert EARNINGS_JOB_ID in job_ids

        job = next(j for j in sched.get_jobs() if j.id == EARNINGS_JOB_ID)
        trigger = job.trigger
        # APScheduler CronTrigger: verify hour and minute fields
        fields = {f.name: str(f) for f in trigger.fields}
        assert fields["hour"] == "5"
        assert fields["minute"] == "30"
        assert fields["day_of_week"] == "mon-fri"


# ─────────────────────────── S6–S7: tick unit tests ─────────────────────────


class TestEarningsTick:
    def test_s6_tick_calls_fetch_and_store(self):
        """S6: _earnings_tick 正常执行时调用 EarningsService.fetch_and_store。"""
        mock_service = MagicMock()
        mock_fmp = MagicMock()
        mock_db = MagicMock()

        def session_factory():
            return mock_db

        with patch(
            "app.services.refresh_job.EarningsService",
            return_value=mock_service,
        ) as MockCls:
            _earnings_tick(session_factory, lambda: mock_fmp)
            MockCls.assert_called_once_with(mock_db, fmp=mock_fmp)
            mock_service.fetch_and_store.assert_called_once()

    def test_s7_tick_swallows_exception(self):
        """S7: _earnings_tick 内部异常不向上抛出（与其他 tick 行为一致）。"""
        def session_factory():
            return MagicMock()

        with patch(
            "app.services.refresh_job.EarningsService",
            side_effect=RuntimeError("FMP down"),
        ):
            # Must not raise
            _earnings_tick(session_factory, lambda: MagicMock())
