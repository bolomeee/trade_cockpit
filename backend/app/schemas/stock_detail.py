from __future__ import annotations

from datetime import date

from app.schemas.watchlist import CamelModel


class ChartBar(CamelModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartMa150Point(CamelModel):
    date: date
    value: float


class ChartPullbackMarker(CamelModel):
    date: date
    distance_pct: float


class ChartData(CamelModel):
    ticker: str
    bars: list[ChartBar]
    ma150: list[ChartMa150Point]
    pullback_markers: list[ChartPullbackMarker]


class PullbackEntry(CamelModel):
    date: date
    close_price: float
    ma150_value: float
    distance_pct: float
    return_10d: float | None = None
    return_20d: float | None = None
    return_30d: float | None = None


class Fundamentals(CamelModel):
    ticker: str
    price_to_earnings: float
    price_to_sales: float
    peg: float
    free_cash_flow: float
    market_cap: float
    source: str
    updated_at: date
