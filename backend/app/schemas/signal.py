from __future__ import annotations

from datetime import date
from typing import Literal

from app.schemas.watchlist import CamelModel


class SignalBoardItem(CamelModel):
    ticker: str
    name: str
    signal_type: str
    date: date
    close_price: float
    ma150_value: float | None = None
    distance_pct: float | None = None
    slope_positive: bool | None = None
    slope_value: float | None = None
    label_color: Literal["red", "yellow", "blue"] | None = None


class SignalLatest(CamelModel):
    signal_type: str
    date: date
    close_price: float
    ma150_value: float | None = None
    distance_pct: float | None = None
    slope_positive: bool | None = None
    slope_value: float | None = None


class SignalHistoryEntry(CamelModel):
    date: date
    signal_type: str
    close_price: float
    ma150_value: float | None = None
    distance_pct: float | None = None


class TickerSignalDetail(CamelModel):
    ticker: str
    name: str
    latest: SignalLatest | None = None
    history: list[SignalHistoryEntry]
