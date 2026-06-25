from __future__ import annotations

from datetime import datetime

from app.schemas.watchlist import CamelModel


class JobFreshness(CamelModel):
    last_at: datetime | None = None
    age_days: float | None = None
    stale: bool


class RefreshHealthOut(CamelModel):
    universe: JobFreshness
    breakout: JobFreshness
    pool_cache_rows: int
    recent_errors: int
