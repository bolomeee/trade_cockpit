from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class UserSettingsData(_CamelModel):
    account_size: float
    max_exposure_pct: float
    single_trade_risk_pct: float
    default_risk_per_trade_pct: float
    base_currency: str
    updated_at: datetime | None


class UserSettingsResponse(BaseModel):
    data: UserSettingsData
    message: str = "success"


class UserSettingsUpdate(_CamelModel):
    """PUT request body; all fields optional; unset fields are not overwritten."""

    account_size: float | None = Field(default=None, gt=0)
    max_exposure_pct: float | None = Field(default=None, ge=0, le=100)
    single_trade_risk_pct: float | None = Field(default=None, ge=0, le=5)
    default_risk_per_trade_pct: float | None = Field(default=None, ge=0, le=5)
    base_currency: str | None = Field(default=None, min_length=1, max_length=8)
