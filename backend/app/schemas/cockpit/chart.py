from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel


class CamelModel(BaseModel):
    model_config = ConfigDict(
        alias_generator=to_camel,
        populate_by_name=True,
        from_attributes=True,
    )


class ChartBarItem(CamelModel):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


class ChartSeriesPoint(CamelModel):
    date: date
    value: float


class ChartAvwap(CamelModel):
    anchor: date | None
    series: list[ChartSeriesPoint]


class CockpitChartData(CamelModel):
    ticker: str
    bars: list[ChartBarItem]
    mas: dict[str, list[ChartSeriesPoint]]
    emas: dict[str, list[ChartSeriesPoint]]
    atr: list[ChartSeriesPoint]
    avwap: ChartAvwap


class CockpitChartResponse(BaseModel):
    data: CockpitChartData
    message: str = "success"
