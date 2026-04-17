"""Background data-refresh orchestration.

Contains:
  - RefreshJobManager: in-memory, thread-safe job state tracker. Exactly one
    refresh may run at a time; `start_refresh` is idempotent while a job is in
    progress.
  - Scheduler setup: APScheduler 3.x BackgroundScheduler that fires the
    daily refresh on weekdays at 21:30 UTC (≈ US market close + 2h buffer).

Session lifetime: the FastAPI request session cannot cross into the refresh
thread (SQLAlchemy Session is not thread-safe). The manager accepts a
`session_factory` (e.g. `SessionLocal`) and the worker opens its own session.
"""
from __future__ import annotations

import logging
import threading
import traceback
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from typing import Callable

from apscheduler.schedulers.background import BackgroundScheduler
from apscheduler.triggers.cron import CronTrigger
from sqlalchemy.orm import Session

from app.external.polygon_client import PolygonClient
from app.repositories.stock_repository import StockRepository
from app.services.data_refresh_service import DataRefreshService

logger = logging.getLogger(__name__)

# Weekdays (Mon–Fri) at 21:30 UTC ≈ ET 17:30 (accounting for DST drift this
# is 16:30–17:30 ET, always post-market). US markets close 20:00 UTC DST /
# 21:00 UTC STD; 21:30 leaves a 30–90 min buffer for EOD data availability.
DAILY_REFRESH_CRON = "30 21 * * 1-5"
SCHEDULER_JOB_ID = "ma150_daily_refresh"

SessionFactory = Callable[[], Session]
PolygonFactory = Callable[[], PolygonClient]


@dataclass
class RefreshJobState:
    job_id: str | None = None
    status: str = "idle"  # idle | in_progress | completed | failed
    total: int = 0
    completed: int = 0
    failed: int = 0
    started_at: datetime | None = None
    last_refreshed_at: datetime | None = None

    def snapshot(self) -> "RefreshJobState":
        return RefreshJobState(**asdict(self))


@dataclass
class StartResult:
    job_id: str
    status: str  # "started" | "in_progress"
    total_stocks: int


class RefreshJobManager:
    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._state = RefreshJobState()
        self._thread: threading.Thread | None = None

    def start_refresh(
        self,
        session_factory: SessionFactory,
        polygon_factory: PolygonFactory,
    ) -> StartResult:
        with self._lock:
            if self._state.status == "in_progress":
                return StartResult(
                    job_id=self._state.job_id or "",
                    status="in_progress",
                    total_stocks=self._state.total,
                )

            # Snapshot active stocks using a short-lived session; the worker
            # opens its own for the long-running batch.
            with _session_scope(session_factory) as db:
                stocks = StockRepository(db).list_active()
                total = len(stocks)
                stock_ids = [s.id for s in stocks]

            now = datetime.now(timezone.utc)
            job_id = f"refresh-{now.strftime('%Y%m%d-%H%M%S')}"
            self._state = RefreshJobState(
                job_id=job_id,
                status="in_progress",
                total=total,
                completed=0,
                failed=0,
                started_at=now,
                last_refreshed_at=self._state.last_refreshed_at,
            )

            thread = threading.Thread(
                target=self._run,
                args=(job_id, stock_ids, session_factory, polygon_factory),
                name=f"ma150-refresh-{job_id}",
                daemon=True,
            )
            self._thread = thread

        thread.start()
        return StartResult(job_id=job_id, status="started", total_stocks=total)

    def get_status(self) -> RefreshJobState:
        with self._lock:
            return self._state.snapshot()

    def _run(
        self,
        job_id: str,
        stock_ids: list[int],
        session_factory: SessionFactory,
        polygon_factory: PolygonFactory,
    ) -> None:
        try:
            with _session_scope(session_factory) as db:
                service = DataRefreshService(db, polygon=polygon_factory())
                batch = service.refresh_all(stock_ids)
                service.purge_old_logs()

            with self._lock:
                self._state.status = "completed"
                self._state.completed = batch["completed"]
                self._state.failed = batch["failed"]
                self._state.last_refreshed_at = datetime.now(timezone.utc)
        except Exception:  # noqa: BLE001 — top-level worker boundary
            logger.error("refresh job %s crashed\n%s", job_id, traceback.format_exc())
            with self._lock:
                self._state.status = "failed"


# Module-level singleton
manager = RefreshJobManager()


# ----- Scheduler management ---------------------------------------------------


_scheduler: BackgroundScheduler | None = None
_scheduler_lock = threading.Lock()


def start_scheduler(
    session_factory: SessionFactory,
    polygon_factory: PolygonFactory,
    *,
    autostart: bool = True,
) -> BackgroundScheduler:
    """Create and (optionally) start the daily refresh scheduler.

    Returns the scheduler so tests can inspect schedules. Safe to call twice;
    subsequent calls return the existing instance.
    """
    global _scheduler
    with _scheduler_lock:
        if _scheduler is not None:
            return _scheduler

        sched = BackgroundScheduler(timezone="UTC")
        sched.add_job(
            _scheduler_tick,
            trigger=CronTrigger.from_crontab(DAILY_REFRESH_CRON, timezone="UTC"),
            id=SCHEDULER_JOB_ID,
            args=[session_factory, polygon_factory],
            replace_existing=True,
        )
        if autostart:
            sched.start()
        _scheduler = sched
        return sched


def shutdown_scheduler() -> None:
    global _scheduler
    with _scheduler_lock:
        if _scheduler is None:
            return
        try:
            if _scheduler.running:
                _scheduler.shutdown(wait=False)
        finally:
            _scheduler = None


def _scheduler_tick(
    session_factory: SessionFactory,
    polygon_factory: PolygonFactory,
) -> None:
    try:
        manager.start_refresh(session_factory, polygon_factory)
    except Exception:  # noqa: BLE001
        logger.error("scheduled refresh tick failed\n%s", traceback.format_exc())


# ----- helpers ---------------------------------------------------------------


class _session_scope:
    """Context manager: open a session via factory, close on exit."""

    def __init__(self, factory: SessionFactory) -> None:
        self._factory = factory
        self._session: Session | None = None

    def __enter__(self) -> Session:
        self._session = self._factory()
        return self._session

    def __exit__(self, *exc) -> None:
        if self._session is not None:
            self._session.close()
