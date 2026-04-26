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

from app.config import settings
from app.external.fmp_client import FmpClient
from app.repositories.stock_repository import StockRepository
from app.services.cockpit.earnings_service import EarningsService
from app.services.cockpit.market_regime_service import MarketRegimeService
from app.services.cockpit.pending_order_expirer import expire_due_pending_orders
from app.services.cockpit.setup_service import SetupService
from app.services.data_refresh_service import DataRefreshService
from app.services.market_refresh_service import MarketRefreshService
from app.services.market_scanner_service import MarketScannerService
from app.services.universe_refresh_service import UniverseRefreshService

logger = logging.getLogger(__name__)

# Weekdays (Mon–Fri) at 21:30 UTC ≈ ET 17:30 (accounting for DST drift this
# is 16:30–17:30 ET, always post-market). US markets close 20:00 UTC DST /
# 21:00 UTC STD; 21:30 leaves a 30–90 min buffer for EOD data availability.
DAILY_REFRESH_CRON = "30 21 * * 1-5"
SCHEDULER_JOB_ID = "ma150_daily_refresh"
SCANNER_JOB_ID = "ma150_market_scanner"
UNIVERSE_JOB_ID = "ma150_universe_refresh"
EARNINGS_JOB_ID = "cockpit_earnings_refresh"
REGIME_JOB_ID = "cockpit_regime_refresh"
SETUP_JOB_ID = "cockpit_setup_refresh"
PENDING_ORDERS_EXPIRER_CRON = "35 22 * * 1-5"
PENDING_ORDERS_EXPIRER_JOB_ID = "cockpit_pending_orders_expirer"

SessionFactory = Callable[[], Session]
FmpFactory = Callable[[], FmpClient]


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
        fmp_factory: FmpFactory,
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
                args=(job_id, stock_ids, session_factory, fmp_factory),
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
        fmp_factory: FmpFactory,
    ) -> None:
        try:
            with _session_scope(session_factory) as db:
                fmp = fmp_factory()
                service = DataRefreshService(db, fmp=fmp)
                batch = service.refresh_all(stock_ids)
                service.purge_old_logs()
                # F006: refresh market indices after stocks. Isolated: a market
                # failure must not mark the overall job failed.
                try:
                    MarketRefreshService(db, fmp=fmp).refresh_all()
                except Exception:  # noqa: BLE001
                    logger.error("market refresh failed\n%s", traceback.format_exc())

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
    fmp_factory: FmpFactory,
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
            args=[session_factory, fmp_factory],
            replace_existing=True,
        )
        # F105 D042: independent scanner cron, weekdays, 15m after watchlist refresh
        sched.add_job(
            _scanner_tick,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=settings.scanner_cron_hour,
                minute=settings.scanner_cron_minute,
                timezone="UTC",
            ),
            id=SCANNER_JOB_ID,
            args=[session_factory, fmp_factory],
            replace_existing=True,
        )
        # F105 D038: monthly universe refresh
        sched.add_job(
            _universe_tick,
            trigger=CronTrigger(
                day=settings.universe_cron_day,
                hour=settings.universe_cron_hour,
                minute=settings.universe_cron_minute,
                timezone="UTC",
            ),
            id=UNIVERSE_JOB_ID,
            args=[session_factory, fmp_factory],
            replace_existing=True,
        )
        # F204-b: earnings calendar refresh, weekdays 05:30 UTC (before scanner at 06:15)
        sched.add_job(
            _earnings_tick,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=settings.earnings_cron_hour,
                minute=settings.earnings_cron_minute,
                timezone="UTC",
            ),
            id=EARNINGS_JOB_ID,
            args=[session_factory, fmp_factory],
            replace_existing=True,
        )
        # F201-b: regime ETF refresh + scoring, weekdays 22:15 UTC (after main refresh at 21:30)
        sched.add_job(
            _regime_tick,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=settings.regime_cron_hour,
                minute=settings.regime_cron_minute,
                timezone="UTC",
            ),
            id=REGIME_JOB_ID,
            args=[session_factory, fmp_factory],
            replace_existing=True,
        )
        # F202-b: setup snapshot scan, weekdays 22:30 UTC (after regime at 22:15)
        sched.add_job(
            _setup_tick,
            trigger=CronTrigger(
                day_of_week="mon-fri",
                hour=settings.setup_cron_hour,
                minute=settings.setup_cron_minute,
                timezone="UTC",
            ),
            id=SETUP_JOB_ID,
            args=[session_factory, fmp_factory],
            replace_existing=True,
        )
        # F206-b2: pending_orders EXPIRED auto-transition, weekdays 22:35 UTC (after setup tick)
        sched.add_job(
            _pending_orders_expirer_tick,
            trigger=CronTrigger.from_crontab(PENDING_ORDERS_EXPIRER_CRON, timezone="UTC"),
            id=PENDING_ORDERS_EXPIRER_JOB_ID,
            args=[session_factory],
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
    fmp_factory: FmpFactory,
) -> None:
    try:
        manager.start_refresh(session_factory, fmp_factory)
    except Exception:  # noqa: BLE001
        logger.error("scheduled refresh tick failed\n%s", traceback.format_exc())


