from __future__ import annotations

from datetime import date as DateType, datetime
from typing import Literal

from pydantic import Field

from app.schemas.watchlist import CamelModel

Action = Literal["BUY", "SELL", "ADD", "REDUCE", "WATCH"]


class JournalEntryOut(CamelModel):
    id: int
    ticker: str
    stock_name: str
    action: Action
    price: float
    date: DateType
    position_size: float | None = None
    stop_loss: float | None = None
    target_price: float | None = None
    reason: str | None = None
    reference: str | None = None
    created_at: datetime
    updated_at: datetime


class JournalListOut(CamelModel):
    items: list[JournalEntryOut]
    total: int
    limit: int
    offset: int


class JournalEntryCreate(CamelModel):
    ticker: str = Field(min_length=1, max_length=10)
    action: Action
    price: float = Field(gt=0)
    date: DateType
    position_size: float | None = Field(default=None, ge=0)
    stop_loss: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    reason: str | None = None
    reference: str | None = None


class JournalEntryUpdate(CamelModel):
    ticker: str | None = Field(default=None, min_length=1, max_length=10)
    action: Action | None = None
    price: float | None = Field(default=None, gt=0)
    date: DateType | None = None
    position_size: float | None = Field(default=None, ge=0)
    stop_loss: float | None = Field(default=None, ge=0)
    target_price: float | None = Field(default=None, ge=0)
    reason: str | None = None
    reference: str | None = None


class JournalDeleteOut(CamelModel):
    id: int
    deleted: bool
