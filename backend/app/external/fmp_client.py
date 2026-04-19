"""Financial Modeling Prep (FMP) /stable/ REST client.

D034 (2026-04-19): primary external data source, replacing Polygon.io.
Endpoint paths are declared as module-level constants so future FMP path
changes touch only this file.

Rate limit policy (ARCHITECTURE.md):
- FMP Starter: 300 req/min documented
- Token bucket: capacity 50 (burst), refill 1 token / 0.2s
- On 429: backoff 1s, retry once; further 429 raises HTTPStatusError
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any

import httpx

from app.config import settings

FMP_BASE = "https://financialmodelingprep.com/stable"
FMP_EP_RATIOS_TTM = "/ratios-ttm"
FMP_EP_KEY_METRICS_TTM = "/key-metrics-ttm"
FMP_EP_HIST_EOD = "/historical-price-eod/full"
FMP_EP_TREASURY = "/treasury-rates"
FMP_EP_SEARCH_SYMBOL = "/search-symbol"
FMP_EP_SEARCH_NAME = "/search-name"
FMP_EP_QUOTE = "/quote"


class FmpClient:
    """Thread-safe FMP client with token-bucket rate limiter and 429 retry."""

    RATE_CAPACITY: int = 50  # burst
    WINDOW_S: float = 60.0
    RATE_PER_WINDOW: int = 300
    REFILL_INTERVAL_S: float = WINDOW_S / RATE_PER_WINDOW  # 0.2s
    RETRY_BACKOFF_S: float = 1.0

    def __init__(
        self,
        api_key: str | None = None,
        _time_source=time.monotonic,
        _sleep=time.sleep,
        _http_client: httpx.Client | None = None,
    ):
        key = api_key if api_key is not None else settings.fmp_api_key
        if not key:
            raise RuntimeError("FMP_API_KEY not set")

        self._api_key = key
        self._http = (
            _http_client
            if _http_client is not None
            else httpx.Client(base_url=FMP_BASE, timeout=10.0)
        )
        self._lock = threading.Lock()
        self._time = _time_source
        self._sleep = _sleep

        self._tokens: float = float(self.RATE_CAPACITY)
        self._last_refill: float = self._time()

    # --- rate limiter ---------------------------------------------------

    def _acquire(self) -> None:
        while True:
            with self._lock:
                now = self._time()
                elapsed = now - self._last_refill
                if elapsed > 0:
                    refill = elapsed / self.REFILL_INTERVAL_S
                    self._tokens = min(
                        float(self.RATE_CAPACITY), self._tokens + refill
                    )
                    self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                wait = (1.0 - self._tokens) * self.REFILL_INTERVAL_S

            self._sleep(wait)

    # --- request helper -------------------------------------------------

    def _request(self, path: str, params: dict[str, Any]) -> Any:
        merged = {**params, "apikey": self._api_key}

        self._acquire()
        resp = self._http.get(path, params=merged)
        if resp.status_code == 429:
            self._sleep(self.RETRY_BACKOFF_S)
            self._acquire()
            resp = self._http.get(path, params=merged)
        resp.raise_for_status()
        return resp.json()

    # --- public API -----------------------------------------------------

    def search_tickers(self, query: str, limit: int = 10) -> list[Any]:
        """Two-phase search: symbol prefix → name fallback (preserves D028 ordering)."""
        q = query.strip()
        if not q:
            return []
        symbol_results = self._request(FMP_EP_SEARCH_SYMBOL, {"query": q, "limit": limit})
        if symbol_results:
            return list(symbol_results)[:limit]
        name_results = self._request(FMP_EP_SEARCH_NAME, {"query": q, "limit": limit})
        return list(name_results)[:limit]

    def get_daily_bars(
        self,
        symbol: str,
        from_date: str | date,
        to_date: str | date,
    ) -> list[Any]:
        """EOD daily bars for a stock symbol."""
        params = {
            "symbol": symbol,
            "from": _fmt_date(from_date),
            "to": _fmt_date(to_date),
        }
        body = self._request(FMP_EP_HIST_EOD, params)
        # FMP returns {"symbol": "...", "historical": [...]} or a bare list depending on endpoint variant
        if isinstance(body, dict):
            return list(body.get("historical") or [])
        return list(body or [])

    def get_index_recent_bars(self, symbol: str, days: int = 10) -> list[Any]:
        """Recent EOD bars for an index symbol (e.g. ^GSPC, ^NDX).

        Caller is responsible for mapping DB symbol (SPX/NDX) → FMP symbol (^GSPC/^NDX).
        """
        today = datetime.now(timezone.utc).date()
        from_ = today - timedelta(days=days)
        return self.get_daily_bars(symbol, from_, today)

    def get_treasury_10y_latest(self) -> dict[str, Any]:
        """Latest two 10Y treasury rates. Returns dict with both for change_pct calc."""
        body = self._request(FMP_EP_TREASURY, {})
        results = list(body or [])
        if not results:
            raise RuntimeError("treasury-rates: empty results")
        # FMP returns descending by date by default; keep defensive sort.
        results_sorted = sorted(
            results,
            key=lambda r: r.get("date") or "",
            reverse=True,
        )
        latest = results_sorted[0]
        prev = results_sorted[1] if len(results_sorted) > 1 else {}
        return {
            "date": latest.get("date"),
            "year10": latest.get("year10"),
            "prev_date": prev.get("date"),
            "prev_year10": prev.get("year10"),
        }

    def get_ratios_ttm(self, symbol: str) -> dict[str, Any] | None:
        """TTM financial ratios for a single symbol. Returns first record, or None if empty."""
        body = self._request(FMP_EP_RATIOS_TTM, {"symbol": symbol})
        results = list(body or [])
        if not results:
            return None
        return results[0]

    def get_key_metrics_ttm(self, symbol: str) -> dict[str, Any] | None:
        """TTM key metrics (valuation) for a single symbol. Source for PE/PS/PEG/ROCE/FCF/marketCap (D035)."""
        body = self._request(FMP_EP_KEY_METRICS_TTM, {"symbol": symbol})
        results = list(body or [])
        if not results:
            return None
        return results[0]


def _fmt_date(d: str | date) -> str:
    if isinstance(d, date):
        return d.isoformat()
    return d
