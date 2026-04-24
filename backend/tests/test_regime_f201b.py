"""Tests for F201-b Market Regime 接入层.

Sprint Contract 标准 S1–S8:
  S1. GET /api/cockpit/regime 冷启动（无 snapshot）→ 404
  S2. 有 snapshot 时 → 200，regime/marketScore/subscores/computedAt 存在
  S3. subscores 字段与 snapshot 6 个 sub-score 字段精确匹配
  S4. indices 固定 3 条 (SPY/QQQ/IWM)
  S5. sectors 固定 11 条 (SHARED.SECTOR_ETFS)
  S6. market_indices 无数据时 indices/sectors close=null，state 降级
  S7. start_scheduler 注册 REGIME_JOB_ID (22:15 UTC, mon-fri)
  S8. _regime_tick 调用 refresh_regime_etfs + compute_and_store，异常不上抛
"""
from __future__ import annotations

import json
from datetime import date, datetime, timezone
from unittest.mock import MagicMock, patch

import pytest

from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.services import refresh_job
from app.services.cockpit.cockpit_params import SHARED
from app.services.refresh_job import (
    REGIME_JOB_ID,
    RefreshJobManager,
    _regime_tick,
    shutdown_scheduler,
    start_scheduler,
)


@pytest.fixture(autouse=True)
def _reset_scheduler():
    refresh_job.manager = RefreshJobManager()
    shutdown_scheduler()
    yield
    shutdown_scheduler()


def _seed_snapshot(db_session, regime: str = "CONSTRUCTIVE") -> MarketRegimeSnapshot:
    snap = MarketRegimeSnapshot(
        date=date(2026, 4, 24),
        regime=regime,
        market_score=68,
        spy_trend_score=18,
        qqq_trend_score=14,
        iwm_breadth_score=9,
        sector_participation_score=14,
        risk_appetite_score=7,
        volatility_stress_score=6,
        allowed_exposure_pct=70.0,
        single_trade_risk_pct=1.0,
        preferred_setups=json.dumps(["BREAKOUT", "PULLBACK"]),
        avoid_setups=json.dumps(["EXTENDED"]),
        computed_at=datetime(2026, 4, 24, 22, 5, 0, tzinfo=timezone.utc),
    )
    db_session.add(snap)
    db_session.commit()
    return snap


# ─────────────────────────── S1–S6: API tests ───────────────────────────────


