"""F206-b1: PendingOrder Pydantic schemas (D074 camelCase)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

_VALID_SETUP_TYPES = Literal[
    "BREAKOUT", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"
]

_VALID_STATUSES = Literal["ACTIVE", "TRIGGERED", "CANCELLED", "EXPIRED"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PendingOrderCreate(_CamelModel):
    ticker: str = Field(min_length=1, max_length=10)
    setup_type: _VALID_SETUP_TYPES
    entry_price: float = Field(gt=0)
    stop_price: float = Field(gt=0)
    shares: int = Field(gt=0)
    target_2r: float | None = Field(default=None, gt=0)
    target_3r: float | None = Field(default=None, gt=0)
    expiration_date: date | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def entry_must_exceed_stop(self) -> "PendingOrderCreate":
        if self.entry_price <= self.stop_price:
            raise ValueError("entryPrice must be greater than stopPrice")
        return self

    @model_validator(mode="after")
    def expiration_not_in_past(self) -> "PendingOrderCreate":
        if self.expiration_date is not None and self.expiration_date < date.today():
            raise ValueError("expirationDate cannot be a past date")
        return self


class PendingOrderUpdate(_CamelModel):
    """PATCH body — all fields optional."""

    entry_price: float | None = Field(default=None, gt=0)
    stop_price: float | None = Field(default=None, gt=0)
    shares: int | None = Field(default=None, gt=0)
    target_2r: float | None = Field(default=None, gt=0)
    target_3r: float | None = Field(default=None, gt=0)
    expiration_date: date | None = None
    setup_type: _VALID_SETUP_TYPES | None = None
    notes: str | None = None
    status: _VALID_STATUSES | None = None

    @model_validator(mode="after")
    def paired_entry_stop_validation(self) -> "PendingOrderUpdate":
        """If both entry and stop are provided, validate entry > stop immediately."""
        if self.entry_price is not None and self.stop_price is not None:
            if self.entry_price <= self.stop_price:
                raise ValueError("entryPrice must be greater than stopPrice")
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PendingOrderItem(_CamelModel):
    """Single pending order in all responses."""

    id: int
    ticker: str
    setup_type: str
    entry_price: float
    stop_price: float
    shares: int
    target_2r: float | None
    target_3r: float | None
    expiration_date: date | None
    status: str
    notes: str | None
    created_at: datetime
    updated_at: datetime

    # computed server-side
    last_close: float | None = None
    distance_to_trigger_pct: float | None = None
    risk_pct: float | None = None


class PendingOrderListResponse(BaseModel):
    """GET /pending-orders — data is a direct array (not items-wrapped, per API-CONTRACT)."""

    data: list[PendingOrderItem]
    message: str = "success"


class PendingOrderSingleResponse(BaseModel):
    data: PendingOrderItem
    message: str = "success"


class _PendingOrderDeleteData(BaseModel):
    id: int
    deleted: bool = True


class PendingOrderDeleteResponse(BaseModel):
    data: _PendingOrderDeleteData
    message: str = "success"
