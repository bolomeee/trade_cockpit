"""F216-b: WeeklyStageRepository — upsert / query weekly_stage_snapshots."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.weekly_stage_snapshot import WeeklyStageSnapshot


class WeeklyStageRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert(self, data: dict) -> WeeklyStageSnapshot:
        """INSERT OR UPDATE by (ticker, scan_date) unique constraint."""
        stmt = sqlite_insert(WeeklyStageSnapshot).values(**data)
        update_cols = {k: v for k, v in data.items() if k not in ("ticker", "scan_date")}
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "scan_date"],
            set_=update_cols,
        )
        self.db.execute(stmt)
        self.db.commit()
        return self.db.execute(
            select(WeeklyStageSnapshot)
            .where(
                WeeklyStageSnapshot.ticker == data["ticker"],
                WeeklyStageSnapshot.scan_date == data["scan_date"],
            )
        ).scalar_one()

    def get_latest_by_ticker(self, ticker: str) -> WeeklyStageSnapshot | None:
        """Return the most recent snapshot for a single ticker, or None."""
        return self.db.execute(
            select(WeeklyStageSnapshot)
            .where(WeeklyStageSnapshot.ticker == ticker)
            .order_by(WeeklyStageSnapshot.scan_date.desc())
            .limit(1)
        ).scalar_one_or_none()

    def get_latest_for_tickers(self, tickers: list[str]) -> dict[str, WeeklyStageSnapshot]:
        """Return {ticker: latest_snapshot} for each ticker that has a row.

        Missing tickers are silently omitted (caller must handle absence).
        Used by F216-d setup_service integration.
        """
        if not tickers:
            return {}
        subq = (
            select(
                WeeklyStageSnapshot.ticker,
                WeeklyStageSnapshot.scan_date,
            )
            .where(WeeklyStageSnapshot.ticker.in_(tickers))
            .group_by(WeeklyStageSnapshot.ticker)
            # SQLite: MAX(scan_date) picks the latest per group
        ).subquery()
        rows = self.db.execute(
            select(WeeklyStageSnapshot)
            .where(WeeklyStageSnapshot.ticker.in_(tickers))
            .order_by(WeeklyStageSnapshot.ticker, WeeklyStageSnapshot.scan_date.desc())
        ).scalars().all()
        # Deduplicate: take first (= latest) per ticker
        seen: set[str] = set()
        result: dict[str, WeeklyStageSnapshot] = {}
        for row in rows:
            if row.ticker not in seen:
                seen.add(row.ticker)
                result[row.ticker] = row
        return result

    def delete_old(self, cutoff: date) -> int:
        """Delete rows where scan_date < cutoff. Returns deleted row count."""
        res = self.db.execute(
            delete(WeeklyStageSnapshot).where(WeeklyStageSnapshot.scan_date < cutoff)
        )
        self.db.commit()
        return res.rowcount
