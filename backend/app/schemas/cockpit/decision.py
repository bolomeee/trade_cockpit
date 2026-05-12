from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel


class _CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class DecisionData(_CamelModel):
    ticker: str
    setup_type: str | None
    setup_quality: str | None
    entry_price: float
    stop_price: float
    # to_camel yields "target2R" for "target_2r" — explicit aliases needed
    target_2r: float = Field(alias="target2r")
    target_3r: float = Field(alias="target3r")
    reward_risk: float | None
    risk_per_share: float
    suggested_shares: int
    position_value: float
    account_risk_pct: float
    effective_risk_pct: float
    regime_cap: float
    user_setting_cap: float
    earnings_risk: str | None
    earnings_date: date | None
    deterministic_hash: str


class DecisionResponse(BaseModel):
    data: DecisionData
    message: str = "success"
