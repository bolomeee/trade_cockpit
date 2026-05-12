"""F211-d1: JournalReviewService tests — 5 unit + 8 integration + 2 e2e = 15 cases.

§U — unit: _build_trade_input + _upsert_sell_journal_entry (pure logic / minimal DB)
§I — integration: trade_review_for_position paths (db_session, gateway mocked)
§E — e2e: PATCH /api/cockpit/positions/{id} BackgroundTask dispatch (TestClient)
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date, datetime, timezone
from decimal import Decimal
from typing import Any
from unittest.mock import MagicMock

import pytest

from app.ai.errors import AiBudgetExceeded, AiGuardrailViolation, AiProviderError
from app.ai.gateway import GatewayMeta, GatewayResult
from app.ai.schemas.journal_assistant import JournalAssistantInput
from app.models.journal_entry import JournalEntry
from app.models.position import Position
from app.models.stock import Stock
from app.services.cockpit.journal_review_service import JournalReviewService


# ---------------------------------------------------------------------------
# Shared helpers
# ---------------------------------------------------------------------------

_TRADE_OUTPUT = {
    "mode": "trade",
    "trade": {
        "planVsActualScore": 7,
        "entryQuality": "good",
        "stopDiscipline": "fair",
        "mistakes": [],
        "lesson": "You executed well.",
    },
    "monthly": None,
}

_FAKE_META = GatewayMeta(
    model_used="test-model",
    tier="complex",
    tokens_in=100,
    tokens_out=50,
    cost_usd=Decimal("0.001"),
    latency_ms=500,
    cache_hit=False,
)


def _fake_gateway_result(memo_id: int = 999) -> GatewayResult:
    return GatewayResult(
        memo_id=memo_id,
        task_type="journal_assistant",
        schema_version="v1",
        output=_TRADE_OUTPUT,
        meta=_FAKE_META,
    )


def _make_position(**kwargs: Any) -> MagicMock:
    """Create a mock Position with sensible defaults for _build_trade_input tests."""
    pos = MagicMock(spec=Position)
    pos.ticker = kwargs.get("ticker", "AAPL")
    pos.setup_type = kwargs.get("setup_type", "BREAKOUT")
    pos.entry_price = kwargs.get("entry_price", 100.0)
    pos.stop_price = kwargs.get("stop_price", 95.0)
    pos.target_2r = kwargs.get("target_2r", 110.0)
    pos.close_price = kwargs.get("close_price", 110.0)
    pos.shares = kwargs.get("shares", 100)
    pos.entry_date = kwargs.get("entry_date", date(2026, 1, 1))
    pos.closed_at = kwargs.get(
        "closed_at", datetime(2026, 1, 15, 12, 0, tzinfo=timezone.utc)
    )
    pos.notes = kwargs.get("notes", None)
    return pos


def _seed_stock_and_position(db_session, *, status: str = "CLOSED") -> tuple[Stock, Position]:
    """Insert a Stock + Position row; return both."""
    stock = Stock(ticker="TSLA", name="Tesla Inc", is_active=True)
    db_session.add(stock)
    db_session.flush()

    close_dt = datetime(2026, 1, 20, 16, 0, tzinfo=timezone.utc)
    pos = Position(
        ticker="TSLA",
        entry_price=200.0,
        entry_date=date(2026, 1, 5),
        shares=50,
        stop_price=190.0,
        target_2r=220.0,
        setup_type="BREAKOUT",
        notes="test trade",
        status=status,
        closed_at=close_dt if status == "CLOSED" else None,
        close_price=210.0 if status == "CLOSED" else None,
    )
    db_session.add(pos)
    db_session.commit()
    return stock, pos


# ---------------------------------------------------------------------------
# §U — Unit tests
# ---------------------------------------------------------------------------


class TestBuildTradeInput:
    def test_U1_normal_position_passes_pydantic_validation(self):
        """_build_trade_input → dict passes JournalAssistantInput(**dict) without error."""
        svc = JournalReviewService.__new__(JournalReviewService)
        pos = _make_position()
        result = svc._build_trade_input(pos)
        # Must not raise — this is the key assertion
        validated = JournalAssistantInput(**result)
        assert validated.mode == "trade"
        assert validated.trade is not None
        assert validated.trade.ticker == "AAPL"

    def test_U2_r_multiple_calculation(self):
        """entry=100, stop=95, exit=110 → rMultiple=2.0."""
        svc = JournalReviewService.__new__(JournalReviewService)
        pos = _make_position(entry_price=100.0, stop_price=95.0, close_price=110.0)
        result = svc._build_trade_input(pos)
        assert result["trade"]["rMultiple"] == 2.0

    def test_U3_none_setup_type_and_notes(self):
        """setup_type=None / notes=None → setupType=None / preTradeNotes=None, no error."""
        svc = JournalReviewService.__new__(JournalReviewService)
        pos = _make_position(setup_type=None, notes=None)
        result = svc._build_trade_input(pos)
        assert result["trade"]["setupType"] is None
        assert result["trade"]["preTradeNotes"] is None
        # Still must pass Pydantic validation
        JournalAssistantInput(**result)

    def test_U4_zero_risk_per_share_returns_zero_r_multiple(self):
        """risk_per_share=0 → rMultiple=0.0, no ZeroDivisionError."""
        svc = JournalReviewService.__new__(JournalReviewService)
        pos = _make_position(entry_price=100.0, stop_price=100.0, close_price=105.0)
        result = svc._build_trade_input(pos)
        assert result["trade"]["rMultiple"] == 0.0


class TestUpsertSellJournalEntry:
    def test_U5_reuse_existing_sell_entry(self, db_session):
        """Same ticker + date + SELL already in DB → returns existing entry, no new INSERT."""
        stock, pos = _seed_stock_and_position(db_session)
        close_date = pos.closed_at.date()

        existing = JournalEntry(
            stock_id=stock.id,
            action="SELL",
            price=209.0,
            date=close_date,
            reason="manual",
        )
        db_session.add(existing)
        db_session.commit()
        existing_id = existing.id

        svc = JournalReviewService(db_session)
        returned = svc._upsert_sell_journal_entry(stock_id=stock.id, position=pos)

        count = db_session.query(JournalEntry).filter(JournalEntry.action == "SELL").count()
        assert returned.id == existing_id
        assert count == 1  # no duplicate inserted


# ---------------------------------------------------------------------------
# §I — Integration tests (gateway mocked, real in-memory DB)
# ---------------------------------------------------------------------------


class TestTradeReviewForPosition:
    def test_I1_success_creates_sell_entry_with_ai_review(self, db_session, monkeypatch):
        """Normal path: gateway succeeds → SELL entry created with ai_review JSON + memo_id."""
        stock, pos = _seed_stock_and_position(db_session)
        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run",
            lambda self, **kwargs: _fake_gateway_result(memo_id=42),
        )

        svc = JournalReviewService(db_session)
        entry_id = svc.trade_review_for_position(pos.id)

        assert entry_id is not None
        entry = db_session.get(JournalEntry, entry_id)
        assert entry is not None
        assert entry.action == "SELL"
        assert entry.ai_review is not None
        review = json.loads(entry.ai_review)
        assert review["mode"] == "trade"
        assert entry.ai_review_memo_id == 42

    def test_I2_existing_ai_review_skips_gateway(self, db_session, monkeypatch):
        """Already has ai_review → gateway NOT called, returns existing entry id."""
        stock, pos = _seed_stock_and_position(db_session)
        existing = JournalEntry(
            stock_id=stock.id,
            action="SELL",
            price=210.0,
            date=pos.closed_at.date(),
            ai_review=json.dumps(_TRADE_OUTPUT),
            ai_review_memo_id=77,
        )
        db_session.add(existing)
        db_session.commit()

        call_count = [0]

        def _should_not_be_called(self, **kwargs: Any) -> GatewayResult:
            call_count[0] += 1
            return _fake_gateway_result()

        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run",
            _should_not_be_called,
        )

        svc = JournalReviewService(db_session)
        returned_id = svc.trade_review_for_position(pos.id)

        assert returned_id == existing.id
        assert call_count[0] == 0

    def test_I3_ai_provider_error_returns_none_no_entry(self, db_session, monkeypatch):
        """AiProviderError → returns None, no SELL entry persisted."""
        stock, pos = _seed_stock_and_position(db_session)
        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run",
            lambda self, **kwargs: (_ for _ in ()).throw(AiProviderError("provider down")),
        )

        svc = JournalReviewService(db_session)
        result = svc.trade_review_for_position(pos.id)

        assert result is None
        count = db_session.query(JournalEntry).filter(JournalEntry.action == "SELL").count()
        assert count == 0

    def test_I4_budget_exceeded_returns_none(self, db_session, monkeypatch):
        """AiBudgetExceeded → returns None, logs warning, no entry."""
        stock, pos = _seed_stock_and_position(db_session)
        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run",
            lambda self, **kwargs: (_ for _ in ()).throw(AiBudgetExceeded("over budget")),
        )

        svc = JournalReviewService(db_session)
        result = svc.trade_review_for_position(pos.id)

        assert result is None

    def test_I5_guardrail_violation_returns_none(self, db_session, monkeypatch):
        """AiGuardrailViolation → returns None, no entry persisted."""
        stock, pos = _seed_stock_and_position(db_session)
        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run",
            lambda self, **kwargs: (_ for _ in ()).throw(
                AiGuardrailViolation("banned phrase")
            ),
        )

        svc = JournalReviewService(db_session)
        result = svc.trade_review_for_position(pos.id)

        assert result is None

    def test_I6_position_not_found_returns_none(self, db_session, monkeypatch):
        """Non-existent position_id → early return None, gateway not called."""
        call_count = [0]

        def _noop(self, **kwargs: Any) -> GatewayResult:
            call_count[0] += 1
            return _fake_gateway_result()

        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run", _noop
        )

        svc = JournalReviewService(db_session)
        result = svc.trade_review_for_position(99999)

        assert result is None
        assert call_count[0] == 0

    def test_I7_ticker_not_in_watchlist_returns_none(self, db_session, monkeypatch):
        """Ticker has no matching Stock row → early return None."""
        pos = Position(
            ticker="UNKNOWN",
            entry_price=100.0,
            entry_date=date(2026, 1, 1),
            shares=10,
            stop_price=90.0,
            status="CLOSED",
            closed_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            close_price=110.0,
        )
        db_session.add(pos)
        db_session.commit()

        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run",
            lambda self, **kwargs: _fake_gateway_result(),
        )

        svc = JournalReviewService(db_session)
        result = svc.trade_review_for_position(pos.id)

        assert result is None
        assert db_session.query(JournalEntry).count() == 0

    def test_I8_position_not_closed_returns_none(self, db_session, monkeypatch):
        """position.status == OPEN → early return None (防御重入)."""
        stock, pos = _seed_stock_and_position(db_session, status="OPEN")

        call_count = [0]

        def _noop(self, **kwargs: Any) -> GatewayResult:
            call_count[0] += 1
            return _fake_gateway_result()

        monkeypatch.setattr(
            "app.services.cockpit.journal_review_service.AiGateway.run", _noop
        )

        svc = JournalReviewService(db_session)
        result = svc.trade_review_for_position(pos.id)

        assert result is None
        assert call_count[0] == 0


# ---------------------------------------------------------------------------
# §E — e2e: PATCH BackgroundTask dispatch
# ---------------------------------------------------------------------------


class TestPositionCloseHookE2E:
    def test_E1_patch_open_to_closed_dispatches_background_task(self, client, db_session):
        """PATCH OPEN→CLOSED → 200 immediate + trade_review_for_position called once."""
        # Seed a stock + open position via API to get valid state
        stock = Stock(ticker="NVDA", name="Nvidia Corp", is_active=True)
        db_session.add(stock)
        db_session.commit()

        resp = client.post(
            "/api/cockpit/positions",
            json={
                "ticker": "NVDA",
                "entryPrice": 500.0,
                "entryDate": "2026-01-05",
                "shares": 20,
                "stopPrice": 480.0,
                "target2r": 540.0,
            },
        )
        assert resp.status_code == 201
        position_id = resp.json()["data"]["id"]

        # Track calls to trade_review_for_position
        call_log: list[int] = []

        def _fake_review(self: JournalReviewService, position_id: int) -> int | None:
            call_log.append(position_id)
            return None

        from app.services.cockpit import journal_review_service as jrs_module

        original = jrs_module.JournalReviewService.trade_review_for_position
        jrs_module.JournalReviewService.trade_review_for_position = _fake_review
        try:
            patch_resp = client.patch(
                f"/api/cockpit/positions/{position_id}",
                json={
                    "status": "CLOSED",
                    "closedAt": "2026-01-20T16:00:00Z",
                    "closePrice": 520.0,
                },
            )
            assert patch_resp.status_code == 200
            assert patch_resp.json()["data"]["status"] == "CLOSED"
            # TestClient runs background tasks synchronously before returning
            assert call_log == [position_id]
        finally:
            jrs_module.JournalReviewService.trade_review_for_position = original

    def test_E2_patch_closed_to_closed_no_background_task(self, client, db_session):
        """PATCH pre_status=CLOSED → BackgroundTask NOT dispatched."""
        stock = Stock(ticker="META", name="Meta Platforms", is_active=True)
        db_session.add(stock)
        db_session.commit()

        # Create + close position in one step via direct model insert
        pos = Position(
            ticker="META",
            entry_price=400.0,
            entry_date=date(2026, 1, 5),
            shares=10,
            stop_price=380.0,
            status="CLOSED",
            closed_at=datetime(2026, 1, 10, tzinfo=timezone.utc),
            close_price=420.0,
        )
        db_session.add(pos)
        db_session.commit()
        position_id = pos.id

        call_log: list[int] = []

        def _fake_review(self: JournalReviewService, pid: int) -> int | None:
            call_log.append(pid)
            return None

        from app.services.cockpit import journal_review_service as jrs_module

        original = jrs_module.JournalReviewService.trade_review_for_position
        jrs_module.JournalReviewService.trade_review_for_position = _fake_review
        try:
            # Patch some non-status field on already-CLOSED position
            patch_resp = client.patch(
                f"/api/cockpit/positions/{position_id}",
                json={"notes": "updated note"},
            )
            assert patch_resp.status_code == 200
            assert call_log == []  # no dispatch
        finally:
            jrs_module.JournalReviewService.trade_review_for_position = original
