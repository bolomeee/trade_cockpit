from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.schemas.cockpit.setup import (
    SetupItemResponse,
    SetupMonitorData,
    SetupMonitorResponse,
    SetupSummary,
)
from app.services.cockpit.setup_service import SetupService
from app.services.watchlist_service import APIError

router = APIRouter(tags=["cockpit-setup"])

_VALID_FILTER_VALUES = {"ready", "near", "extended", "broken", "none"}


@router.get("/setup-monitor", response_model=SetupMonitorResponse)
def get_setup_monitor(
    filter: str | None = Query(None, description="Comma-separated: ready,near,extended,broken,none"),
    db: Session = Depends(get_db),
) -> SetupMonitorResponse:
    if filter is not None:
        parts = [p.strip() for p in filter.split(",") if p.strip()]
        invalid = [p for p in parts if p not in _VALID_FILTER_VALUES]
        if invalid:
            raise APIError(
                "VALIDATION_ERROR",
                f"Invalid filter value(s): {invalid}. Allowed: {sorted(_VALID_FILTER_VALUES)}",
                422,
            )

    result = SetupService(db).get_setup_monitor_data(filter_str=filter)

    summary = SetupSummary(**result["summary"])
    items = [SetupItemResponse.model_validate(item) for item in result["items"]]
    data = SetupMonitorData(summary=summary, items=items)
    return SetupMonitorResponse(data=data)
