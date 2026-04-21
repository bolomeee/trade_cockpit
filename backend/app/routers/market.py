from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.market_breakout_repository import MarketBreakoutRepository
from app.repositories.market_index_repository import (
    MARKET_INDEX_SYMBOLS,
    MarketIndexRepository,
)
from app.schemas.market import BreakoutItemOut, BreakoutSnapshotOut, MarketIndexOut
from app.schemas.watchlist import ResponseEnvelope

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview", response_model=ResponseEnvelope[list[MarketIndexOut]])
def get_overview(
    db: Session = Depends(get_db),
) -> ResponseEnvelope[list[MarketIndexOut]]:
    rows = MarketIndexRepository(db).list_latest_by_symbol(MARKET_INDEX_SYMBOLS)
    return ResponseEnvelope(data=[MarketIndexOut.model_validate(r) for r in rows])


@router.get("/breakouts", response_model=ResponseEnvelope[BreakoutSnapshotOut])
def get_breakouts(
    db: Session = Depends(get_db),
) -> ResponseEnvelope[BreakoutSnapshotOut]:
    snap = MarketBreakoutRepository(db).get_latest_snapshot()
    if snap is None:
        return ResponseEnvelope(
            data=BreakoutSnapshotOut(
                scan_date=None, scanned_at=None, items=[], total=0
            )
        )
    items = [
        BreakoutItemOut(
            ticker=str(m.ticker),
            company_name=str(m.company_name),
            close_price=round(m.close_price, 2),
            ma150_value=round(m.ma150_value, 2),
            pct_above_ma150=round(m.pct_above_ma150, 2),
            market_cap=int(m.market_cap),
        )
        for m in snap.items
    ]
    return ResponseEnvelope(
        data=BreakoutSnapshotOut(
            scan_date=snap.scan_date,
            scanned_at=snap.scanned_at,
            items=items,
            total=len(items),
        )
    )
