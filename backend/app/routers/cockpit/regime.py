from __future__ import annotations

import json

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.repositories.market_regime_repository import MarketRegimeRepository
from app.schemas.cockpit.regime import (
    RegimeData,
    RegimeIndexItem,
    RegimeResponse,
    RegimeSectorItem,
    RegimeSubscores,
)
from app.services.cockpit.market_regime_service import MarketRegimeService
from app.services.watchlist_service import APIError

router = APIRouter(tags=["cockpit-regime"])


@router.get("/regime", response_model=RegimeResponse)
def get_regime(db: Session = Depends(get_db)) -> RegimeResponse:
    snapshot = MarketRegimeRepository(db).get_latest()
    if snapshot is None:
        raise APIError("NOT_FOUND", "No market regime data available", 404)

    indices_raw, sectors_raw = MarketRegimeService(db).get_indices_and_sectors_state()

    indices = [RegimeIndexItem.model_validate(item) for item in indices_raw]
    sectors = [RegimeSectorItem.model_validate(item) for item in sectors_raw]

    data = RegimeData(
        date=str(snapshot.date),
        regime=snapshot.regime,
        market_score=snapshot.market_score,
        subscores=RegimeSubscores(
            spy_trend=snapshot.spy_trend_score,
            qqq_trend=snapshot.qqq_trend_score,
            iwm_breadth=snapshot.iwm_breadth_score,
            sector_participation=snapshot.sector_participation_score,
            risk_appetite=snapshot.risk_appetite_score,
            volatility_stress=snapshot.volatility_stress_score,
        ),
        allowed_exposure_pct=snapshot.allowed_exposure_pct,
        single_trade_risk_pct=snapshot.single_trade_risk_pct,
        preferred_setups=json.loads(snapshot.preferred_setups),
        avoid_setups=json.loads(snapshot.avoid_setups),
        indices=indices,
        sectors=sectors,
        computed_at=snapshot.computed_at.isoformat(),
    )

    return RegimeResponse(data=data)
