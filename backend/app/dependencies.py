from __future__ import annotations

from fastapi import Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.external.polygon_client import PolygonClient
from app.repositories.stock_repository import StockRepository
from app.services.watchlist_service import WatchlistService


def get_polygon_client() -> PolygonClient:
    return PolygonClient()


def get_watchlist_service(
    db: Session = Depends(get_db),
    polygon: PolygonClient = Depends(get_polygon_client),
) -> WatchlistService:
    return WatchlistService(repo=StockRepository(db), polygon=polygon)
