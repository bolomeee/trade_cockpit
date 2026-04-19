from __future__ import annotations

from typing import Callable

from fastapi import APIRouter, Depends, Response, status
from sqlalchemy.orm import Session

from app.dependencies import get_fmp_client, get_session_factory
from app.external.fmp_client import FmpClient
from app.schemas.data import (
    RefreshProgress,
    RefreshStartedPayload,
    RefreshStatusPayload,
)
from app.schemas.watchlist import ResponseEnvelope
from app.services import refresh_job

router = APIRouter(prefix="/api/data", tags=["data"])


def _fmp_factory_dep(
    fmp: FmpClient = Depends(get_fmp_client),
):
    return lambda _client=fmp: _client


@router.post(
    "/refresh",
    response_model=ResponseEnvelope[RefreshStartedPayload],
    status_code=status.HTTP_202_ACCEPTED,
)
def trigger_refresh(
    response: Response,
    session_factory: Callable[[], Session] = Depends(get_session_factory),
    fmp_factory=Depends(_fmp_factory_dep),
) -> ResponseEnvelope[RefreshStartedPayload]:
    result = refresh_job.manager.start_refresh(
        session_factory=session_factory,
        fmp_factory=fmp_factory,
    )
    # Per API-CONTRACT: 202 on start and on "already running" — client polls /status.
    response.status_code = status.HTTP_202_ACCEPTED
    return ResponseEnvelope(
        data=RefreshStartedPayload.model_validate(
            {
                "jobId": result.job_id,
                "status": result.status,
                "totalStocks": result.total_stocks,
            }
        )
    )


@router.get(
    "/status",
    response_model=ResponseEnvelope[RefreshStatusPayload],
)
def get_status() -> ResponseEnvelope[RefreshStatusPayload]:
    state = refresh_job.manager.get_status()
    payload = RefreshStatusPayload.model_validate(
        {
            "jobId": state.job_id,
            "status": state.status,
            "progress": RefreshProgress.model_validate(
                {
                    "total": state.total,
                    "completed": state.completed,
                    "failed": state.failed,
                }
            ),
            "startedAt": state.started_at,
            "lastRefreshedAt": state.last_refreshed_at,
        }
    )
    return ResponseEnvelope(data=payload)
