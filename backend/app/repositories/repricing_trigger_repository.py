"""F218-d1: RepricingTriggerRepository — upsert / soft_expire / query / retention."""
from __future__ import annotations

from datetime import date

from sqlalchemy import delete, func, select, update
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.repricing_trigger import RepricingTrigger

_UQ_COLS = ("ticker", "trigger_type", "detected_date")


class RepricingTriggerRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write ──────────────────────────────────────────────────────────────────

    def upsert(self, data: dict) -> RepricingTrigger:
        """INSERT OR UPDATE by (ticker, trigger_type, detected_date) UQ.

        Overwrites confidence / evidence_json / active / computed_at on conflict.
        """
        stmt = sqlite_insert(RepricingTrigger).values(**data)
        update_cols = {k: v for k, v in data.items() if k not in (*_UQ_COLS, "id")}
        stmt = stmt.on_conflict_do_update(
            index_elements=list(_UQ_COLS),
            set_=update_cols,
        )
        self.db.execute(stmt)
        self.db.commit()
        # expire_all forces a fresh DB read — ON CONFLICT UPDATE bypasses the ORM
        # identity map, so the cached instance would otherwise return stale values.
        self.db.expire_all()
        return self.db.execute(
            select(RepricingTrigger).where(
                RepricingTrigger.ticker == data["ticker"],
                RepricingTrigger.trigger_type == data["trigger_type"],
                RepricingTrigger.detected_date == data["detected_date"],
            )
        ).scalar_one()

    def soft_expire(self, ticker: str, trigger_type: str, current_date: date) -> int:
        """Mark active=true rows with detected_date < current_date as inactive.

        Returns count updated. Called when detector finds no hit on current_date.
        """
        res = self.db.execute(
            update(RepricingTrigger)
            .where(
                RepricingTrigger.ticker == ticker,
                RepricingTrigger.trigger_type == trigger_type,
                RepricingTrigger.detected_date < current_date,
                RepricingTrigger.active.is_(True),
            )
            .values(active=False)
        )
        self.db.commit()
        return res.rowcount

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_active_for_ticker(self, ticker: str) -> list[RepricingTrigger]:
        """All active=true triggers for a ticker, ordered by detected_date DESC."""
        return list(
            self.db.execute(
                select(RepricingTrigger)
                .where(
                    RepricingTrigger.ticker == ticker,
                    RepricingTrigger.active.is_(True),
                )
                .order_by(RepricingTrigger.detected_date.desc())
            ).scalars().all()
        )

    def get_all_active(
        self,
        trigger_type: str | None = None,
        limit: int = 100,
    ) -> tuple[list[RepricingTrigger], int]:
        """All active=true triggers market-wide, ordered by detected_date DESC then confidence DESC.

        Returns (rows, total_count) — total_count ignores limit.
        """
        filters = [RepricingTrigger.active.is_(True)]
        if trigger_type is not None:
            filters.append(RepricingTrigger.trigger_type == trigger_type)

        total: int = self.db.execute(
            select(func.count(RepricingTrigger.id)).where(*filters)
        ).scalar_one()

        rows = list(
            self.db.execute(
                select(RepricingTrigger)
                .where(*filters)
                .order_by(
                    RepricingTrigger.detected_date.desc(),
                    RepricingTrigger.confidence.desc(),
                )
                .limit(limit)
            ).scalars().all()
        )
        return rows, total

    # ── Retention ──────────────────────────────────────────────────────────────

    def delete_expired_inactive(self, cutoff: date) -> int:
        """Hard-delete active=false rows with detected_date < cutoff.

        active=true rows are never touched by this method.
        Returns count deleted.
        """
        res = self.db.execute(
            delete(RepricingTrigger).where(
                RepricingTrigger.active.is_(False),
                RepricingTrigger.detected_date < cutoff,
            )
        )
        self.db.commit()
        return res.rowcount
