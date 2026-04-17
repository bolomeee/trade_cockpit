from __future__ import annotations

from datetime import date

from app.schemas.watchlist import CamelModel


class MarketIndexOut(CamelModel):
    symbol: str
    name: str
    close: float
    prev_close: float | None = None
    change_pct: float | None = None
    date: date
