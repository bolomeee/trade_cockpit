from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.market_regime_snapshot import MarketRegimeSnapshot

REGIME_RETENTION_DAYS = 90


class MarketRegimeRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, data: dict) -> MarketRegimeSnapshot:
        """INSERT OR UPDATE by date (uq_market_regime_date).

        data keys must match MarketRegimeSnapshot column names (snake_case).
        preferred_setups / avoid_setups must be pre-serialised JSON strings.
        """
        stmt = sqlite_insert(MarketRegimeSnapshot).values(**data)
        update_cols = {k: v for k, v in data.items() if k != "date"}
        stmt = stmt.on_conflict_do_update(
            index_elements=["date"],
            set_=update_cols,
        )
        self.db.execute(stmt)
        self.db.commit()
        return self.db.execute(
            select(MarketRegimeSnapshot).where(MarketRegimeSnapshot.date == data["date"])
        ).scalar_one()

    def get_latest(self) -> MarketRegimeSnapshot | None:
        """Return the row with the most recent date, or None if empty."""
        return self.db.execute(
            select(MarketRegimeSnapshot).order_by(MarketRegimeSnapshot.date.desc()).limit(1)
        ).scalar_one_or_none()

    def delete_old(self, cutoff: date) -> int:
        """Delete rows where date < cutoff. Returns deleted row count."""
        result = self.db.execute(
            delete(MarketRegimeSnapshot).where(MarketRegimeSnapshot.date < cutoff)
        )
        self.db.commit()
        return result.rowcount
