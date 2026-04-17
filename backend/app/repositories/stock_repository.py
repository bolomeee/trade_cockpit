from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock


class StockRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def get_by_ticker(self, ticker: str) -> Stock | None:
        stmt = select(Stock).where(Stock.ticker == ticker.upper())
        return self.db.execute(stmt).scalar_one_or_none()

    def list_active(self) -> list[Stock]:
        stmt = select(Stock).where(Stock.is_active.is_(True)).order_by(Stock.added_at.desc())
        return list(self.db.execute(stmt).scalars().all())

    def create(self, ticker: str, name: str, exchange: str | None) -> Stock:
        stock = Stock(
            ticker=ticker.upper(),
            name=name,
            exchange=exchange,
            is_active=True,
            added_at=datetime.now(timezone.utc),
        )
        self.db.add(stock)
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def reactivate(self, stock: Stock, name: str, exchange: str | None) -> Stock:
        stock.is_active = True
        stock.added_at = datetime.now(timezone.utc)
        stock.name = name
        stock.exchange = exchange
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def soft_delete(self, stock: Stock) -> Stock:
        stock.is_active = False
        self.db.commit()
        self.db.refresh(stock)
        return stock

    def count_bars(self, stock_id: int) -> int:
        stmt = select(func.count(DailyBar.id)).where(DailyBar.stock_id == stock_id)
        return int(self.db.execute(stmt).scalar_one())
