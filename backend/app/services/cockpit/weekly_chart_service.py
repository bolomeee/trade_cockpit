"""F216-a: Weekly bar aggregation service — pure function + WeeklyChartService."""
from __future__ import annotations

from datetime import date
from typing import Any, TypedDict

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyBar, Stock
from app.repositories.stock_repository import StockRepository
from app.services.cockpit.chart_service import _compute_ma_series
from app.services.cockpit.cockpit_params import WEEKLY
from app.services.watchlist_service import APIError


class WeeklyBarDict(TypedDict):
    date: date
    open: float
    high: float
    low: float
    close: float
    volume: int


def aggregate_daily_to_weekly(daily_bars: list[dict[str, Any]]) -> list[WeeklyBarDict]:
    """Aggregate ascending daily bars into weekly bars grouped by ISO week.

    Each weekly bar's date is the last actual trading day of that week
    (not forced to Friday — handles short weeks and holiday closures).
    """
    if not daily_bars:
        return []
    sorted_bars = sorted(daily_bars, key=lambda b: b["date"])
    groups: dict[tuple[int, int], list[dict[str, Any]]] = {}
    for bar in sorted_bars:
        key = bar["date"].isocalendar()[:2]  # (iso_year, iso_week)
        groups.setdefault(key, []).append(bar)
    weekly: list[WeeklyBarDict] = []
    for key in sorted(groups):
        week_bars = groups[key]
        weekly.append(
            WeeklyBarDict(
                date=week_bars[-1]["date"],
                open=week_bars[0]["open"],
                high=max(b["high"] for b in week_bars),
                low=min(b["low"] for b in week_bars),
                close=week_bars[-1]["close"],
                volume=sum(b["volume"] for b in week_bars),
            )
        )
    return weekly


class WeeklyChartService:
    def __init__(self, db: Session) -> None:
        self._db = db
        self._stocks = StockRepository(db)

    def get_weekly_chart(self, ticker: str, weeks: int = WEEKLY.DEFAULT_WEEKS) -> dict[str, Any]:
        ticker = ticker.strip().upper()
        stock = self._stocks.get_by_ticker(ticker)
        if stock is None:
            raise APIError("NOT_FOUND", f"ticker {ticker} not found", 404)

        all_bars = self._load_all_bars(stock)

        if len(all_bars) < WEEKLY.MIN_DAILY_BARS_FOR_WEEKLY:
            return {
                "ticker": ticker,
                "weekly_bars": [],
                "weekly_mas": {str(p): [] for p in WEEKLY.WEEKLY_MAS},
            }

        all_weekly = aggregate_daily_to_weekly(all_bars)
        weekly_bars = all_weekly[-weeks:]

        weekly_mas: dict[str, list[dict[str, Any]]] = {}
        for period in WEEKLY.WEEKLY_MAS:
            weekly_mas[str(period)] = _compute_ma_series(weekly_bars, period)

        return {"ticker": ticker, "weekly_bars": weekly_bars, "weekly_mas": weekly_mas}

    def _load_all_bars(self, stock: Stock) -> list[dict[str, Any]]:
        stmt = (
            select(DailyBar)
            .where(DailyBar.stock_id == stock.id)
            .order_by(DailyBar.date.asc())
        )
        rows = list(self._db.execute(stmt).scalars().all())
        return [
            {
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in rows
        ]
