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
FMP_EP_SCREENER = "/company-screener"  # F105 universe (D038)
FMP_EP_SMA = "/technical-indicators/sma"  # F105 daily scan primary path (D039)

# F105: status codes that trigger the SMA → EOD fallback in get_ma150_series_or_eod.
# Narrow set on purpose: 402 (paywall / tier unavailable), 403 (forbidden),
# 404 (endpoint not found). 5xx and connection errors are considered transient
# upstream problems and must surface rather than mask behind a data-path switch.
_SMA_FALLBACK_STATUS_CODES: frozenset[int] = frozenset({402, 403, 404})

# F105 default SMA window: 35 calendar days ≈ 25 trading days (D039 "最近 25 交易日窗口").
_SMA_DEFAULT_WINDOW_DAYS: int = 35
# F105 EOD fallback window: 260 calendar days ≈ 180 trading days, enough for
# MA150 + 20-day slope even after weekends/holidays.
_EOD_FALLBACK_WINDOW_DAYS: int = 260


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

    def get_company_screener_page(
        self,
        market_cap_gte: int,
        exchange: str,
        *,
        is_etf: bool = False,
        is_actively_trading: bool = True,
        limit: int = 500,
    ) -> list[Any]:
        """Single-exchange FMP company screener call (F105 universe, D038).

        Returns FMP's raw list of screener rows (each item typically contains
        `symbol`, `companyName`, `exchange`, `marketCap`, etc.). Caller should
        use `get_screener_universe` for the three-exchange merge.
        """
        params = {
            "marketCapMoreThan": market_cap_gte,
            "exchange": exchange,
            "isEtf": "true" if is_etf else "false",
            "isActivelyTrading": "true" if is_actively_trading else "false",
            "limit": limit,
        }
        body = self._request(FMP_EP_SCREENER, params)
        return list(body or [])

    def get_screener_universe(
        self,
        market_cap_gte: int = 50_000_000_000,
        exchanges: tuple[str, ...] = ("NYSE", "NASDAQ", "AMEX"),
        limit_per_exchange: int = 500,
    ) -> list[dict[str, Any]]:
        """Merged, de-duplicated screener universe across US exchanges (F105, D038).

        Calls `get_company_screener_page` once per exchange and merges results,
        de-duplicating by `symbol` with first-seen wins (stable ordering for
        downstream consumers). Any per-exchange error propagates — the caller
        is responsible for retrying the whole refresh.
        """
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for exchange in exchanges:
            rows = self.get_company_screener_page(
                market_cap_gte=market_cap_gte,
                exchange=exchange,
                limit=limit_per_exchange,
            )
            for row in rows:
                if not isinstance(row, dict):
                    continue
                symbol = row.get("symbol")
                if not symbol or symbol in seen:
                    continue
                seen.add(symbol)
                merged.append(row)
        return merged

    def get_sma_series(
        self,
        symbol: str,
        period_length: int = 150,
        from_date: str | date | None = None,
        to_date: str | date | None = None,
        timeframe: str = "1day",
    ) -> list[Any]:
        """FMP `/technical-indicators/sma` time series (F105 daily scan primary path, D039).

        Each payload item contains `date / open / high / low / close / volume / sma`.
        When `from_date`/`to_date` are omitted, defaults to the most recent
        35 calendar days (≈ 25 trading days — enough for breakout judgement and
        20-day MA150 linear regression slope).
        """
        today = datetime.now(timezone.utc).date()
        to_d = to_date if to_date is not None else today
        from_d = (
            from_date
            if from_date is not None
            else today - timedelta(days=_SMA_DEFAULT_WINDOW_DAYS)
        )
        params = {
            "symbol": symbol,
            "periodLength": period_length,
            "timeframe": timeframe,
            "from": _fmt_date(from_d),
            "to": _fmt_date(to_d),
        }
        body = self._request(FMP_EP_SMA, params)
        if isinstance(body, dict):
            # Defensive: some FMP endpoints wrap payloads in {"historical": [...]}
            return list(body.get("historical") or [])
        return list(body or [])

    def get_ma150_series_or_eod(self, symbol: str) -> dict[str, Any]:
        """Transparent SMA → EOD fallback for F105 daily scan (D039).

        Primary path hits `/technical-indicators/sma?periodLength=150`. If the
        endpoint is unavailable on the current FMP tier (402/403/404), falls
        back to `/historical-price-eod/full` so the caller can compute MA150
        and the 20-day slope locally (reusing F002 signal_engine).

        Returns `{"source": "sma" | "eod_fallback", "bars": [...]}`. The
        caller (F105-a3 MarketScannerService) inspects `source` to decide
        whether to emit a SystemLog WARN — the client layer deliberately does
        not log, keeping external/ layer free of DB dependencies.
        """
        try:
            bars = self.get_sma_series(symbol, period_length=150)
            return {"source": "sma", "bars": bars}
        except httpx.HTTPStatusError as exc:
            if exc.response.status_code not in _SMA_FALLBACK_STATUS_CODES:
                raise
        today = datetime.now(timezone.utc).date()
        from_d = today - timedelta(days=_EOD_FALLBACK_WINDOW_DAYS)
        eod_bars = self.get_daily_bars(symbol, from_d, today)
        return {"source": "eod_fallback", "bars": eod_bars}

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
