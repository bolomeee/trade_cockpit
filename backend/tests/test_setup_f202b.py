"""Tests for F202-b Setup Monitor 接入层.

Sprint Contract 标准 S1–S7:
  S1. GET /api/cockpit/setup-monitor 冷启动（无 snapshot）→ 200 summary.total=0 items=[]
  S2. 有 snapshot 时 → 200，summary 计数正确，items 含 stockName / setupType / readySignal
  S3. filter=ready 只返回 ready bucket 的 item
  S4. filter=broken,extended 只返回对应两个 bucket
  S5. filter 含非法值 → 422 VALIDATION_ERROR
  S6. start_scheduler 注册 SETUP_JOB_ID (22:30 UTC, mon-fri)
  S7. _setup_tick 调用 compute_and_store_all；异常不向上抛
"""
from __future__ import annotations

from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock
from app.services import refresh_job
from app.services.refresh_job import (
    SETUP_JOB_ID,
    RefreshJobManager,
    _setup_tick,
    shutdown_scheduler,
    start_scheduler,
)


@pytest.fixture(autouse=True)
def _reset_scheduler():
    refresh_job.manager = RefreshJobManager()
    shutdown_scheduler()
    yield
    shutdown_scheduler()


# ── helpers ───────────────────────────────────────────────────────────────────


def _seed_stock(db, ticker: str, name: str = "Test Corp") -> Stock:
    stock = Stock(ticker=ticker, name=name, is_active=True, added_at=datetime.now(timezone.utc))
    db.add(stock)
    db.flush()
    return stock


def _seed_snapshot(db, ticker: str, scan_date: date, **kwargs) -> SetupSnapshot:
    defaults: dict = {
        "setup_type": "BREAKOUT",
        "setup_quality": "B",
        "entry_price": 100.0,
        "stop_price": 95.0,
        "target_2r": 110.0,
        "target_3r": 115.0,
        "distance_to_entry_pct": 1.5,
        "reward_risk": 2.0,
        "rs_percentile": 80.0,
        "volume_status": "HIGH",
        "trend_score": 4,
        "earnings_risk": "SAFE",
        "ready_signal": False,
        "suggested_action": "watch",
        "scanned_at": datetime.now(timezone.utc),
    }
    defaults.update(kwargs)
    snap = SetupSnapshot(ticker=ticker, scan_date=scan_date, **defaults)
    db.add(snap)
    db.flush()
    return snap


# ── S1–S5: API tests ──────────────────────────────────────────────────────────


