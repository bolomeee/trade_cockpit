from __future__ import annotations

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class SetupSummary(CamelModel):
    total: int
    ready: int
    near: int
    extended: int
    broken: int
    none: int


class SetupItemResponse(CamelModel):
    ticker: str
    stock_name: str | None
    setup_type: str
    setup_quality: str | None
    entry_price: float | None
    stop_price: float | None
    target2r: float | None
    target3r: float | None
    distance_to_entry_pct: float | None
    reward_risk: float | None
    rs_percentile: float | None
    volume_status: str | None
    trend_score: int | None
    earnings_risk: str
    ready_signal: bool
    suggested_action: str | None
    scan_date: str
    volume_zscore: float | None = None
    obv_trend: str | None = None
    up_down_volume_ratio: float | None = None
    weekly_stage: int | None = None
    macd_divergence: str | None = None


class SetupMonitorData(CamelModel):
    summary: SetupSummary
    items: list[SetupItemResponse]


class SetupMonitorResponse(BaseModel):
    data: SetupMonitorData
    message: str = "success"
