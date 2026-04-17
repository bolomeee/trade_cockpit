"""Refresh SPX / NDX / TNX latest values via Polygon and persist into market_indices.

Each symbol is fetched independently; failure of one does not abort the others.
Writes OK / ERROR SystemLog entries so the logs page surfaces status.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.external.polygon_client import PolygonClient
from app.repositories.market_index_repository import (
    MARKET_INDEX_SYMBOLS,
    MARKET_INDEX_WINDOW,
    MarketIndexRepository,
)
from app.repositories.system_log_repository import SystemLogRepository

LOG_SOURCE = "market_refresh"

SYMBOL_NAMES: dict[str, str] = {
    "SPX": "S&P 500",
    "NDX": "NASDAQ 100",
    "TNX": "10-Year Treasury Yield",
}


@dataclass
class SymbolResult:
    symbol: str
    status: str  # "ok" | "error"
    error: str | None = None


@dataclass
class MarketBatchResult:
    completed: int
    failed: int
    results: list[SymbolResult]


class MarketRefreshService:
    def __init__(self, db: Session, polygon: PolygonClient) -> None:
        self.db = db
        self.polygon = polygon
        self.repo = MarketIndexRepository(db)
        self.log_repo = SystemLogRepository(db)

    def refresh_all(self) -> MarketBatchResult:
        results: list[SymbolResult] = []
        completed = 0
        failed = 0
        for symbol in MARKET_INDEX_SYMBOLS:
            try:
                self._refresh_one(symbol)
            except Exception as exc:  # noqa: BLE001 — isolate per-symbol failure
                self.log_repo.create(
                    level="ERROR",
                    source=LOG_SOURCE,
                    message=f"{symbol} refresh failed: {exc}",
                    detail=traceback.format_exc(),
                )
                results.append(SymbolResult(symbol=symbol, status="error", error=str(exc)))
                failed += 1
                continue

            self.log_repo.create(
                level="OK",
                source=LOG_SOURCE,
                message=f"{symbol} refreshed",
            )
            results.append(SymbolResult(symbol=symbol, status="ok"))
            completed += 1

        return MarketBatchResult(completed=completed, failed=failed, results=results)

    # ----- internals -----

    def _refresh_one(self, symbol: str) -> None:
        if symbol == "TNX":
            row_date, close, prev_close = self._fetch_treasury()
        else:
            row_date, close, prev_close = self._fetch_index(symbol)

        change_pct = _change_pct(close, prev_close)
        self.repo.upsert(
            symbol=symbol,
            name=SYMBOL_NAMES[symbol],
            date_=row_date,
            close=close,
            prev_close=prev_close,
            change_pct=change_pct,
        )
        self.repo.prune_to_window(symbol, MARKET_INDEX_WINDOW)

    def _fetch_index(self, symbol: str) -> tuple[date, float, float | None]:
        aggs = self.polygon.get_index_recent_aggs(symbol)
        if not aggs:
            raise RuntimeError(f"{symbol}: empty aggregate response")

        # list_aggs returns ascending by date; take last two for latest + prev.
        bars = sorted(aggs, key=lambda b: _get(b, "timestamp") or 0)
        latest = bars[-1]
        prev = bars[-2] if len(bars) >= 2 else None

        close = _get(latest, "close")
        ts_ms = _get(latest, "timestamp")
        if close is None or ts_ms is None:
            raise RuntimeError(f"{symbol}: missing close/timestamp")

        row_date = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()
        prev_close = _get(prev, "close") if prev is not None else None
        return (
            row_date,
            float(close),
            float(prev_close) if prev_close is not None else None,
        )

    def _fetch_treasury(self) -> tuple[date, float, float | None]:
        data = self.polygon.get_treasury_10y_latest()
        latest_close = data.get("yield_10_year")
        latest_date = data.get("date")
        if latest_close is None or latest_date is None:
            raise RuntimeError("TNX: missing yield_10_year/date")
        prev_close = data.get("prev_yield_10_year")
        row_date = _parse_iso_date(latest_date)
        return (
            row_date,
            float(latest_close),
            float(prev_close) if prev_close is not None else None,
        )


def _change_pct(close: float, prev_close: float | None) -> float | None:
    if prev_close is None or prev_close == 0:
        return None
    return round((close - prev_close) / prev_close * 100, 4)


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _parse_iso_date(s: str) -> date:
    return datetime.strptime(s, "%Y-%m-%d").date()