class TestSetupMonitorEndpoint:
    def test_s1_cold_start_returns_200_empty(self, client):
        """S1: 无 snapshot → 200 with total=0 items=[]."""
        resp = client.get("/api/cockpit/setup-monitor")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        data = body["data"]
        assert data["summary"]["total"] == 0
        assert data["items"] == []

    def test_s2_with_snapshots_returns_correct_structure(self, client, db_session):
        """S2: 有 snapshot → 200，summary 计数正确，items 含核心字段。"""
        _seed_stock(db_session, "NVDA", "NVIDIA Corp")
        _seed_stock(db_session, "AAPL", "Apple Inc")
        _seed_snapshot(db_session, "NVDA", date(2026, 4, 25), ready_signal=True, suggested_action="enter")
        _seed_snapshot(db_session, "AAPL", date(2026, 4, 25), suggested_action="watch")
        db_session.commit()

        resp = client.get("/api/cockpit/setup-monitor")
        assert resp.status_code == 200
        data = resp.json()["data"]

        summary = data["summary"]
        assert summary["total"] == 2
        assert summary["ready"] == 1
        assert summary["near"] == 1

        items = data["items"]
        assert len(items) == 2

        # enter-action item should come first (sort order)
        nvda_item = next(i for i in items if i["ticker"] == "NVDA")
        assert nvda_item["stockName"] == "NVIDIA Corp"
        assert nvda_item["setupType"] == "BREAKOUT"
        assert nvda_item["readySignal"] is True
        assert nvda_item["suggestedAction"] == "enter"
        assert nvda_item["scanDate"] == "2026-04-25"

        aapl_item = next(i for i in items if i["ticker"] == "AAPL")
        assert aapl_item["stockName"] == "Apple Inc"
        assert aapl_item["readySignal"] is False

    def test_s3_filter_ready_returns_only_enter_items(self, client, db_session):
        """S3: filter=ready 只返回 suggestedAction=enter 的 item。"""
        _seed_stock(db_session, "NVDA", "NVIDIA Corp")
        _seed_stock(db_session, "AAPL", "Apple Inc")
        _seed_snapshot(db_session, "NVDA", date(2026, 4, 25), ready_signal=True, suggested_action="enter")
        _seed_snapshot(db_session, "AAPL", date(2026, 4, 25), suggested_action="watch")
        db_session.commit()

        resp = client.get("/api/cockpit/setup-monitor?filter=ready")
        assert resp.status_code == 200
        data = resp.json()["data"]
        assert data["summary"]["total"] == 2  # summary always shows full count
        assert len(data["items"]) == 1
        assert data["items"][0]["ticker"] == "NVDA"

    def test_s4_filter_multi_bucket_returns_correct_subset(self, client, db_session):
        """S4: filter=broken,extended 只返回对应两个 bucket。"""
        _seed_stock(db_session, "AAA", "Alpha Corp")
        _seed_stock(db_session, "BBB", "Beta Corp")
        _seed_stock(db_session, "CCC", "Gamma Corp")
        _seed_snapshot(db_session, "AAA", date(2026, 4, 25),
                       setup_type="BROKEN", suggested_action="exit",
                       setup_quality=None, entry_price=None, stop_price=None,
                       target_2r=None, target_3r=None)
        _seed_snapshot(db_session, "BBB", date(2026, 4, 25),
                       setup_type="EXTENDED", suggested_action="reduce",
                       setup_quality=None, entry_price=None, stop_price=None,
                       target_2r=None, target_3r=None)
        _seed_snapshot(db_session, "CCC", date(2026, 4, 25), suggested_action="watch")
        db_session.commit()

        resp = client.get("/api/cockpit/setup-monitor?filter=broken,extended")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        assert len(items) == 2
        tickers = {i["ticker"] for i in items}
        assert tickers == {"AAA", "BBB"}

    def test_s5_invalid_filter_returns_422(self, client):
        """S5: filter 含非法值 → 422 VALIDATION_ERROR."""
        resp = client.get("/api/cockpit/setup-monitor?filter=invalid_value")
        assert resp.status_code == 422
        body = resp.json()
        assert body["error"]["code"] == "VALIDATION_ERROR"

    def test_s5b_partial_invalid_filter_returns_422(self, client):
        """S5b: filter 混合合法+非法值 → 422。"""
        resp = client.get("/api/cockpit/setup-monitor?filter=ready,bogus")
        assert resp.status_code == 422


# ── S6: Scheduler test ────────────────────────────────────────────────────────


class TestSetupScheduler:
    def test_s6_setup_job_registered_with_correct_schedule(self):
        """S6: start_scheduler 注册 SETUP_JOB_ID (22:30 UTC, mon-fri)."""
        sched = start_scheduler(
            session_factory=lambda: None,
            fmp_factory=lambda: None,
            autostart=False,
        )
        job_ids = {j.id for j in sched.get_jobs()}
        assert SETUP_JOB_ID in job_ids

        job = next(j for j in sched.get_jobs() if j.id == SETUP_JOB_ID)
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["hour"] == "22"
        assert fields["minute"] == "30"
        assert fields["day_of_week"] == "mon-fri"


# ── S7: tick unit tests ───────────────────────────────────────────────────────


class TestSetupTick:
    def test_s7a_tick_calls_compute_and_store_all(self):
        """S7a: _setup_tick 正常执行时调用 SetupService.compute_and_store_all。"""
        mock_service = MagicMock()
        mock_db = MagicMock()

        with patch("app.services.refresh_job.SetupService", return_value=mock_service) as MockSetup:
            _setup_tick(lambda: mock_db, lambda: None)
            MockSetup.assert_called_once_with(mock_db)
            mock_service.compute_and_store_all.assert_called_once()

    def test_s7b_tick_swallows_exception(self):
        """S7b: _setup_tick 内部异常不向上抛（与其他 tick 行为一致）。"""
        with patch(
            "app.services.refresh_job.SetupService",
            side_effect=RuntimeError("DB down"),
        ):
            _setup_tick(lambda: MagicMock(), lambda: None)
