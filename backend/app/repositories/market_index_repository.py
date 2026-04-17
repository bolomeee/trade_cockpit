from __future__ import annotations

from datetime import date
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.market_index import MarketIndex

MARKET_INDEX_WINDOW = 5
MARKET_INDEX_SYMBOLS = ("SPX", "NDX", "TNX")


class MarketIndexRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(
        self,
        symbol: str,
        name: str,
        date_: date,
        close: float,
        prev_close: float | None,
        change_pct: float | None,
    ) -> MarketIndex:
        stmt = sqlite_insert(MarketIndex).values(
            symbol=symbol,
            name=name,
            date=date_,
            close=close,
            prev_close=prev_close,
            change_pct=change_pct,
        )
        stmt = stmt.on_conflict_do_update(
            index_elements=["symbol", "date"],
            set_={
                "name": name,
                "close": close,
                "prev_close": prev_close,
                "change_pct": change_pct,
            },
        )
        self.db.execute(stmt)
        self.db.commit()
        return self.db.execute(
            select(MarketIndex).where(
                MarketIndex.symbol == symbol, MarketIndex.date == date_
            )
        ).scalar_one()

    def list_latest_by_symbol(
        self, symbols: Iterable[str] = MARKET_INDEX_SYMBOLS
    ) -> list[MarketIndex]:
        out: list[MarketIndex] = []
        for sym in symbols:
            row = self.db.execute(
                select(MarketIndex)
                .where(MarketIndex.symbol == sym)
                .order_by(MarketIndex.date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                out.append(row)
        return out

    def prune_to_window(self, symbol: str, max_rows: int = MARKET_INDEX_WINDOW) -> int:
        dates = list(
            self.db.execute(
                select(MarketIndex.date)
                .where(MarketIndex.symbol == symbol)
                .order_by(MarketIndex.date.desc())
            ).scalars()
        )
        if len(dates) <= max_rows:
            return 0
        cutoff = dates[max_rows - 1]
        result = self.db.execute(
            delete(MarketIndex).where(
                MarketIndex.symbol == symbol,
                MarketIndex.date < cutoff,
            )
        )
        self.db.commit()
        return int(result.rowcount or 0)
