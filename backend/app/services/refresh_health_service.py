"""D108 / F221: aggregate scheduled-refresh health for the TopNav alert badge.

Read-only. Staleness is derived from table data (`market_scan_universe.last_seen_at`,
`market_breakout_scans.scanned_at`) so it survives the 7-day `system_logs` purge —
a refresh that failed weeks ago still shows as stale even after its ERROR log is gone.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.cockpit_pool_cache import CockpitPoolCache
from app.repositories.market_breakout_repository import MarketBreakoutRepository
from app.repositories.market_scan_universe_repository import MarketScanUniverseRepository
from app.repositories.system_log_repository import SystemLogRepository

# Staleness thresholds (days). universe refreshes weekly (Mon); breakout every
# weekday, so >3 days covers a normal weekend gap before flagging.
UNIVERSE_STALE_DAYS = 8.0
BREAKOUT_STALE_DAYS = 3.0
RECENT_ERROR_WINDOW_HOURS = 24
RECENT_ERROR_SCAN_LIMIT = 500


def _freshness(last_at: datetime | None, now: datetime, stale_days: float) -> dict[str, Any]:
    if last_at is None:
        return {"last_at": None, "age_days": None, "stale": True}
    # Stored timestamps are naive UTC (SQLite drops tzinfo); normalize to compare.
    aware = last_at if last_at.tzinfo else last_at.replace(tzinfo=timezone.utc)
    age_days = (now - aware).total_seconds() / 86400.0
    return {"last_at": last_at, "age_days": round(age_days, 2), "stale": age_days > stale_days}


class RefreshHealthService:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_health(self) -> dict[str, Any]:
        now = datetime.now(timezone.utc)

        universe_last = MarketScanUniverseRepository(self.db).latest_refresh_time()
        breakout_snapshot = MarketBreakoutRepository(self.db).get_latest_snapshot()
        breakout_last = breakout_snapshot.scanned_at if breakout_snapshot else None

        pool_cache_rows = int(
            self.db.execute(select(func.count()).select_from(CockpitPoolCache)).scalar_one()
        )

        return {
            "universe": _freshness(universe_last, now, UNIVERSE_STALE_DAYS),
            "breakout": _freshness(breakout_last, now, BREAKOUT_STALE_DAYS),
            "pool_cache_rows": pool_cache_rows,
            "recent_errors": self._count_recent_errors(now),
        }

    def _count_recent_errors(self, now: datetime) -> int:
        cutoff = now.replace(tzinfo=None) - timedelta(hours=RECENT_ERROR_WINDOW_HOURS)
        logs = SystemLogRepository(self.db).list_recent(
            limit=RECENT_ERROR_SCAN_LIMIT, level="ERROR"
        )
        return sum(1 for log in logs if log.created_at is not None and log.created_at >= cutoff)