class TestRegimeApiEndpoint:
    def test_s1_cold_start_returns_404(self, client):
        """S1: 无 snapshot 时返回 404 NOT_FOUND."""
        resp = client.get("/api/cockpit/regime")
        assert resp.status_code == 404
        body = resp.json()
        assert body["error"]["code"] == "NOT_FOUND"

    def test_s2_with_snapshot_returns_200_full_structure(self, client, db_session):
        """S2: 有 snapshot → 200，必要顶层字段存在."""
        _seed_snapshot(db_session)
        resp = client.get("/api/cockpit/regime")
        assert resp.status_code == 200
        body = resp.json()
        assert body["message"] == "success"
        data = body["data"]
        assert data["date"] == "2026-04-24"
        assert data["regime"] == "CONSTRUCTIVE"
        assert data["marketScore"] == 68
        assert data["allowedExposurePct"] == pytest.approx(70.0)
        assert data["singleTradeRiskPct"] == pytest.approx(1.0)
        assert data["preferredSetups"] == ["BREAKOUT", "PULLBACK"]
        assert data["avoidSetups"] == ["EXTENDED"]
        assert "computedAt" in data
        assert "subscores" in data
        assert "indices" in data
        assert "sectors" in data

    def test_s3_subscores_match_snapshot_fields(self, client, db_session):
        """S3: subscores camelCase 字段值与 snapshot 精确匹配."""
        _seed_snapshot(db_session)
        data = client.get("/api/cockpit/regime").json()["data"]
        subscores = data["subscores"]
        assert subscores["spyTrend"] == 18
        assert subscores["qqqTrend"] == 14
        assert subscores["iwmBreadth"] == 9
        assert subscores["sectorParticipation"] == 14
        assert subscores["riskAppetite"] == 7
        assert subscores["volatilityStress"] == 6

    def test_s4_indices_has_exactly_3_items(self, client, db_session):
        """S4: indices 固定 3 条 (SPY/QQQ/IWM)."""
        _seed_snapshot(db_session)
        data = client.get("/api/cockpit/regime").json()["data"]
        assert len(data["indices"]) == 3
        symbols = [item["symbol"] for item in data["indices"]]
        assert symbols == list(SHARED.INDEX_ETFS)

    def test_s5_sectors_has_exactly_11_items(self, client, db_session):
        """S5: sectors 固定 11 条 (SHARED.SECTOR_ETFS)."""
        _seed_snapshot(db_session)
        data = client.get("/api/cockpit/regime").json()["data"]
        assert len(data["sectors"]) == 11
        symbols = [item["symbol"] for item in data["sectors"]]
        assert symbols == list(SHARED.SECTOR_ETFS)

    def test_s6_missing_market_indices_data_degrades_gracefully(self, client, db_session):
        """S6: market_indices 无数据时 close=null，sectors state="Neutral"，indices aboveMa50/200=false."""
        _seed_snapshot(db_session)
        data = client.get("/api/cockpit/regime").json()["data"]
        for sector in data["sectors"]:
            assert sector["close"] is None
            assert sector["state"] == "Neutral"
        for index_item in data["indices"]:
            assert index_item["close"] is None
            assert index_item["aboveMa50"] is False
            assert index_item["aboveMa200"] is False


# ─────────────────────────── S7: Scheduler test ─────────────────────────────


class TestRegimeScheduler:
    def test_s7_regime_job_registered_with_correct_schedule(self):
        """S7: start_scheduler 注册 regime job (22:15 UTC, mon-fri)."""
        sched = start_scheduler(
            session_factory=lambda: None,
            fmp_factory=lambda: None,
            autostart=False,
        )
        job_ids = {j.id for j in sched.get_jobs()}
        assert REGIME_JOB_ID in job_ids

        job = next(j for j in sched.get_jobs() if j.id == REGIME_JOB_ID)
        fields = {f.name: str(f) for f in job.trigger.fields}
        assert fields["hour"] == "22"
        assert fields["minute"] == "15"
        assert fields["day_of_week"] == "mon-fri"


# ─────────────────────────── S8: tick unit tests ────────────────────────────


class TestRegimeTick:
    def test_s8a_tick_calls_refresh_and_compute(self):
        """S8a: _regime_tick 正常执行时调用 refresh_regime_etfs + compute_and_store."""
        mock_refresh_svc = MagicMock()
        mock_regime_svc = MagicMock()
        mock_fmp = MagicMock()
        mock_db = MagicMock()

        with (
            patch("app.services.refresh_job.MarketRefreshService", return_value=mock_refresh_svc) as MockRefresh,
            patch("app.services.refresh_job.MarketRegimeService", return_value=mock_regime_svc) as MockRegime,
        ):
            _regime_tick(lambda: mock_db, lambda: mock_fmp)
            MockRefresh.assert_called_once_with(mock_db, fmp=mock_fmp)
            mock_refresh_svc.refresh_regime_etfs.assert_called_once()
            MockRegime.assert_called_once_with(mock_db)
            mock_regime_svc.compute_and_store.assert_called_once()

    def test_s8b_tick_swallows_exception(self):
        """S8b: _regime_tick 内部异常不向上抛出（与其他 tick 行为一致）。"""
        with patch(
            "app.services.refresh_job.MarketRefreshService",
            side_effect=RuntimeError("FMP down"),
        ):
            _regime_tick(lambda: MagicMock(), lambda: MagicMock())
