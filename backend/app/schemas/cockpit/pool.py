"""F205-c: Pydantic schemas for GET /api/cockpit/pool response."""
from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class PoolFunnel(_CamelModel):
    tradable: int
    trend: int
    rs: int
    fundamental: int
    action: int


class PoolItem(_CamelModel):
    ticker: str
    name: str
    sector: str | None
    price: float | None
    trend_score: int | None
    rs_percentile: float
    setup_type: str | None
    distance_to_pivot_pct: float | None
    distance_to_50ma_pct: float | None
    earnings_date: date | None
    days_until_earnings: int | None
    revenue_growth_yoy: float | None
    suggested_action: str | None
    in_watchlist: bool


class PoolData(_CamelModel):
    funnel: PoolFunnel
    items: list[PoolItem]


class PoolResponse(BaseModel):
    data: PoolData
    message: str = "success"
