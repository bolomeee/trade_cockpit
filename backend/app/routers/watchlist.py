from __future__ import annotations

from fastapi import APIRouter, Depends, status

from app.dependencies import get_watchlist_service
from app.schemas.watchlist import (
    AddStockRequest,
    BulkAddRequest,
    BulkAddResult,
    DeleteStockResponse,
    ResponseEnvelope,
    WatchlistCreatedItem,
    WatchlistItem,
)
from app.services.watchlist_service import WatchlistService

router = APIRouter(prefix="/api/watchlist", tags=["watchlist"])


@router.get("", response_model=ResponseEnvelope[list[WatchlistItem]])
def list_watchlist(
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[list[WatchlistItem]]:
    items = service.list_watchlist()
    return ResponseEnvelope(data=[WatchlistItem.model_validate(i) for i in items])


@router.post(
    "",
    response_model=ResponseEnvelope[WatchlistCreatedItem],
    status_code=status.HTTP_201_CREATED,
)
def add_stock(
    payload: AddStockRequest,
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[WatchlistCreatedItem]:
    stock = service.add_stock(payload.ticker)
    data = service.build_created_payload(stock)
    return ResponseEnvelope(data=WatchlistCreatedItem.model_validate(data))


@router.post(
    "/bulk",
    response_model=ResponseEnvelope[BulkAddResult],
    status_code=status.HTTP_200_OK,
)
def bulk_add(
    payload: BulkAddRequest,
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[BulkAddResult]:
    result = service.bulk_add_stocks(payload.tickers)
    return ResponseEnvelope(data=BulkAddResult.model_validate(result))


@router.delete("/{ticker}", response_model=ResponseEnvelope[DeleteStockResponse])
def remove_stock(
    ticker: str,
    service: WatchlistService = Depends(get_watchlist_service),
) -> ResponseEnvelope[DeleteStockResponse]:
    removed_ticker = service.remove_stock(ticker)
    return ResponseEnvelope(
        data=DeleteStockResponse(ticker=removed_ticker, removed=True)
    )
