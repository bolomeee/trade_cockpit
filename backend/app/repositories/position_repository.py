from __future__ import annotations

from datetime import datetime, timezone
from typing import Literal

from sqlalchemy.orm import Session

from app.models.position import Position


class PositionRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_status(self, status: Literal["open", "closed", "all"]) -> list[Position]:
        q = self._db.query(Position)
        if status == "open":
            q = q.filter(Position.status == "OPEN")
        elif status == "closed":
            q = q.filter(Position.status == "CLOSED")
        return q.order_by(Position.created_at.desc()).all()

    def get_by_id(self, position_id: int) -> Position | None:
        return self._db.query(Position).filter(Position.id == position_id).first()

    def create(self, payload: dict) -> Position:
        now = datetime.now(timezone.utc)
        row = Position(
            **payload,
            status="OPEN",
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def update(self, position_id: int, patch: dict) -> Position | None:
        row = self.get_by_id(position_id)
        if row is None:
            return None
        for field, value in patch.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete(self, position_id: int) -> bool:
        row = self.get_by_id(position_id)
        if row is None:
            return False
        self._db.delete(row)
        self._db.commit()
        return True
