"""EarningsEvent repository (F204-a).

Responsibilities:
- upsert_batch: 增量 upsert earnings_events；estimate 字段完整覆盖，
  actual 字段仅在新值非 None 时覆盖（保留 FMP 尚未回填前的旧值）
- get_next_earnings: 查询 ticker 在指定日期之后最近一次 earnings
- delete_before: 清理 earnings_date < cutoff 的历史记录（60 天窗口）
"""
from __future__ import annotations

import logging
from datetime import date, datetime, timezone

from sqlalchemy.orm import Session

from app.models.earnings_event import EarningsEvent

logger = logging.getLogger(__name__)


class EarningsEventRepository:
    def __init__(self, db: Session) -> None:
        self._db = db

    def upsert_batch(self, records: list[dict]) -> int:
        """Upsert a batch of earnings records.

        Each dict must contain: ticker, earnings_date, eps_estimate,
        revenue_estimate, time_of_day, fetched_at.
        Optional: eps_actual, revenue_actual.

        estimate フィールド（eps_estimate, revenue_estimate, time_of_day,
        fetched_at）は常に上書き。actual フィールドは新値が None でない
        場合のみ上書き（FMP 回填前の既存値を保護）。

        Returns number of records processed.
        """
        if not records:
            return 0

        # Deduplicate within the batch by (ticker, earnings_date); last record wins
        deduped: dict[tuple, dict] = {}
        for r in records:
            deduped[(r["ticker"], r["earnings_date"])] = r
        records = list(deduped.values())

        for record in records:
            ticker = record["ticker"]
            earnings_date = record["earnings_date"]

            existing = (
                self._db.query(EarningsEvent)
                .filter_by(ticker=ticker, earnings_date=earnings_date)
                .first()
            )

            if existing is None:
                row = EarningsEvent(
                    ticker=ticker,
                    earnings_date=earnings_date,
                    eps_estimate=record.get("eps_estimate"),
                    eps_actual=record.get("eps_actual"),
                    revenue_estimate=record.get("revenue_estimate"),
                    revenue_actual=record.get("revenue_actual"),
                    time_of_day=record.get("time_of_day"),
                    fetched_at=record.get("fetched_at", datetime.now(timezone.utc)),
                )
                self._db.add(row)
            else:
                # Always update estimate fields
                existing.eps_estimate = record.get("eps_estimate")
                existing.revenue_estimate = record.get("revenue_estimate")
                existing.time_of_day = record.get("time_of_day")
                existing.fetched_at = record.get("fetched_at", datetime.now(timezone.utc))
                # Only update actual fields if new value is not None
                if record.get("eps_actual") is not None:
                    existing.eps_actual = record["eps_actual"]
                if record.get("revenue_actual") is not None:
                    existing.revenue_actual = record["revenue_actual"]

        self._db.commit()
        return len(records)

    def get_next_earnings(self, ticker: str, from_date: date) -> EarningsEvent | None:
        """Return the nearest upcoming earnings for ticker on or after from_date."""
        return (
            self._db.query(EarningsEvent)
            .filter(
                EarningsEvent.ticker == ticker,
                EarningsEvent.earnings_date >= from_date,
            )
            .order_by(EarningsEvent.earnings_date.asc())
            .first()
        )

    def delete_before(self, cutoff: date) -> int:
        """Delete records with earnings_date before cutoff. Returns deleted count."""
        deleted = (
            self._db.query(EarningsEvent)
            .filter(EarningsEvent.earnings_date < cutoff)
            .delete(synchronize_session=False)
        )
        self._db.commit()
        logger.info("earnings_events cleanup: deleted %d rows before %s", deleted, cutoff)
        return deleted
