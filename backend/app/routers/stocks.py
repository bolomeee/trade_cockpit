from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_watchlist_service
from app.schemas.watchlist import ResponseEnvelope, StockSearchItem
from app.services.watchlist_service import SEARCH_LIMIT_DEFAULT, WatchlistService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


@router.get("/search", response_model=ResponseEnvelope[list[StockSearchItem]])
def search_stocks(
    q: str = Query(..., min_length=1),
    limit: int = Query(SEARCH_LIMIT_DEFAULT, ge=1),
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[list[StockSearchItem]]:
    items = service.search(q, limit=limit)
    return ResponseEnvelope(data=[StockSearchItem.model_validate(i) for i in items])
