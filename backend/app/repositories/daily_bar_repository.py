from __future__ import annotations

from datetime import date
from typing import Iterable, TypedDict

from sqlalchemy import delete, func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models import DailyBar

DAILY_BAR_WINDOW = 250


class BarDTO(TypedDict):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class DailyBarRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_latest_date(self, stock_id: int) -> date | None:
        stmt = select(func.max(DailyBar.date)).where(DailyBar.stock_id == stock_id)
        return self.db.execute(stmt).scalar_one_or_none()

    def count_bars(self, stock_id: int) -> int:
        stmt = select(func.count(DailyBar.id)).where(DailyBar.stock_id == stock_id)
        return int(self.db.execute(stmt).scalar_one())

    def bulk_upsert(self, stock_id: int, bars: Iterable[BarDTO]) -> int:
        rows = [
            {
                "stock_id": stock_id,
                "date": b["date"],
                "open": b["open"],
                "high": b["high"],
                "low": b["low"],
                "close": b["close"],
                "volume": b["volume"],
            }
            for b in bars
        ]
        if not rows:
            return 0

        before = self.count_bars(stock_id)
        stmt = sqlite_insert(DailyBar).values(rows)
        stmt = stmt.on_conflict_do_nothing(
            index_elements=["stock_id", "date"],
        )
        self.db.execute(stmt)
        self.db.commit()
        after = self.count_bars(stock_id)
        return after - before

    def prune_to_window(self, stock_id: int, max_rows: int = DAILY_BAR_WINDOW) -> int:
        total = self.count_bars(stock_id)
        if total <= max_rows:
            return 0

        cutoff_stmt = (
            select(DailyBar.date)
            .where(DailyBar.stock_id == stock_id)
            .order_by(DailyBar.date.desc())
            .offset(max_rows - 1)
            .limit(1)
        )
        cutoff_date = self.db.execute(cutoff_stmt).scalar_one()

        del_stmt = delete(DailyBar).where(
            DailyBar.stock_id == stock_id,
            DailyBar.date < cutoff_date,
        )
        result = self.db.execute(del_stmt)
        self.db.commit()
        return int(result.rowcount or 0)
