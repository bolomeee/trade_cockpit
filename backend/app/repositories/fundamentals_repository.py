"""F218-d6a: FundamentalsRepository — null-not-erase upsert + read APIs for T5 Balance Inflection."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.stock_fundamentals_quarterly import StockFundamentalsQuarterly

_UQ_COLS = ("ticker", "fiscal_quarter")


class FundamentalsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write ──────────────────────────────────────────────────────────────────

    def upsert(self, data: dict) -> StockFundamentalsQuarterly:
        """INSERT OR UPDATE by (ticker, fiscal_quarter) UQ with null-not-erase semantics.

        On conflict, only non-NULL fields in `data` overwrite existing values
        (D097 §4: avoid wiping cached values when FMP transiently returns null).
        Strategy: SELECT existing row → merge non-null incoming fields → INSERT OR REPLACE.
        """
        ticker = data["ticker"]
        fiscal_quarter = data["fiscal_quarter"]

        existing = self.db.execute(
            select(StockFundamentalsQuarterly).where(
                StockFundamentalsQuarterly.ticker == ticker,
                StockFundamentalsQuarterly.fiscal_quarter == fiscal_quarter,
            )
        ).scalar_one_or_none()

        if existing is not None:
            merged = {
                "id": existing.id,
                "ticker": existing.ticker,
                "fiscal_quarter": existing.fiscal_quarter,
                "period_end_date": existing.period_end_date,
                "total_debt": existing.total_debt,
                "cash": existing.cash,
                "net_debt": existing.net_debt,
                "fcf": existing.fcf,
                "fetched_at": existing.fetched_at,
            }
            for k, v in data.items():
                if v is not None:
                    merged[k] = v
        else:
            merged = dict(data)

        stmt = sqlite_insert(StockFundamentalsQuarterly).values(**merged)
        update_cols = {k: merged[k] for k in merged if k not in (*_UQ_COLS, "id")}
        stmt = stmt.on_conflict_do_update(
            index_elements=list(_UQ_COLS),
            set_=update_cols,
        )
        self.db.execute(stmt)
        self.db.commit()
        self.db.expire_all()

        return self.db.execute(
            select(StockFundamentalsQuarterly).where(
                StockFundamentalsQuarterly.ticker == ticker,
                StockFundamentalsQuarterly.fiscal_quarter == fiscal_quarter,
            )
        ).scalar_one()

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_recent_for_ticker(
        self, ticker: str, limit: int = 8,
    ) -> list[StockFundamentalsQuarterly]:
        """Most recent `limit` rows ordered by period_end_date DESC. T5 detector entry."""
        return list(
            self.db.execute(
                select(StockFundamentalsQuarterly)
                .where(StockFundamentalsQuarterly.ticker == ticker)
                .order_by(StockFundamentalsQuarterly.period_end_date.desc())
                .limit(limit)
            ).scalars().all()
        )

    # ── Retention ──────────────────────────────────────────────────────────────

    def delete_for_tickers_not_in(self, active_tickers: list[str]) -> int:
        """Cleanup rows for tickers no longer in pool.

        Not hooked into any caller in d6a — provided for future monthly cleanup task.
        Returns count deleted.
        """
        res = self.db.execute(
            delete(StockFundamentalsQuarterly).where(
                StockFundamentalsQuarterly.ticker.not_in(active_tickers)
            )
        )
        self.db.commit()
        return res.rowcount
