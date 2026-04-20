"""Refresh SPX / NDX / TNX latest values via FMP /stable/ and persist into market_indices.

D034: SPX/NDX use `/stable/historical-price-eod/full` with FMP index symbols
`^GSPC` / `^NDX`; TNX uses `/stable/treasury-rates` `year10`. DB-layer
`market_indices.symbol` stays SPX/NDX/TNX (DATA-MODEL unchanged).

Each symbol is fetched independently; failure of one does not abort the others.
Writes OK / ERROR SystemLog entries so the logs page surfaces status.
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import date, datetime
from typing import Any

from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
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

# DB symbol → FMP fetch symbol (D034). TNX uses treasury-rates, not this map.
# NDX uses QQQM (Invesco NASDAQ 100 ETF) because FMP Starter plan does not
# cover the ^NDX licensed index; QQQM tracks NDX with >99% correlation.
_DB_TO_FMP_INDEX: dict[str, str] = {
    "SPX": "^GSPC",
    "NDX": "QQQM",
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
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self.db = db
        self.fmp = fmp
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
        fmp_symbol = _DB_TO_FMP_INDEX.get(symbol)
        if fmp_symbol is None:
            raise RuntimeError(f"{symbol}: no FMP mapping configured")

        bars = self.fmp.get_index_recent_bars(fmp_symbol)
        if not bars:
            raise RuntimeError(f"{symbol}: empty FMP historical response")

        # FMP returns descending by date; sort ascending for latest/prev access.
        sorted_bars = sorted(bars, key=lambda b: str(_get(b, "date") or ""))
        latest = sorted_bars[-1]
        prev = sorted_bars[-2] if len(sorted_bars) >= 2 else None

        close = _get(latest, "close")
        raw_date = _get(latest, "date")
        if close is None or raw_date is None:
            raise RuntimeError(f"{symbol}: missing close/date")

        row_date = _parse_iso_date(str(raw_date)[:10])
        prev_close = _get(prev, "close") if prev is not None else None
        return (
            row_date,
            float(close),
            float(prev_close) if prev_close is not None else None,
        )

    def _fetch_treasury(self) -> tuple[date, float, float | None]:
        data = self.fmp.get_treasury_10y_latest()
        latest_close = data.get("year10")
        latest_date = data.get("date")
        if latest_close is None or latest_date is None:
            raise RuntimeError("TNX: missing year10/date")
        prev_close = data.get("prev_year10")
        row_date = _parse_iso_date(str(latest_date)[:10])
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
