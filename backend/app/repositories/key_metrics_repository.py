"""F218-d3a: KeyMetricsRepository — null-not-erase upsert + read APIs for T2 margin expansion."""
from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.stock_key_metrics_quarterly import StockKeyMetricsQuarterly

_UQ_COLS = ("ticker", "fiscal_quarter")


class KeyMetricsRepository:
    def __init__(self, db: Session) -> None:
        self.db = db

    # ── Write ──────────────────────────────────────────────────────────────────

    def upsert(self, data: dict) -> StockKeyMetricsQuarterly:
        """INSERT OR UPDATE by (ticker, fiscal_quarter) UQ with null-not-erase semantics.

        On conflict, only non-NULL fields in `data` overwrite existing values
        (D097 §4: avoid wiping cached values when FMP transiently returns null).
        Strategy: SELECT existing row → merge non-null incoming fields → INSERT OR REPLACE.
        """
        ticker = data["ticker"]
        fiscal_quarter = data["fiscal_quarter"]

        existing = self.db.execute(
            select(StockKeyMetricsQuarterly).where(
                StockKeyMetricsQuarterly.ticker == ticker,
                StockKeyMetricsQuarterly.fiscal_quarter == fiscal_quarter,
            )
        ).scalar_one_or_none()

        if existing is not None:
            merged = {
                "id": existing.id,
                "ticker": existing.ticker,
                "fiscal_quarter": existing.fiscal_quarter,
                "period_end_date": existing.period_end_date,
                "gross_margin": existing.gross_margin,
                "op_margin": existing.op_margin,
                "net_margin": existing.net_margin,
                "fcf_margin": existing.fcf_margin,
                "roic": existing.roic,
                "fetched_at": existing.fetched_at,
            }
            for k, v in data.items():
                if v is not None:
                    merged[k] = v
        else:
            merged = dict(data)

        stmt = sqlite_insert(StockKeyMetricsQuarterly).values(**merged)
        update_cols = {k: merged[k] for k in merged if k not in (*_UQ_COLS, "id")}
        stmt = stmt.on_conflict_do_update(
            index_elements=list(_UQ_COLS),
            set_=update_cols,
        )
        self.db.execute(stmt)
        self.db.commit()
        self.db.expire_all()

        return self.db.execute(
            select(StockKeyMetricsQuarterly).where(
                StockKeyMetricsQuarterly.ticker == ticker,
                StockKeyMetricsQuarterly.fiscal_quarter == fiscal_quarter,
            )
        ).scalar_one()

    # ── Read ───────────────────────────────────────────────────────────────────

    def get_recent_for_ticker(
        self, ticker: str, limit: int = 8,
    ) -> list[StockKeyMetricsQuarterly]:
        """Most recent `limit` rows ordered by period_end_date DESC. T2 detector entry."""
        return list(
            self.db.execute(
                select(StockKeyMetricsQuarterly)
                .where(StockKeyMetricsQuarterly.ticker == ticker)
                .order_by(StockKeyMetricsQuarterly.period_end_date.desc())
                .limit(limit)
            ).scalars().all()
        )

    # ── Retention ──────────────────────────────────────────────────────────────

    def delete_for_tickers_not_in(self, active_tickers: list[str]) -> int:
        """Cleanup rows for tickers no longer in pool (called by monthly universe refresh).

        Not hooked into any caller in d3a — provided for future monthly cleanup task.
        Returns count deleted.
        """
        res = self.db.execute(
            delete(StockKeyMetricsQuarterly).where(
                StockKeyMetricsQuarterly.ticker.not_in(active_tickers)
            )
        )
        self.db.commit()
        return res.rowcount
