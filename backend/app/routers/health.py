"""D108 / F221: GET /api/refresh-health — scheduled-refresh health for TopNav badge.

API-CONTRACT.md §GET /api/refresh-health. Read-only; never triggers a refresh.
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.health import RefreshHealthOut
from app.schemas.watchlist import ResponseEnvelope
from app.services.refresh_health_service import RefreshHealthService

router = APIRouter(prefix="/api/refresh-health", tags=["health"])


@router.get("", response_model=ResponseEnvelope[RefreshHealthOut])
def get_refresh_health(
    db: Session = Depends(get_db),
) -> ResponseEnvelope[RefreshHealthOut]:
    data = RefreshHealthService(db).get_health()
    return ResponseEnvelope(data=RefreshHealthOut.model_validate(data))
