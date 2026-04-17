from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import SystemLog

SYSTEM_LOG_RETENTION_DAYS = 7
LOG_LEVELS = ("OK", "INFO", "WARN", "ERROR")


class SystemLogRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def create(
        self,
        level: str,
        source: str,
        message: str,
        detail: str | None = None,
    ) -> SystemLog:
        if level not in LOG_LEVELS:
            raise ValueError(f"invalid log level: {level}")
        log = SystemLog(
            level=level,
            source=source,
            message=message[:500],
            detail=detail,
            created_at=datetime.now(timezone.utc),
        )
        self.db.add(log)
        self.db.commit()
        self.db.refresh(log)
        return log

    def purge_older_than(self, days: int = SYSTEM_LOG_RETENTION_DAYS) -> int:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        stmt = delete(SystemLog).where(SystemLog.created_at < cutoff)
        result = self.db.execute(stmt)
        self.db.commit()
        return int(result.rowcount or 0)

    def list_recent(
        self,
        limit: int = 500,
        level: str | None = None,
    ) -> list[SystemLog]:
        stmt = select(SystemLog).order_by(SystemLog.created_at.desc()).limit(limit)
        if level is not None:
            stmt = stmt.where(SystemLog.level == level)
        return list(self.db.execute(stmt).scalars().all())
