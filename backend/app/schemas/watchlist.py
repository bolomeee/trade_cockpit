from __future__ import annotations

from datetime import datetime
from typing import Generic, Literal, TypeVar

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


T = TypeVar("T")


class ResponseEnvelope(CamelModel, Generic[T]):
    data: T
    message: str = "success"


class ErrorDetail(BaseModel):
    code: str
    message: str


class ErrorEnvelope(BaseModel):
    error: ErrorDetail


# --- Watchlist ---------------------------------------------------------------

DataStatus = Literal["loading", "insufficient", "ready"]


class LatestSignal(CamelModel):
    signal_type: str
    distance_pct: float | None = None
    date: str | None = None


class WatchlistItem(CamelModel):
    id: int
    ticker: str
    name: str
    exchange: str | None = None
    added_at: datetime
    last_refreshed_at: datetime | None = None
    data_status: DataStatus
    latest_signal: LatestSignal | None = None


class WatchlistCreatedItem(CamelModel):
    id: int
    ticker: str
    name: str
    exchange: str | None = None
    added_at: datetime
    data_status: DataStatus


class AddStockRequest(CamelModel):
    ticker: str = Field(min_length=1, max_length=10)


class DeleteStockResponse(CamelModel):
    ticker: str
    removed: bool


# --- Stock Search ------------------------------------------------------------


class StockSearchItem(CamelModel):
    ticker: str
    name: str
    exchange: str | None = None
    type: str | None = None
