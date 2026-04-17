from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models import DailyBar, Pullback, Signal, Stock
from app.services.signal_engine import (
    SIGNAL_RETENTION_DAYS,
    PullbackPoint,
    SignalPoint,
)


class SignalRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def list_daily_bars(self, stock_id: int) -> list[DailyBar]:
        stmt = (
            select(DailyBar)
            .where(DailyBar.stock_id == stock_id)
            .order_by(DailyBar.date.asc())
        )
        return list(self.db.execute(stmt).scalars().all())

    def replace_signals(self, stock_id: int, points: list[SignalPoint]) -> None:
        self.db.execute(delete(Signal).where(Signal.stock_id == stock_id))
        retained = points[-SIGNAL_RETENTION_DAYS:] if points else []
        for p in retained:
            self.db.add(
                Signal(
                    stock_id=stock_id,
                    date=p.date,
                    signal_type=p.signal_type,
                    ma150_value=p.ma150_value,
                    close_price=p.close_price,
                    distance_pct=p.distance_pct,
                    slope_positive=p.slope_positive,
                    slope_value=p.slope_value,
                )
            )
        self.db.commit()

    def replace_pullbacks(self, stock_id: int, points: list[PullbackPoint]) -> None:
        self.db.execute(delete(Pullback).where(Pullback.stock_id == stock_id))
        for p in points:
            self.db.add(
                Pullback(
                    stock_id=stock_id,
                    date=p.date,
                    close_price=p.close_price,
                    ma150_value=p.ma150_value,
                    distance_pct=p.distance_pct,
                    return_10d=p.return_10d,
                    return_20d=p.return_20d,
                    return_30d=p.return_30d,
                )
            )
        self.db.commit()

    def get_latest_signal(self, stock_id: int) -> Signal | None:
        stmt = (
            select(Signal)
            .where(Signal.stock_id == stock_id)
            .order_by(Signal.date.desc())
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none()

    def get_signal_history(self, stock_id: int, days: int) -> list[Signal]:
        stmt = (
            select(Signal)
            .where(Signal.stock_id == stock_id)
            .order_by(Signal.date.desc())
            .limit(days)
        )
        return list(self.db.execute(stmt).scalars().all())

    def list_latest_per_active_stock(self) -> list[tuple[Stock, Signal | None]]:
        stocks = list(
            self.db.execute(
                select(Stock)
                .where(Stock.is_active.is_(True))
                .order_by(Stock.added_at.desc())
            )
            .scalars()
            .all()
        )
        result: list[tuple[Stock, Signal | None]] = []
        for stock in stocks:
            latest = self.get_latest_signal(stock.id)
            result.append((stock, latest))
        return result

    def count_signals(self, stock_id: int) -> int:
        from sqlalchemy import func

        stmt = select(func.count(Signal.id)).where(Signal.stock_id == stock_id)
        return int(self.db.execute(stmt).scalar_one())
