from __future__ import annotations

from datetime import date

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.setup_snapshot import SetupSnapshot

_ACTION_PRIORITY: dict[str | None, int] = {
    "enter": 0,
    "watch": 1,
    "wait": 2,
    None: 3,
    "reduce": 4,
    "exit": 5,
}


class SetupSnapshotRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_batch(self, rows: list[dict]) -> int:
        if not rows:
            return 0
        stmt = sqlite_insert(SetupSnapshot).values(rows)
        stmt = stmt.on_conflict_do_update(
            index_elements=["ticker", "scan_date"],
            set_={
                col: stmt.excluded[col]
                for col in rows[0]
                if col not in ("ticker", "scan_date")
            },
        )
        self.db.execute(stmt)
        self.db.commit()
        return len(rows)

    def get_latest_all_active(self, active_tickers: list[str]) -> list[SetupSnapshot]:
        if not active_tickers:
            return []
        rows: list[SetupSnapshot] = []
        for ticker in active_tickers:
            row = self.db.execute(
                select(SetupSnapshot)
                .where(SetupSnapshot.ticker == ticker)
                .order_by(SetupSnapshot.scan_date.desc())
                .limit(1)
            ).scalar_one_or_none()
            if row is not None:
                rows.append(row)
        rows.sort(key=lambda r: _ACTION_PRIORITY.get(r.suggested_action, 3))
        return rows

    def get_latest_for_tickers(self, tickers: list[str]) -> list[SetupSnapshot]:
        return self.get_latest_all_active(tickers)

    def delete_before(self, cutoff: date) -> int:
        stmt = delete(SetupSnapshot).where(SetupSnapshot.scan_date < cutoff)
        result = self.db.execute(stmt)
        self.db.commit()
        return int(result.rowcount or 0)
