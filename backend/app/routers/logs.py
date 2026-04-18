from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_system_log_repository
from app.repositories.system_log_repository import SystemLogRepository
from app.schemas.log import LogEntryOut, LogLevel
from app.schemas.watchlist import ResponseEnvelope

router = APIRouter(prefix="/api/logs", tags=["logs"])

LIMIT_DEFAULT = 50
LIMIT_MAX = 500


@router.get("", response_model=ResponseEnvelope[list[LogEntryOut]])
def list_logs(
    level: LogLevel | None = Query(default=None),
    limit: int = Query(default=LIMIT_DEFAULT, ge=1, le=LIMIT_MAX),
    repo: SystemLogRepository = Depends(get_system_log_repository),
) -> ResponseEnvelope[list[LogEntryOut]]:
    rows = repo.list_recent(limit=limit, level=level)
    return ResponseEnvelope(data=[LogEntryOut.model_validate(r) for r in rows])
