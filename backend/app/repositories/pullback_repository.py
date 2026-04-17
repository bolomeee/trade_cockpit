from __future__ import annotations

from datetime import date

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import Pullback


class PullbackRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_by_stock(self, stock_id: int) -> list[Pullback]:
        stmt = (
            select(Pullback)
            .where(Pullback.stock_id == stock_id)
            .order_by(Pullback.date.desc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_by_stock_since(self, stock_id: int, since: date) -> list[Pullback]:
        stmt = (
            select(Pullback)
            .where(Pullback.stock_id == stock_id, Pullback.date >= since)
            .order_by(Pullback.date.asc())
        )
        return list(self.db.execute(stmt).scalars().all())
