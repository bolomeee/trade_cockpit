"""F211-d2: JournalReviewService monthly mode + refresh_job cron tests.

14 test cases:
  U1-U3  — _previous_month_utc pure function (added in step 4)
  U4-U6  — _brief_for_position unit tests
  I1-I5  — monthly_review_for_month integration tests
  S1-S3  — refresh_job scheduler registration + tick tests (added in step 4)
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from app.ai.errors import AiBudgetExceeded, AiGuardrailViolation, AiProviderError, AiSchemaError
from app.ai.schemas.journal_assistant import ClosedTradeBrief, JournalAssistantInput
from app.models.position import Position
from app.services.cockpit.journal_review_service import JournalReviewService
from app.services.refresh_job import (
    JOURNAL_MONTHLY_JOB_ID,
    _journal_monthly_tick,
    _previous_month_utc,
    start_scheduler,
)


# ─── helpers ─────────────────────────────────────────────────────────────────


def _make_position(
    *,
    ticker: str = "AAPL",
    status: str = "CLOSED",
    entry_price: float = 100.0,
    stop_price: float = 90.0,
    close_price: float = 120.0,
    entry_date: date = date(2026, 3, 1),
    closed_at: datetime | None = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
    setup_type: str | None = "BREAKOUT",
    updated_at: datetime = datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
    shares: int = 100,
) -> Position:
    p = Position()
    p.ticker = ticker
    p.status = status
    p.entry_price = entry_price
    p.stop_price = stop_price
    p.close_price = close_price
    p.entry_date = entry_date
    p.closed_at = closed_at
    p.setup_type = setup_type
    p.updated_at = updated_at
    p.shares = shares
    p.notes = None
    p.target_2r = None
    p.target_3r = None
    return p


def _make_gateway_result(memo_id: int = 999) -> Any:
    from dataclasses import make_dataclass
    from decimal import Decimal

    Meta = make_dataclass("Meta", ["model_used", "tier", "tokens_in", "tokens_out", "cost_usd", "latency_ms", "cache_hit"])
    Result = make_dataclass("Result", ["memo_id", "task_type", "schema_version", "output", "meta"])
    meta = Meta(
        model_used="gpt-5.4",
        tier="complex",
        tokens_in=100,
        tokens_out=50,
        cost_usd=Decimal("0.01"),
        latency_ms=500,
        cache_hit=False,
    )
    return Result(
        memo_id=memo_id,
        task_type="journal_assistant",
        schema_version="v1",
        output={
            "mode": "monthly",
            "monthly": {
                "month": "2026-03",
                "overallExpectancy": "Solid month with 2 winning trades.",
                "ruleAdherence": 8,
                "setupPerformance": [],
                "keyLessons": [],
            },
        },
        meta=meta,
    )


# ─── U4-U6: _brief_for_position ──────────────────────────────────────────────


class TestBriefForPosition:
    def _svc(self, db_session) -> JournalReviewService:
        return JournalReviewService(db_session)

    def test_u4_normal_fields_pass_schema(self, db_session):
        """U4: _brief_for_position 正常字段 → schema ClosedTradeBrief 不抛；rMultiple 正确。"""
        svc = self._svc(db_session)
        p = _make_position(
            entry_price=100.0,
            stop_price=90.0,
            close_price=120.0,
            entry_date=date(2026, 3, 1),
            closed_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            setup_type="BREAKOUT",
        )
        brief = svc._brief_for_position(p)

        # Pydantic validation
        ClosedTradeBrief(**brief)

        # rMultiple: (120 - 100) / (100 - 90) = 2.0
        assert brief["rMultiple"] == 2.0
        assert brief["ticker"] == "AAPL"
        assert brief["setupType"] == "BREAKOUT"
        assert brief["holdingDays"] == 14
        assert brief["closedOn"] == "2026-03-15"

    def test_u5_setup_type_none(self, db_session):
        """U5: setup_type=None → setupType=None，不抛。"""
        svc = self._svc(db_session)
        p = _make_position(setup_type=None)
        brief = svc._brief_for_position(p)

        ClosedTradeBrief(**brief)
        assert brief["setupType"] is None

    def test_u6_risk_per_share_zero_returns_zero(self, db_session):
        """U6: risk_per_share ≤ 0（entry == stop）→ rMultiple=0.0，不抛 ZeroDivision。"""
        svc = self._svc(db_session)
        p = _make_position(entry_price=100.0, stop_price=100.0)  # risk = 0
        brief = svc._brief_for_position(p)

        ClosedTradeBrief(**brief)
        assert brief["rMultiple"] == 0.0


# ─── I1-I5: monthly_review_for_month integration ────────────────────────────


class TestMonthlyReviewIntegration:
    def _svc(self, db_session) -> JournalReviewService:
        return JournalReviewService(db_session)

    def _add_position(self, db_session, **kwargs) -> Position:
        p = _make_position(**kwargs)
        db_session.add(p)
        db_session.flush()
        return p

    def test_i1_fetch_only_month_closed_positions(self, db_session):
        """I1: _fetch_closed_positions_for_month 只返回月内 CLOSED positions。"""
        # In month: March 2026
        in_month = self._add_position(
            db_session,
            closed_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            status="CLOSED",
        )
        # Out: previous month
        self._add_position(
            db_session,
            ticker="PREV",
            closed_at=datetime(2026, 2, 28, 23, 59, tzinfo=timezone.utc),
            status="CLOSED",
        )
        # Out: next month
        self._add_position(
            db_session,
            ticker="NEXT",
            closed_at=datetime(2026, 4, 1, 0, 0, tzinfo=timezone.utc),
            status="CLOSED",
        )
        # Out: OPEN in March
        self._add_position(
            db_session,
            ticker="OPEN",
            closed_at=None,
            status="OPEN",
        )
        db_session.commit()

        svc = self._svc(db_session)
        result = svc._fetch_closed_positions_for_month("2026-03")

        assert len(result) == 1
        assert result[0].id == in_month.id

    def test_i2_zero_trades_skips_gateway(self, db_session, caplog):
        """I2: 0 trades → 跳过 gateway，返回 None，log INFO。"""
        svc = self._svc(db_session)

        with patch.object(svc._gateway, "run") as mock_run, \
             caplog.at_level("INFO", logger="app.services.cockpit.journal_review_service"):
            result = svc.monthly_review_for_month("2026-03")

        assert result is None
        mock_run.assert_not_called()
        assert "monthly_review skipped" in caplog.text

    def test_i3_normal_path_returns_memo_id_and_validates_input(self, db_session):
        """I3: 正常路径返回 memo_id；input dict 过 JournalAssistantInput Pydantic 验证。"""
        self._add_position(
            db_session,
            closed_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            status="CLOSED",
        )
        db_session.commit()

        fake_result = _make_gateway_result(memo_id=999)
        captured_input: dict = {}

        def fake_run(task_type: str, input_dict: dict):
            captured_input.update(input_dict)
            return fake_result

        svc = self._svc(db_session)
        with patch.object(svc._gateway, "run", side_effect=fake_run):
            result = svc.monthly_review_for_month("2026-03")

        assert result == 999

        # Pydantic validation of the input dict passed to gateway
        JournalAssistantInput(**captured_input)
        assert captured_input["mode"] == "monthly"
        assert captured_input["monthly"]["month"] == "2026-03"
        assert len(captured_input["monthly"]["closedTrades"]) == 1

    def test_i4_limit_100_takes_earliest(self, db_session):
        """I4: 105 closed positions → 取最早 100 条传 gateway（ORDER BY closed_at ASC）。"""
        # 105 positions in March 2026, spaced 6 hours apart starting 2026-03-01 00:00
        base = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        for i in range(105):
            closed_at = base.replace(hour=0) + __import__("datetime").timedelta(hours=i * 6)
            if closed_at.month != 3:
                # Keep within March by capping — but 105 * 6h = 630h = 26 days, stays in March
                pass
            p = _make_position(
                ticker=f"T{i:03d}",
                closed_at=closed_at,
                status="CLOSED",
            )
            db_session.add(p)
        db_session.commit()

        captured_trades: list = []

        def fake_run(task_type: str, input_dict: dict):
            captured_trades.extend(input_dict["monthly"]["closedTrades"])
            return _make_gateway_result()

        svc = self._svc(db_session)
        with patch.object(svc._gateway, "run", side_effect=fake_run):
            svc.monthly_review_for_month("2026-03")

        assert len(captured_trades) == 100
        # First trade should be T000 (earliest)
        assert captured_trades[0]["ticker"] == "T000"

    @pytest.mark.parametrize("exc_cls", [
        AiProviderError,
        AiSchemaError,
        AiGuardrailViolation,
        AiBudgetExceeded,
    ])
    def test_i5_ai_errors_return_none_and_log_warn(self, db_session, caplog, exc_cls):
        """I5: 4 类 AI 错误 → 全部返回 None，log WARN，不抛。"""
        self._add_position(
            db_session,
            closed_at=datetime(2026, 3, 15, 12, 0, tzinfo=timezone.utc),
            status="CLOSED",
        )
        db_session.commit()

        svc = self._svc(db_session)
        with patch.object(svc._gateway, "run", side_effect=exc_cls("test error")), \
             caplog.at_level("WARNING", logger="app.services.cockpit.journal_review_service"):
            result = svc.monthly_review_for_month("2026-03")

        assert result is None
        assert "monthly_review AI error" in caplog.text


# ─── U1-U3: _previous_month_utc ──────────────────────────────────────────────


class TestPreviousMonthUtc:
    def test_u1_normal_month(self):
        """U1: 2026-04-29 06:00 UTC → '2026-03'。"""
        now = datetime(2026, 4, 29, 6, 0, tzinfo=timezone.utc)
        assert _previous_month_utc(now) == "2026-03"

    def test_u2_cross_year_boundary(self):
        """U2: 2026-01-15 → '2025-12'（跨年）。"""
        now = datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
        assert _previous_month_utc(now) == "2025-12"

    def test_u3_first_day_of_month(self):
        """U3: 2026-03-01 00:00 → '2026-02'（边界：1 号当天取上个月）。"""
        now = datetime(2026, 3, 1, 0, 0, tzinfo=timezone.utc)
        assert _previous_month_utc(now) == "2026-02"


# ─── S1-S3: scheduler registration + tick ────────────────────────────────────


class TestJournalMonthlyScheduler:
    def test_s1_job_registered_with_correct_trigger(self):
        """S1: start_scheduler 注册 JOURNAL_MONTHLY_JOB_ID，trigger day=1/hour=6/minute=0。"""
        sched = start_scheduler(
            session_factory=lambda: None,
            fmp_factory=lambda: None,
            autostart=False,
        )
        job_ids = {j.id for j in sched.get_jobs()}
        assert JOURNAL_MONTHLY_JOB_ID in job_ids

        job = next(j for j in sched.get_jobs() if j.id == JOURNAL_MONTHLY_JOB_ID)
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["day"] == "1"
        assert fields["hour"] == "6"
        assert fields["minute"] == "0"

    def test_s2_tick_calls_monthly_review_with_previous_month(self):
        """S2: _journal_monthly_tick 调用 JournalReviewService.monthly_review_for_month，参数为 _previous_month_utc(now)。"""
        fixed_now = datetime(2026, 4, 29, 6, 0, tzinfo=timezone.utc)
        expected_month = _previous_month_utc(fixed_now)  # "2026-03"

        mock_service = MagicMock()
        mock_db = MagicMock()

        def session_factory():
            return mock_db

        with patch("app.services.refresh_job.datetime") as mock_dt, \
             patch("app.services.refresh_job.JournalReviewService", return_value=mock_service) as MockCls:
            mock_dt.now.return_value = fixed_now
            _journal_monthly_tick(session_factory)

        MockCls.assert_called_once_with(mock_db)
        mock_service.monthly_review_for_month.assert_called_once_with(expected_month)

    def test_s3_tick_swallows_exception(self):
        """S3: _journal_monthly_tick 内部异常不向上抛出。"""
        def session_factory():
            return MagicMock()

        with patch(
            "app.services.refresh_job.JournalReviewService",
            side_effect=RuntimeError("db down"),
        ):
            # Must not raise
            _journal_monthly_tick(session_factory)
