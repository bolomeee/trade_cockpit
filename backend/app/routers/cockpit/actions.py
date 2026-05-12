"""F207-a: GET /api/cockpit/actions/today — daily action list."""
from __future__ import annotations

from datetime import date
from typing import Any

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.cockpit.position import _CamelModel
from app.services.cockpit.action_service import ActionService
from app.services.watchlist_service import APIError

router = APIRouter(prefix="/actions", tags=["cockpit-actions"])


# ── Pydantic schemas ──────────────────────────────────────────────────────────

class ActionItem(_CamelModel):
    ticker: str
    action_type: str
    rationale: str
    refs: dict[str, Any]


class ActionsTodayPayload(_CamelModel):
    as_of_date: date
    must_act: list[ActionItem]
    monitor: list[ActionItem]
    no_action: list[ActionItem]


class ActionsTodayResponse(BaseModel):
    data: ActionsTodayPayload
    message: str


# ── Dependency ────────────────────────────────────────────────────────────────

def _get_service(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> ActionService:
    return ActionService(db=db, fmp=fmp)


# ── Endpoint ──────────────────────────────────────────────────────────────────

@router.get("/today", response_model=ActionsTodayResponse)
def get_today_actions(svc: ActionService = Depends(_get_service)) -> ActionsTodayResponse:
    try:
        data = svc.build_today_actions()
        return ActionsTodayResponse(
            data=ActionsTodayPayload(**data),
            message="success",
        )
    except SQLAlchemyError as exc:
        raise APIError("INTERNAL_ERROR", str(exc), 500) from exc
