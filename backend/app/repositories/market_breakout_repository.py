from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.market_breakout_scan import MarketBreakoutScan


@dataclass(frozen=True)
class BreakoutScanRow:
    """单次扫描命中的 breakout 记录。"""

    scan_date: date
    ticker: str
    company_name: str
    close_price: float
    ma150_value: float
    pct_above_ma150: float
    slope_value: float
    market_cap: int
    scanned_at: datetime


@dataclass(frozen=True)
class BreakoutSnapshot:
    """一次扫描的完整快照（用于读端点返回）。"""

    scan_date: date
    scanned_at: datetime
    items: list[MarketBreakoutScan]


class MarketBreakoutRepository:
    """D040：只存最新快照，覆盖写入。

    replace_scan 在单事务内 DELETE + INSERT。中途异常回滚，旧快照保留。
    """

    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_scan(self, rows: Iterable[BreakoutScanRow]) -> int:
        rows_list = list(rows)
        # 以 SAVEPOINT 事务确保 DELETE + INSERT 原子：中途异常回滚后旧数据保留
        with self.db.begin_nested():
            self.db.execute(delete(MarketBreakoutScan))
            for r in rows_list:
                self.db.execute(
                    MarketBreakoutScan.__table__.insert().values(
                        scan_date=r.scan_date,
                        ticker=r.ticker,
                        company_name=r.company_name,
                        close_price=r.close_price,
                        ma150_value=r.ma150_value,
                        pct_above_ma150=r.pct_above_ma150,
                        slope_value=r.slope_value,
                        market_cap=int(r.market_cap),
                        scanned_at=r.scanned_at,
                    )
                )
        self.db.commit()
        return len(rows_list)

    def get_latest_snapshot(self) -> BreakoutSnapshot | None:
        # 最新 scan：按 scanned_at DESC 取 top 1，锁定其 scan_date，再拉该日全部命中
        top = self.db.execute(
            select(MarketBreakoutScan.scan_date, MarketBreakoutScan.scanned_at)
            .order_by(MarketBreakoutScan.scanned_at.desc())
            .limit(1)
        ).first()
        if top is None:
            return None
        scan_date, scanned_at = top

        items = list(
            self.db.execute(
                select(MarketBreakoutScan)
                .where(MarketBreakoutScan.scan_date == scan_date)
                .order_by(MarketBreakoutScan.pct_above_ma150.asc())
            ).scalars()
        )
        return BreakoutSnapshot(
            scan_date=scan_date, scanned_at=scanned_at, items=items
        )
