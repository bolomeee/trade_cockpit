from __future__ import annotations

from datetime import date

from pydantic import Field

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
    shares_float: int | None = None


class PullbackEntry(CamelModel):
    date: date
    close_price: float
    ma150_value: float
    distance_pct: float
    return_10d: float | None = Field(default=None, alias="return10d")
    return_20d: float | None = Field(default=None, alias="return20d")
    return_30d: float | None = Field(default=None, alias="return30d")


class Fundamentals(CamelModel):
    ticker: str
    price_to_earnings: float | None = None
    price_to_sales: float | None = None
    peg: float | None = None
    roce: float | None = None
    free_cash_flow: float | None = None
    market_cap: float | None = None
    shares_float: int | None = None
    source: str
    updated_at: date
