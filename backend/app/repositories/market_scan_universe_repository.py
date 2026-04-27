from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Iterable, Optional

from sqlalchemy import func, select
from sqlalchemy.dialects.sqlite import insert as sqlite_insert
from sqlalchemy.orm import Session

from app.models.market_scan_universe import MarketScanUniverse


@dataclass(frozen=True)
class UniverseUpsertRow:
    """单次 upsert 的输入行（来自 screener 聚合结果）。"""

    ticker: str
    company_name: str
    exchange: str
    market_cap: int
    sector: Optional[str] = None
    industry: Optional[str] = None
    last_price: Optional[float] = None
    last_volume: Optional[int] = None


class MarketScanUniverseRepository:
    """D038：market_scan_universe 的持久化接口。

    业务规则：
    - upsert 已存在 ticker 时更新 company_name / exchange / market_cap / last_seen_at；
      added_at 保留首次值。
    - 不删除"掉出 universe"的历史行；有效性由 list_active(since) 按 last_seen_at 过滤。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def upsert_many(
        self, rows: Iterable[UniverseUpsertRow], now: datetime
    ) -> int:
        payload = [
            {
                "ticker": r.ticker,
                "company_name": r.company_name,
                "exchange": r.exchange,
                "market_cap": int(r.market_cap),
                "sector": r.sector,
                "industry": r.industry,
                "last_price": r.last_price,
                "last_volume": r.last_volume,
                "last_seen_at": now,
                "added_at": now,
            }
            for r in rows
        ]
        if not payload:
            return 0

        count = 0
        for row in payload:
            stmt = sqlite_insert(MarketScanUniverse).values(**row)
            stmt = stmt.on_conflict_do_update(
                index_elements=["ticker"],
                set_={
                    "company_name": row["company_name"],
                    "exchange": row["exchange"],
                    "market_cap": row["market_cap"],
                    "sector": row["sector"],
                    "industry": row["industry"],
                    "last_price": row["last_price"],
                    "last_volume": row["last_volume"],
                    "last_seen_at": row["last_seen_at"],
                },
            )
            self.db.execute(stmt)
            count += 1
        self.db.commit()
        return count

    def list_active(self, since: datetime) -> list[MarketScanUniverse]:
        return list(
            self.db.execute(
                select(MarketScanUniverse)
                .where(MarketScanUniverse.last_seen_at >= since)
                .order_by(MarketScanUniverse.ticker)
            ).scalars()
        )

    def latest_refresh_time(self) -> datetime | None:
        return self.db.execute(
            select(func.max(MarketScanUniverse.last_seen_at))
        ).scalar_one_or_none()

    def count(self) -> int:
        return int(
            self.db.execute(
                select(func.count()).select_from(MarketScanUniverse)
            ).scalar_one()
        )
