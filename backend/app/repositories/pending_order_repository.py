from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import Session

from app.models.pending_order import PendingOrder


class PendingOrderRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def list_by_status(self, status: str) -> list[PendingOrder]:
        """status='all' returns all rows; any other value filters by that status."""
        q = self._db.query(PendingOrder)
        if status != "all":
            q = q.filter(PendingOrder.status == status)
        return q.order_by(PendingOrder.created_at.desc()).all()

    def get_by_id(self, order_id: int) -> PendingOrder | None:
        return self._db.query(PendingOrder).filter(PendingOrder.id == order_id).first()

    def create(self, payload: dict) -> PendingOrder:
        now = datetime.now(timezone.utc)
        row = PendingOrder(
            **payload,
            status="ACTIVE",
            created_at=now,
            updated_at=now,
        )
        self._db.add(row)
        self._db.commit()
        self._db.refresh(row)
        return row

    def update(self, order_id: int, patch: dict) -> PendingOrder | None:
        row = self.get_by_id(order_id)
        if row is None:
            return None
        for field, value in patch.items():
            setattr(row, field, value)
        row.updated_at = datetime.now(timezone.utc)
        self._db.commit()
        self._db.refresh(row)
        return row

    def delete(self, order_id: int) -> bool:
        row = self.get_by_id(order_id)
        if row is None:
            return False
        self._db.delete(row)
        self._db.commit()
        return True
