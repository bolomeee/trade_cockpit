from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_watchlist_service
from app.schemas.stock_detail import (
    ChartData,
    Fundamentals,
    PullbackEntry,
)
from app.schemas.watchlist import ResponseEnvelope, StockSearchItem
from app.services.stock_detail_service import StockDetailService
from app.services.watchlist_service import SEARCH_LIMIT_DEFAULT, WatchlistService

router = APIRouter(prefix="/api/stocks", tags=["stocks"])


def get_stock_detail_service(db: Session = Depends(get_db)) -> StockDetailService:
    return StockDetailService(db)


@router.get("/search", response_model=ResponseEnvelope[list[StockSearchItem]])
def search_stocks(
    q: str = Query(..., min_length=1),
    limit: int = Query(SEARCH_LIMIT_DEFAULT, ge=1),
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[list[StockSearchItem]]:
    items = service.search(q, limit=limit)
    return ResponseEnvelope(data=[StockSearchItem.model_validate(i) for i in items])


@router.get("/{ticker}/chart", response_model=ResponseEnvelope[ChartData])
def get_stock_chart(
    ticker: str,
    service: StockDetailService = Depends(get_stock_detail_service),
) -> ResponseEnvelope[ChartData]:
    payload = service.get_chart(ticker)
    return ResponseEnvelope(data=ChartData.model_validate(payload))


@router.get(
    "/{ticker}/pullbacks",
    response_model=ResponseEnvelope[list[PullbackEntry]],
)
def get_stock_pullbacks(
    ticker: str,
    service: StockDetailService = Depends(get_stock_detail_service),
) -> ResponseEnvelope[list[PullbackEntry]]:
    rows = service.get_pullbacks(ticker)
    return ResponseEnvelope(
        data=[PullbackEntry.model_validate(r) for r in rows]
    )


@router.get(
    "/{ticker}/fundamentals",
    response_model=ResponseEnvelope[Fundamentals],
)
def get_stock_fundamentals(
    ticker: str,
    service: StockDetailService = Depends(get_stock_detail_service),
) -> ResponseEnvelope[Fundamentals]:
    payload = service.get_fundamentals(ticker)
    return ResponseEnvelope(data=Fundamentals.model_validate(payload))
