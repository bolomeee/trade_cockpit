from __future__ import annotations

from datetime import datetime
from typing import Literal

from app.schemas.watchlist import CamelModel

LogLevel = Literal["OK", "INFO", "WARN", "ERROR"]


class LogEntryOut(CamelModel):
    id: int
    level: LogLevel
    source: str
    message: str
    detail: str | None = None
    created_at: datetime
