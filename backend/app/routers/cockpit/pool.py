"""F205-c: GET /api/cockpit/pool — pool builder funnel endpoint.

API-CONTRACT.md §GET /api/cockpit/pool (lines 1322–1387).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.cockpit.pool import PoolData, PoolFunnel, PoolItem, PoolResponse
from app.services.cockpit.pool_service import PoolParams, PoolService
from app.services.watchlist_service import APIError

router = APIRouter(tags=["cockpit-pool"])


@router.get("/pool", response_model=PoolResponse)
def get_pool(
    marketCapMin: int = Query(10_000_000_000, description="Market cap lower bound (USD)"),
    priceMin: float = Query(10.0, description="Stock price lower bound"),
    advMin: int = Query(20_000_000, description="Dollar volume lower bound (USD, single-day proxy)"),
    trendScoreMin: int = Query(3, ge=0, le=5, description="Accepted but ignored this sprint (D080)"),
    rsPercentileMin: int = Query(70, description="RS percentile lower bound (0–100)"),
    revenueGrowthYoyMin: float = Query(10.0, description="Revenue growth YoY lower bound (%)"),
    sectors: str | None = Query(None, description="Comma-separated sector ETF symbols (e.g. XLK,XLY)"),
    setupTypes: str | None = Query(None, description="Comma-separated setup types"),
    limit: int = Query(50, description="Max items returned (1–200)"),
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> PoolResponse:
    """Run the 5-layer pool funnel and return ranked candidates.

    API-CONTRACT.md §GET /api/cockpit/pool — validation: limit 1–200, rsPercentileMin 0–100.
    """
    if not (1 <= limit <= 200):
        raise APIError("VALIDATION_ERROR", f"limit must be 1–200, got {limit}", 422)
    if not (0 <= rsPercentileMin <= 100):
        raise APIError("VALIDATION_ERROR", f"rsPercentileMin must be 0–100, got {rsPercentileMin}", 422)

    params = PoolParams(
        market_cap_min=marketCapMin,
        price_min=priceMin,
        adv_min=advMin,
        trend_score_min=trendScoreMin,
        rs_percentile_min=float(rsPercentileMin),
        revenue_growth_yoy_min=revenueGrowthYoyMin,
        sectors=[s.strip() for s in sectors.split(",") if s.strip()] if sectors else [],
        setup_types=[s.strip() for s in setupTypes.split(",") if s.strip()] if setupTypes else [],
        limit=limit,
    )

    result = PoolService(db=db, fmp=fmp).get_pool(params)

    funnel = PoolFunnel(**result["funnel"])
    items = [PoolItem.model_validate(item) for item in result["items"]]
    return PoolResponse(data=PoolData(funnel=funnel, items=items))
