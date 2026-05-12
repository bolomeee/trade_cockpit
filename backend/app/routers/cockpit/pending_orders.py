"""F206-b1: /api/cockpit/pending-orders — PendingOrder CRUD (4 endpoints)."""
from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.cockpit.pending_order import (
    PendingOrderCreate,
    PendingOrderDeleteResponse,
    PendingOrderListResponse,
    PendingOrderSingleResponse,
    PendingOrderUpdate,
    _PendingOrderDeleteData,
)
from app.services.cockpit.pending_order_service import PendingOrderService
from app.services.watchlist_service import APIError

router = APIRouter(prefix="/pending-orders", tags=["cockpit-pending-orders"])


def _get_service(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> PendingOrderService:
    return PendingOrderService(db=db, fmp=fmp)


# ---------------------------------------------------------------------------
# GET /api/cockpit/pending-orders?status=active|all|ACTIVE|TRIGGERED|...
# ---------------------------------------------------------------------------

@router.get("", response_model=PendingOrderListResponse)
def list_pending_orders(
    status: str = Query("active"),
    svc: PendingOrderService = Depends(_get_service),
) -> PendingOrderListResponse:
    items = svc.list_pending_orders(status)
    return PendingOrderListResponse(data=items)


# ---------------------------------------------------------------------------
# POST /api/cockpit/pending-orders → 201
# ---------------------------------------------------------------------------

@router.post("", response_model=PendingOrderSingleResponse, status_code=201)
def create_pending_order(
    payload: PendingOrderCreate,
    svc: PendingOrderService = Depends(_get_service),
) -> PendingOrderSingleResponse:
    item = svc.create_pending_order(payload)
    return PendingOrderSingleResponse(data=item)


# ---------------------------------------------------------------------------
# PATCH /api/cockpit/pending-orders/{order_id}
# ---------------------------------------------------------------------------

@router.patch("/{order_id}", response_model=PendingOrderSingleResponse)
def update_pending_order(
    order_id: int,
    patch: PendingOrderUpdate,
    svc: PendingOrderService = Depends(_get_service),
) -> PendingOrderSingleResponse:
    item = svc.update_pending_order(order_id, patch)
    if item is None:
        raise APIError("NOT_FOUND", f"pending order {order_id} not found", 404)
    return PendingOrderSingleResponse(data=item)


# ---------------------------------------------------------------------------
# DELETE /api/cockpit/pending-orders/{order_id}
# ---------------------------------------------------------------------------

@router.delete("/{order_id}", response_model=PendingOrderDeleteResponse)
def delete_pending_order(
    order_id: int,
    svc: PendingOrderService = Depends(_get_service),
) -> PendingOrderDeleteResponse:
    deleted = svc.delete_pending_order(order_id)
    if not deleted:
        raise APIError("NOT_FOUND", f"pending order {order_id} not found", 404)
    return PendingOrderDeleteResponse(data=_PendingOrderDeleteData(id=order_id))
