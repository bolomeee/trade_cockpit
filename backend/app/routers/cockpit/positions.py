"""F206-a: /api/cockpit/positions — Position CRUD (4 endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.cockpit.position import (
    PositionCreate,
    PositionDeleteResponse,
    PositionListResponse,
    PositionSingleResponse,
    PositionUpdate,
    _PositionListData,
    _PositionDeleteData,
)
from app.services.cockpit.position_service import PositionService
from app.services.watchlist_service import APIError

router = APIRouter(prefix="/positions", tags=["cockpit-positions"])


def _get_service(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> PositionService:
    return PositionService(db=db, fmp=fmp)


# ---------------------------------------------------------------------------
# GET /api/cockpit/positions?status=open|closed|all
# ---------------------------------------------------------------------------

@router.get("", response_model=PositionListResponse)
def list_positions(
    status: str = Query("open", pattern="^(open|closed|all)$"),
    svc: PositionService = Depends(_get_service),
) -> PositionListResponse:
    items = svc.list_positions(status)
    return PositionListResponse(data=_PositionListData(items=items))


# ---------------------------------------------------------------------------
# POST /api/cockpit/positions → 201
# ---------------------------------------------------------------------------

@router.post("", response_model=PositionSingleResponse, status_code=201)
def create_position(
    payload: PositionCreate,
    svc: PositionService = Depends(_get_service),
) -> PositionSingleResponse:
    item = svc.create_position(payload)
    return PositionSingleResponse(data=item)


# ---------------------------------------------------------------------------
# PATCH /api/cockpit/positions/{position_id}
# ---------------------------------------------------------------------------

@router.patch("/{position_id}", response_model=PositionSingleResponse)
def update_position(
    position_id: int,
    patch: PositionUpdate,
    svc: PositionService = Depends(_get_service),
) -> PositionSingleResponse:
    item = svc.update_position(position_id, patch)
    if item is None:
        raise APIError("NOT_FOUND", f"position {position_id} not found", 404)
    return PositionSingleResponse(data=item)


# ---------------------------------------------------------------------------
# DELETE /api/cockpit/positions/{position_id}
# ---------------------------------------------------------------------------

@router.delete("/{position_id}", response_model=PositionDeleteResponse)
def delete_position(
    position_id: int,
    svc: PositionService = Depends(_get_service),
) -> PositionDeleteResponse:
    deleted = svc.delete_position(position_id)
    if not deleted:
        raise APIError("NOT_FOUND", f"position {position_id} not found", 404)
    return PositionDeleteResponse(data=_PositionDeleteData(id=position_id))
