from __future__ import annotations

from datetime import date, datetime

from app.schemas.watchlist import CamelModel


class MarketIndexOut(CamelModel):
    symbol: str
    name: str
    close: float
    prev_close: float | None = None
    change_pct: float | None = None
    date: date


class BreakoutItemOut(CamelModel):
    ticker: str
    company_name: str
    close_price: float
    ma150_value: float
    pct_above_ma150: float
    market_cap: int


class BreakoutSnapshotOut(CamelModel):
    scan_date: date | None
    scanned_at: datetime | None
    items: list[BreakoutItemOut]
    total: int
