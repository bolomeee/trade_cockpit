from __future__ import annotations

import json

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class RegimeSubscores(CamelModel):
    spy_trend: int
    qqq_trend: int
    iwm_breadth: int
    sector_participation: int
    risk_appetite: int
    volatility_stress: int


class RegimeIndexItem(CamelModel):
    symbol: str
    close: float | None
    change_pct: float | None
    above_ma50: bool
    above_ma200: bool
    rs_trend: str
    state: str


class RegimeSectorItem(CamelModel):
    symbol: str
    close: float | None
    change_pct: float | None
    state: str


class RegimeData(CamelModel):
    date: str
    regime: str
    market_score: int
    subscores: RegimeSubscores
    allowed_exposure_pct: float
    single_trade_risk_pct: float
    preferred_setups: list[str]
    avoid_setups: list[str]
    indices: list[RegimeIndexItem]
    sectors: list[RegimeSectorItem]
    computed_at: str


class RegimeResponse(BaseModel):
    data: RegimeData
    message: str = "success"
