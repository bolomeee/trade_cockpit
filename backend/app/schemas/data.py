from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.watchlist import CamelModel

RefreshStatus = Literal["idle", "in_progress", "completed", "failed"]
RefreshStartStatus = Literal["started", "in_progress"]


class RefreshStartedPayload(CamelModel):
    job_id: str
    status: RefreshStartStatus
    total_stocks: int


class RefreshProgress(CamelModel):
    total: int
    completed: int
    failed: int


class RefreshStatusPayload(CamelModel):
    job_id: str | None = None
    status: RefreshStatus
    progress: RefreshProgress
    started_at: datetime | None = None
    last_refreshed_at: datetime | None = None
