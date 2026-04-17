from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.signal import (
    SignalBoardItem,
    TickerSignalDetail,
)
from app.schemas.watchlist import ResponseEnvelope
from app.services.signal_service import SignalService

MAX_HISTORY_DAYS = 250
DEFAULT_HISTORY_DAYS = 30

router = APIRouter(prefix="/api/signals", tags=["signals"])


def get_signal_service(db: Session = Depends(get_db)) -> SignalService:
    return SignalService(db)


@router.get("", response_model=ResponseEnvelope[list[SignalBoardItem]])
def list_signals(
    service: SignalService = Depends(get_signal_service),
) -> ResponseEnvelope[list[SignalBoardItem]]:
    items = service.list_board()
    return ResponseEnvelope(
        data=[SignalBoardItem.model_validate(i) for i in items]
    )


@router.get("/{ticker}", response_model=ResponseEnvelope[TickerSignalDetail])
def get_ticker_signal(
    ticker: str,
    days: int = Query(
        DEFAULT_HISTORY_DAYS, ge=1, le=MAX_HISTORY_DAYS
    ),
    service: SignalService = Depends(get_signal_service),
) -> ResponseEnvelope[TickerSignalDetail]:
    payload = service.get_ticker_detail(ticker, days)
    return ResponseEnvelope(data=TickerSignalDetail.model_validate(payload))
