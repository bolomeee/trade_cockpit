from __future__ import annotations

from typing import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.external.fmp_client import FmpClient, default_rate_limiter
from app.repositories.journal_repository import JournalRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.system_log_repository import SystemLogRepository
from app.services.journal_service import JournalService
from app.services.watchlist_service import WatchlistService


def get_fmp_client() -> FmpClient:
    return FmpClient(rate_limiter=default_rate_limiter())


def get_session_factory() -> Callable[[], Session]:
    """Return a callable that produces fresh Sessions.

    Used by background jobs (refresh) that must not reuse request-scoped
    sessions. Tests override this to bind to the in-memory test engine.
    """
    return SessionLocal


def get_watchlist_service(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> WatchlistService:
    return WatchlistService(repo=StockRepository(db), fmp=fmp)


def get_journal_service(db: Session = Depends(get_db)) -> JournalService:
    return JournalService(
        journal_repo=JournalRepository(db),
        stock_repo=StockRepository(db),
    )


def get_system_log_repository(db: Session = Depends(get_db)) -> SystemLogRepository:
    return SystemLogRepository(db)
