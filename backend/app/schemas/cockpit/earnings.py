from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class EarningsData(CamelModel):
    ticker: str
    next_earnings_date: str | None
    days_until: int | None
    time_of_day: str | None
    eps_estimate: float | None
    revenue_estimate: int | None
    note: str | None = None


class EarningsResponse(BaseModel):
    data: EarningsData
    message: str = "success"
