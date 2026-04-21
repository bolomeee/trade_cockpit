from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.market_breakout_repository import MarketBreakoutRepository
from app.repositories.market_index_repository import (
    MARKET_INDEX_SYMBOLS,
    MarketIndexRepository,
)
from app.schemas.market import BreakoutItemOut, BreakoutSnapshotOut, MarketIndexOut
from app.schemas.watchlist import ResponseEnvelope
from app.services import scanner_params as P

router = APIRouter(prefix="/api/market", tags=["market"])


@router.get("/overview", response_model=ResponseEnvelope[list[MarketIndexOut]])
def get_overview(
    db: Session = Depends(get_db),
) -> ResponseEnvelope[list[MarketIndexOut]]:
    rows = MarketIndexRepository(db).list_latest_by_symbol(MARKET_INDEX_SYMBOLS)
    return ResponseEnvelope(data=[MarketIndexOut.model_validate(r) for r in rows])


@router.get("/breakouts", response_model=ResponseEnvelope[BreakoutSnapshotOut])
def get_breakouts(
    type: str | None = Query(
        default=None,
        description="Comma-separated signal_type filter. Omit for default (A1/A2/B2).",
    ),
    db: Session = Depends(get_db),
) -> ResponseEnvelope[BreakoutSnapshotOut]:
    if type is None:
        signal_types: tuple[str, ...] = P.DEFAULT_API_SIGNAL_TYPES
    else:
        requested = tuple(s.strip() for s in type.split(",") if s.strip())
        invalid = [s for s in requested if s not in P.ALL_SIGNAL_TYPES]
        if invalid:
            raise HTTPException(
                status_code=400,
                detail=f"invalid signal_type: {','.join(invalid)}",
            )
        signal_types = requested or P.DEFAULT_API_SIGNAL_TYPES

    snap = MarketBreakoutRepository(db).get_latest_snapshot(signal_types=signal_types)
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
            signal_type=str(m.signal_type),
            close_price=round(m.close_price, 2),
            ma150_value=round(m.ma150_value, 2),
            pct_above_ma150=round(m.pct_above_ma150, 2),
            slope_value=round(m.slope_value, 4),
            volume=int(m.volume) if m.volume is not None else None,
            volume_ratio_20=(
                round(m.volume_ratio_20, 2) if m.volume_ratio_20 is not None else None
            ),
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
