"""F206-a: Position Pydantic schemas (D074 camelCase via to_camel alias_generator)."""
from __future__ import annotations

from datetime import date, datetime
from typing import Literal

import pydantic
from pydantic import BaseModel, ConfigDict, Field, model_validator
from pydantic.alias_generators import to_camel

_VALID_SETUP_TYPES = Literal[
    "BREAKOUT", "PULLBACK", "CAPITULATION", "RECLAIM", "EARNINGS_DRIFT", "EXTENDED", "BROKEN", "NONE"
]

_VALID_NEXT_ACTIONS = Literal["hold", "raise_stop", "reduce", "exit"]


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


# ---------------------------------------------------------------------------
# Request schemas
# ---------------------------------------------------------------------------


class PositionCreate(_CamelModel):
    ticker: str = Field(min_length=1, max_length=10)
    entry_price: float = Field(gt=0)
    entry_date: date
    shares: int = Field(gt=0)
    stop_price: float = Field(gt=0)
    target_2r: float | None = Field(default=None, gt=0)
    target_3r: float | None = Field(default=None, gt=0)
    setup_type: _VALID_SETUP_TYPES | None = None
    notes: str | None = None

    @model_validator(mode="after")
    def entry_must_exceed_stop(self) -> "PositionCreate":
        if self.entry_price <= self.stop_price:
            raise ValueError("entryPrice must be greater than stopPrice")
        return self

    @model_validator(mode="after")
    def entry_date_not_future(self) -> "PositionCreate":
        if self.entry_date > date.today():
            raise ValueError("entryDate cannot be a future date")
        return self


class PositionUpdate(_CamelModel):
    """PATCH body — all fields optional; status=CLOSED requires closedAt + closePrice."""

    stop_price: float | None = Field(default=None, gt=0)
    target_2r: float | None = Field(default=None, gt=0)
    target_3r: float | None = Field(default=None, gt=0)
    setup_type: _VALID_SETUP_TYPES | None = None
    notes: str | None = None
    status: Literal["OPEN", "CLOSED"] | None = None
    closed_at: datetime | None = None
    close_price: float | None = Field(default=None, gt=0)

    @model_validator(mode="after")
    def closed_requires_metadata(self) -> "PositionUpdate":
        if self.status == "CLOSED":
            if self.closed_at is None or self.close_price is None:
                raise ValueError(
                    "status=CLOSED requires both closedAt and closePrice"
                )
        return self

    @model_validator(mode="after")
    def no_reopen(self) -> "PositionUpdate":
        # Enforcement happens at service layer (needs current status); schema allows OPEN
        # but service will reject CLOSED→OPEN.
        return self


# ---------------------------------------------------------------------------
# Response schemas
# ---------------------------------------------------------------------------


class PositionItem(_CamelModel):
    """Single position in all responses (GET list / POST / PATCH)."""

    id: int
    ticker: str
    entry_price: float
    entry_date: date
    shares: int
    stop_price: float
    target_2r: float | None
    target_3r: float | None
    setup_type: str | None
    notes: str | None
    status: str
    closed_at: datetime | None
    close_price: float | None
    created_at: datetime
    updated_at: datetime

    # computed (server-side)
    last_close: float | None = None
    r_multiple: float | None = None
    unrealized_pl: float | None = None
    position_value: float | None = None
    earnings_date: str | None = None
    days_until_earnings: int | None = None
    next_action: _VALID_NEXT_ACTIONS = "hold"
    recommended_shares: int | None = None  # populated only in POST response


class PositionSummary(_CamelModel):
    open_risk_pct: float | None
    total_exposure_pct: float | None
    pending_risk_pct: float | None
    positions_count: int
    pending_count: int


class _PositionListData(_CamelModel):
    summary: PositionSummary
    items: list[PositionItem]


class PositionListResponse(BaseModel):
    data: _PositionListData
    message: str = "success"


class _PositionDeleteData(BaseModel):
    id: int
    deleted: bool = True


class PositionDeleteResponse(BaseModel):
    data: _PositionDeleteData
    message: str = "success"


class PositionSingleResponse(BaseModel):
    data: PositionItem
    message: str = "success"
