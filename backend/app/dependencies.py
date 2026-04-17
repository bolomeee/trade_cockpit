from __future__ import annotations

from typing import Callable

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import SessionLocal, get_db
from app.external.polygon_client import PolygonClient
from app.repositories.stock_repository import StockRepository
from app.services.watchlist_service import WatchlistService


def get_polygon_client() -> PolygonClient:
    return PolygonClient()


def get_session_factory() -> Callable[[], Session]:
    """Return a callable that produces fresh Sessions.

    Used by background jobs (refresh) that must not reuse request-scoped
    sessions. Tests override this to bind to the in-memory test engine.
    """
    return SessionLocal


def get_watchlist_service(
    db: Session = Depends(get_db),
    polygon: PolygonClient = Depends(get_polygon_client),
) -> WatchlistService:
    return WatchlistService(repo=StockRepository(db), polygon=polygon)
