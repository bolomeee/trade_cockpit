from __future__ import annotations

from typing import Any

from sqlalchemy import func, select
from sqlalchemy.orm import Session, joinedload

from app.models import JournalEntry, Stock


class JournalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def _base_query(self, ticker: str | None, action: str | None):
        stmt = select(JournalEntry).options(joinedload(JournalEntry.stock))
        if ticker:
            stmt = stmt.join(Stock).where(Stock.ticker == ticker.upper())
        if action:
            stmt = stmt.where(JournalEntry.action == action)
        return stmt

    def count(self, ticker: str | None = None, action: str | None = None) -> int:
        stmt = select(func.count(JournalEntry.id))
        if ticker:
            stmt = stmt.join(Stock, Stock.id == JournalEntry.stock_id).where(
                Stock.ticker == ticker.upper()
            )
        if action:
            stmt = stmt.where(JournalEntry.action == action)
        return int(self.db.execute(stmt).scalar_one())

    def list(
        self,
        ticker: str | None = None,
        action: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[JournalEntry]:
        stmt = (
            self._base_query(ticker, action)
            .order_by(JournalEntry.date.desc(), JournalEntry.id.desc())
            .limit(limit)
            .offset(offset)
        )
        return list(self.db.execute(stmt).scalars().all())

    def get_by_id(self, entry_id: int) -> JournalEntry | None:
        stmt = (
            select(JournalEntry)
            .options(joinedload(JournalEntry.stock))
            .where(JournalEntry.id == entry_id)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def create(self, *, stock_id: int, fields: dict[str, Any]) -> JournalEntry:
        entry = JournalEntry(stock_id=stock_id, **fields)
        self.db.add(entry)
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def update(self, entry: JournalEntry, fields: dict[str, Any]) -> JournalEntry:
        for key, value in fields.items():
            setattr(entry, key, value)
        self.db.flush()
        self.db.commit()
        self.db.refresh(entry)
        return entry

    def delete(self, entry: JournalEntry) -> None:
        self.db.delete(entry)
        self.db.commit()
