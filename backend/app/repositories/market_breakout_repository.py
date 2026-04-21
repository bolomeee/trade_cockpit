from __future__ import annotations

from dataclasses import dataclass
from datetime import date, datetime
from typing import Iterable

from sqlalchemy import delete, select
from sqlalchemy.orm import Session

from app.models.market_breakout_scan import MarketBreakoutScan


@dataclass(frozen=True)
class BreakoutScanRow:
    """单次扫描命中的信号记录。F106 起支持多 signal_type。"""

    scan_date: date
    ticker: str
    company_name: str
    signal_type: str
    close_price: float
    ma150_value: float
    pct_above_ma150: float
    slope_value: float
    market_cap: int
    scanned_at: datetime
    volume: int | None = None
    volume_ratio_20: float | None = None


@dataclass(frozen=True)
class BreakoutSnapshot:
    """一次扫描的完整快照（用于读端点返回）。"""

    scan_date: date
    scanned_at: datetime
    items: list[MarketBreakoutScan]


class MarketBreakoutRepository:
    """D040 + D045：只存最新快照，覆盖写入；单表多 signal_type。"""

    def __init__(self, db: Session) -> None:
        self.db = db

    def replace_scan(self, rows: Iterable[BreakoutScanRow]) -> int:
        rows_list = list(rows)
        with self.db.begin_nested():
            self.db.execute(delete(MarketBreakoutScan))
            for r in rows_list:
                self.db.execute(
                    MarketBreakoutScan.__table__.insert().values(
                        scan_date=r.scan_date,
                        ticker=r.ticker,
                        company_name=r.company_name,
                        signal_type=r.signal_type,
                        close_price=r.close_price,
                        ma150_value=r.ma150_value,
                        pct_above_ma150=r.pct_above_ma150,
                        slope_value=r.slope_value,
                        volume=int(r.volume) if r.volume is not None else None,
                        volume_ratio_20=r.volume_ratio_20,
                        market_cap=int(r.market_cap),
                        scanned_at=r.scanned_at,
                    )
                )
        self.db.commit()
        return len(rows_list)

    def get_latest_snapshot(
        self,
        signal_types: tuple[str, ...] | None = None,
    ) -> BreakoutSnapshot | None:
        """Return the latest scan snapshot, optionally filtered by signal_type.

        signal_types=None → return all rows from the latest scan_date.
        """
        top = self.db.execute(
            select(MarketBreakoutScan.scan_date, MarketBreakoutScan.scanned_at)
            .order_by(MarketBreakoutScan.scanned_at.desc())
            .limit(1)
        ).first()
        if top is None:
            return None
        scan_date, scanned_at = top

        stmt = (
            select(MarketBreakoutScan)
            .where(MarketBreakoutScan.scan_date == scan_date)
            .order_by(MarketBreakoutScan.pct_above_ma150.asc())
        )
        if signal_types is not None:
            stmt = stmt.where(MarketBreakoutScan.signal_type.in_(signal_types))

        items = list(self.db.execute(stmt).scalars())
        return BreakoutSnapshot(
            scan_date=scan_date, scanned_at=scanned_at, items=items
        )