def _scanner_tick(
    session_factory: SessionFactory,
    fmp_factory: FmpFactory,
) -> None:
    """APScheduler tick for MarketScannerService (F105 D042)."""
    try:
        with _session_scope(session_factory) as db:
            MarketScannerService(db, fmp=fmp_factory()).run_scan()
    except Exception:  # noqa: BLE001 — service logs its own errors; this is the belt
        logger.error("scanner tick failed\n%s", traceback.format_exc())


def _universe_tick(
    session_factory: SessionFactory,
    fmp_factory: FmpFactory,
) -> None:
    """APScheduler tick for UniverseRefreshService (F105 D038)."""
    try:
        with _session_scope(session_factory) as db:
            UniverseRefreshService(db, fmp=fmp_factory()).refresh()
    except Exception:  # noqa: BLE001
        logger.error("universe tick failed\n%s", traceback.format_exc())


def _earnings_tick(
    session_factory: SessionFactory,
    fmp_factory: FmpFactory,
) -> None:
    """APScheduler tick for EarningsService (F204-b): weekdays 05:30 UTC."""
    try:
        with _session_scope(session_factory) as db:
            EarningsService(db, fmp=fmp_factory()).fetch_and_store()
    except Exception:  # noqa: BLE001
        logger.error("earnings tick failed\n%s", traceback.format_exc())


def _regime_tick(
    session_factory: SessionFactory,
    fmp_factory: FmpFactory,
) -> None:
    """APScheduler tick for regime ETF refresh + scoring (F201-b): weekdays 22:15 UTC."""
    try:
        with _session_scope(session_factory) as db:
            fmp = fmp_factory()
            MarketRefreshService(db, fmp=fmp).refresh_regime_etfs()
            MarketRegimeService(db).compute_and_store()
    except Exception:  # noqa: BLE001
        logger.error("regime tick failed\n%s", traceback.format_exc())


def _setup_tick(
    session_factory: SessionFactory,
    fmp_factory: FmpFactory,
) -> None:
    """APScheduler tick for setup snapshot scan (F202-b): weekdays 22:30 UTC."""
    try:
        with _session_scope(session_factory) as db:
            SetupService(db).compute_and_store_all()
    except Exception:  # noqa: BLE001
        logger.error("setup tick failed\n%s", traceback.format_exc())


def _pending_orders_expirer_tick(session_factory: SessionFactory) -> None:
    """APScheduler tick for pending_orders auto-EXPIRED (F206-b2): weekdays 22:35 UTC."""
    try:
        with _session_scope(session_factory) as db:
            expire_due_pending_orders(db)
    except Exception:  # noqa: BLE001
        logger.error("pending_orders expirer tick failed\n%s", traceback.format_exc())


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
