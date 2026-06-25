"""F221 / D108: refresh cadence + visibility tests.

Covers:
- scheduler cadence change (universe weekly, pool-cache weekdays)
- universe soft-degradation → ERROR log (price/volume mostly missing)
- RefreshHealthService staleness + /api/refresh-health endpoint
"""
from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from unittest.mock import MagicMock

import pytest
from apscheduler.triggers.cron import CronTrigger

import app.services.refresh_job as refresh_job
from app.repositories.market_breakout_repository import (
    BreakoutScanRow,
    MarketBreakoutRepository,
)
from app.repositories.market_scan_universe_repository import (
    MarketScanUniverseRepository,
    UniverseUpsertRow,
)
from app.repositories.system_log_repository import SystemLogRepository
from app.services.refresh_health_service import RefreshHealthService
from app.services.refresh_job import (
    POOL_CACHE_JOB_ID,
    UNIVERSE_JOB_ID,
    shutdown_scheduler,
    start_scheduler,
)
from app.services.universe_refresh_service import UniverseRefreshService


@pytest.fixture(autouse=True)
def _reset_scheduler():
    shutdown_scheduler()
    yield
    shutdown_scheduler()


def _trigger_fields(job) -> dict[str, str]:
    assert isinstance(job.trigger, CronTrigger)
    return {f.name: str(f) for f in job.trigger.fields}


# ---------------------------------------------------------------------------
# Cadence (D108)
# ---------------------------------------------------------------------------

def test_universe_job_is_weekly_monday_not_monthly():
    sched = start_scheduler(
        session_factory=MagicMock(), fmp_factory=MagicMock(), autostart=False
    )
    job = next(j for j in sched.get_jobs() if j.id == UNIVERSE_JOB_ID)
    fields = _trigger_fields(job)
    assert "mon" in fields["day_of_week"]
    assert fields["hour"] == "5"
    assert fields["minute"] == "0"
    # No longer monthly: day-of-month must be unrestricted.
    assert fields["day"] == "*"


def test_pool_cache_job_runs_weekdays_0630():
    sched = start_scheduler(
        session_factory=MagicMock(), fmp_factory=MagicMock(), autostart=False
    )
    job = next(j for j in sched.get_jobs() if j.id == POOL_CACHE_JOB_ID)
    fields = _trigger_fields(job)
    assert fields["hour"] == "6"
    assert fields["minute"] == "30"
    # weekdays only (was Mon-only "1"); must be restricted, not every day.
    assert fields["day_of_week"] != "*"
    assert "5" in fields["day_of_week"]


# ---------------------------------------------------------------------------
# Universe soft-degradation (2a)
# ---------------------------------------------------------------------------

def _screener_row(symbol: str, *, price=None, volume=None) -> dict:
    row = {"symbol": symbol, "companyName": f"{symbol} Inc", "marketCap": 60_000_000_000, "exchange": "NYSE"}
    if price is not None:
        row["price"] = price
    if volume is not None:
        row["volume"] = volume
    return row


def test_universe_mostly_null_price_logs_error(db_session, fake_fmp):
    # All rows missing price/volume → "successful" refresh but unusable data.
    fake_fmp.screener_universe_result = [
        _screener_row("AAA"),
        _screener_row("BBB"),
        _screener_row("CCC"),
    ]
    result = UniverseRefreshService(db_session, fake_fmp).refresh()
    assert result.status == "ok"  # no exception — it "succeeded"

    errors = SystemLogRepository(db_session).list_recent(level="ERROR")
    assert any(
        log.source == "universe_refresher" and "degraded" in log.message for log in errors
    )


def test_universe_with_price_volume_logs_ok_not_error(db_session, fake_fmp):
    fake_fmp.screener_universe_result = [
        _screener_row("AAA", price=100.0, volume=1_000_000),
        _screener_row("BBB", price=50.0, volume=2_000_000),
    ]
    result = UniverseRefreshService(db_session, fake_fmp).refresh()
    assert result.status == "ok"

    errors = SystemLogRepository(db_session).list_recent(level="ERROR")
    assert not any(log.source == "universe_refresher" for log in errors)


# ---------------------------------------------------------------------------
# RefreshHealthService + endpoint (2b/2c)
# ---------------------------------------------------------------------------

def _seed_universe(db_session, when: datetime) -> None:
    MarketScanUniverseRepository(db_session).upsert_many(
        [
            UniverseUpsertRow(
                ticker="AAA",
                company_name="Alpha",
                exchange="NYSE",
                market_cap=60_000_000_000,
                last_price=100.0,
                last_volume=1_000_000,
            )
        ],
        now=when,
    )


def _seed_breakout(db_session, when: datetime) -> None:
    MarketBreakoutRepository(db_session).replace_scan(
        [
            BreakoutScanRow(
                scan_date=when.date(),
                ticker="AAA",
                company_name="Alpha",
                signal_type="a2_slope_flip",
                close_price=100.0,
                ma150_value=90.0,
                pct_above_ma150=11.1,
                slope_value=0.5,
                market_cap=60_000_000_000,
                scanned_at=when,
            )
        ]
    )


def test_health_empty_is_stale(db_session):
    health = RefreshHealthService(db_session).get_health()
    assert health["universe"]["stale"] is True
    assert health["universe"]["last_at"] is None
    assert health["universe"]["age_days"] is None
    assert health["breakout"]["stale"] is True
    assert health["pool_cache_rows"] == 0
    assert health["recent_errors"] == 0


def test_health_fresh_not_stale(db_session):
    now = datetime.now(timezone.utc).replace(tzinfo=None)
    _seed_universe(db_session, now)
    _seed_breakout(db_session, now)

    health = RefreshHealthService(db_session).get_health()
    assert health["universe"]["stale"] is False
    assert health["universe"]["age_days"] is not None and health["universe"]["age_days"] < 1
    assert health["breakout"]["stale"] is False


def test_health_old_universe_is_stale(db_session):
    old = datetime.now(timezone.utc).replace(tzinfo=None) - timedelta(days=30)
    _seed_universe(db_session, old)

    health = RefreshHealthService(db_session).get_health()
    assert health["universe"]["stale"] is True
    assert health["universe"]["age_days"] >= 29


def test_health_counts_recent_errors(db_session):
    SystemLogRepository(db_session).create(
        level="ERROR", source="universe_refresher", message="boom"
    )
    health = RefreshHealthService(db_session).get_health()
    assert health["recent_errors"] >= 1


def test_refresh_health_endpoint_shape(client):
    resp = client.get("/api/refresh-health")
    assert resp.status_code == 200
    data = resp.json()["data"]
    # camelCase contract
    assert set(data.keys()) == {"universe", "breakout", "poolCacheRows", "recentErrors"}
    assert set(data["universe"].keys()) == {"lastAt", "ageDays", "stale"}
    # empty test DB → universe stale
    assert data["universe"]["stale"] is True
