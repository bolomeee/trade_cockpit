"""F203-b2: GET /api/cockpit/decision/{ticker}"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.cockpit.decision import DecisionResponse
from app.services.cockpit.decision_service import compute_decision
from app.services.watchlist_service import APIError

router = APIRouter(prefix="/decision", tags=["cockpit-decision"])


@router.get("/{ticker}", response_model=DecisionResponse)
def get_decision(
    ticker: str,
    entry_override: float | None = Query(default=None, alias="entryOverride", gt=0),
    stop_override: float | None = Query(default=None, alias="stopOverride", gt=0),
    risk_pct_override: float | None = Query(default=None, alias="riskPctOverride", ge=0, le=5),
    db: Session = Depends(get_db),
) -> DecisionResponse:
    try:
        data = compute_decision(db, ticker, entry_override, stop_override, risk_pct_override)
    except LookupError as exc:
        raise APIError("NOT_FOUND", str(exc), 404) from exc
    except ValueError as exc:
        raise APIError("VALIDATION_ERROR", str(exc), 422) from exc
    return DecisionResponse(data=data)
