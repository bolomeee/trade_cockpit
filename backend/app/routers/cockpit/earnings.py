from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.cockpit.earnings import EarningsData, EarningsResponse
from app.services.cockpit.earnings_service import EarningsService

router = APIRouter(tags=["cockpit-earnings"])


def get_earnings_service(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> EarningsService:
    return EarningsService(db, fmp)


@router.get("/earnings", response_model=EarningsResponse)
def get_earnings(
    ticker: str = Query(..., min_length=1),
    service: EarningsService = Depends(get_earnings_service),
) -> EarningsResponse:
    result = service.get_next_earnings(ticker)
    if result["nextEarningsDate"] is None:
        result["note"] = "No upcoming earnings in next 30 days"
    data = EarningsData(
        ticker=result["ticker"],
        next_earnings_date=result["nextEarningsDate"],
        days_until=result["daysUntil"],
        time_of_day=result["timeOfDay"],
        eps_estimate=result["epsEstimate"],
        revenue_estimate=result["revenueEstimate"],
        note=result.get("note"),
    )
    return EarningsResponse(data=data)
