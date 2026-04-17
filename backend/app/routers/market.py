from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.market_index_repository import (
    MARKET_INDEX_SYMBOLS,
    MarketIndexRepository,
)
from app.schemas.market import MarketIndexOut
from app.schemas.watchlist import ResponseEnvelope

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview", response_model=ResponseEnvelope[list[MarketIndexOut]])
def get_overview(
    db: Session = Depends(get_db),
) -> ResponseEnvelope[list[MarketIndexOut]]:
    rows = MarketIndexRepository(db).list_latest_by_symbol(MARKET_INDEX_SYMBOLS)
    return ResponseEnvelope(data=[MarketIndexOut.model_validate(r) for r in rows])
