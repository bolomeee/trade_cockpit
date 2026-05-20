"""F218-d7a: Pydantic response models for /api/cockpit/repricing-triggers."""
from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

TriggerType = Literal[
    "EARNINGS_ACCEL",
    "MARGIN_EXPANSION",
    "NEW_PRODUCT",
    "SECTOR_CYCLE",
    "BALANCE_INFLECTION",
]


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class RepricingTriggerItem(CamelModel):
    """单条 trigger 项（用于单标的 endpoint，不带 ticker）。"""

    trigger_type: TriggerType
    detected_date: str   # ISO date YYYY-MM-DD
    confidence: float
    evidence: dict[str, Any]  # camelCase keys；5 类 schema 见 DATA-MODEL §1080-1129
    computed_at: str     # ISO8601 UTC


class RepricingTriggerItemWithTicker(RepricingTriggerItem):
    """全市场 endpoint 用：单条带 ticker 字段。"""

    ticker: str


class TickerRepricingTriggersData(CamelModel):
    ticker: str
    triggers: list[RepricingTriggerItem]


class TickerRepricingTriggersResponse(BaseModel):
    data: TickerRepricingTriggersData
    message: str = "success"


class MarketRepricingTriggersData(CamelModel):
    triggers: list[RepricingTriggerItemWithTicker]
    total_count: int
    computed_at: str     # ISO8601 UTC


class MarketRepricingTriggersResponse(BaseModel):
    data: MarketRepricingTriggersData
    message: str = "success"
