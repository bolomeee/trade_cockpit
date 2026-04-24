"""Financial Modeling Prep (FMP) /stable/ REST client.

D034 (2026-04-19): primary external data source, replacing Polygon.io.
Endpoint paths are declared as module-level constants so future FMP path
changes touch only this file.

Rate limit policy (ARCHITECTURE.md, D044):
- FMP Starter: 300 req/min documented
- Token bucket: capacity 50 (burst), refill 1 token / 0.2s → 5 rps steady
- Concurrency cap: Semaphore(6) — prevents burst-stacking against a single endpoint
- Both limits are process-shared via a module-level default limiter so that
  scanner / watchlist refresh / user-triggered calls cannot aggregate past 300 rpm
- On 429: exponential backoff (1s → 2s → 4s, cap 8s) with up to MAX_RETRIES_429
  retries; honors server-supplied `Retry-After` header (seconds or HTTP-date)
  when present; exhausting retries raises HTTPStatusError
"""
from __future__ import annotations

import threading
import time
from datetime import date, datetime, timedelta, timezone
from typing import Any, Callable

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
FMP_EP_SHARES_FLOAT = "/shares-float"  # F107-b1 shares_float source (D051 rev)
FMP_EP_FMP_ARTICLES = "/fmp-articles"  # F112-a news proxy
FMP_EP_EARNINGS_CALENDAR = "/earnings-calendar"  # F204-a earnings events

# F105: status codes that trigger the SMA → EOD fallback in get_ma150_series_or_eod.
# Narrow set on purpose: 402 (paywall / tier unavailable), 403 (forbidden),
# 404 (endpoint not found). 5xx and connection errors are considered transient
# upstream problems and must surface rather than mask behind a data-path switch.
_SMA_FALLBACK_STATUS_CODES: frozenset[int] = frozenset({402, 403, 404})

# F105 default SMA window was 35 days (25 trading days) — enough for legacy
# crossover + 20-day slope. F106 A1 requires 60-trading-day MA150 horizontality
# check, so bumped to 90 calendar days (~63 trading days with buffer).
_SMA_DEFAULT_WINDOW_DAYS: int = 90
# F105 EOD fallback window: 260 calendar days ≈ 180 trading days, enough for
# MA150 + 20-day slope even after weekends/holidays.
_EOD_FALLBACK_WINDOW_DAYS: int = 260


class _FmpRateLimiter:
    """Process-shareable FMP rate limiter (D044).

    Combines:
    - Token bucket (capacity=RATE_CAPACITY, refill=1/REFILL_INTERVAL_S) — long-run rate cap
    - Semaphore(CONCURRENCY_LIMIT) — in-flight cap to prevent burst-stacking

    Acquire order in `_request`: concurrency semaphore first (blocks at 6 in-flight),
    then token bucket (blocks at 300 rpm). Release semaphore in `finally`.

    A module-level singleton (see `default_rate_limiter()`) backs production
    FmpClient instances so multiple DI factories share one bucket. Tests can
    construct fresh limiters to avoid cross-test state.
    """

    RATE_CAPACITY: int = 50  # burst
    WINDOW_S: float = 60.0
    RATE_PER_WINDOW: int = 300
    REFILL_INTERVAL_S: float = WINDOW_S / RATE_PER_WINDOW  # 0.2s
    CONCURRENCY_LIMIT: int = 6  # F105-a5

    def __init__(
        self,
        *,
        time_source: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self._time = time_source
        self._sleep = sleep
        self._lock = threading.Lock()
        self._tokens: float = float(self.RATE_CAPACITY)
        self._last_refill: float = self._time()
        self._semaphore = threading.BoundedSemaphore(self.CONCURRENCY_LIMIT)

    def acquire_concurrency(self) -> None:
        self._semaphore.acquire()

    def release_concurrency(self) -> None:
        self._semaphore.release()

    def acquire_token(self) -> None:
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


_default_limiter: _FmpRateLimiter | None = None
_default_limiter_lock = threading.Lock()


def default_rate_limiter() -> _FmpRateLimiter:
    """Return the process-shared FMP rate limiter singleton (D044)."""
    global _default_limiter
    if _default_limiter is None:
        with _default_limiter_lock:
            if _default_limiter is None:
                _default_limiter = _FmpRateLimiter()
    return _default_limiter


def reset_default_rate_limiter() -> None:
    """Reset the module-level singleton. Test-only helper."""
    global _default_limiter
    with _default_limiter_lock:
        _default_limiter = None


class FmpClient:
    """Thread-safe FMP client.

    Rate limiting is delegated to an injected `_FmpRateLimiter` (D044). By
    default this is the process-wide singleton so all FmpClient instances
    share one bucket + one semaphore. Tests may inject a fresh limiter.
    """

    # Kept for backwards-compat test references (test_fmp_client.py reads these).
    RATE_CAPACITY: int = _FmpRateLimiter.RATE_CAPACITY
    WINDOW_S: float = _FmpRateLimiter.WINDOW_S
    RATE_PER_WINDOW: int = _FmpRateLimiter.RATE_PER_WINDOW
    REFILL_INTERVAL_S: float = _FmpRateLimiter.REFILL_INTERVAL_S
    CONCURRENCY_LIMIT: int = _FmpRateLimiter.CONCURRENCY_LIMIT
    RETRY_BACKOFF_S: float = 1.0  # base delay for exponential backoff on 429
    RETRY_BACKOFF_MAX_S: float = 8.0  # cap per-retry wait
    MAX_RETRIES_429: int = 3  # total attempts = 1 + MAX_RETRIES_429
    RETRY_AFTER_CAP_S: float = 30.0  # ignore absurd server Retry-After values

    def __init__(
        self,
        api_key: str | None = None,
        _time_source: Callable[[], float] = time.monotonic,
        _sleep: Callable[[float], None] = time.sleep,
        _http_client: httpx.Client | None = None,
        rate_limiter: _FmpRateLimiter | None = None,
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
        self._sleep = _sleep
        self._limiter = (
            rate_limiter
            if rate_limiter is not None
            else _FmpRateLimiter(time_source=_time_source, sleep=_sleep)
        )

    # --- rate limiter shims (kept for test compat) ---------------------

    def _acquire(self) -> None:
        self._limiter.acquire_token()

    # --- request helper -------------------------------------------------

    def _request(self, path: str, params: dict[str, Any]) -> Any:
        merged = {**params, "apikey": self._api_key}

        self._limiter.acquire_concurrency()
        try:
            for attempt in range(self.MAX_RETRIES_429 + 1):
                self._limiter.acquire_token()
                resp = self._http.get(path, params=merged)
                if resp.status_code != 429 or attempt == self.MAX_RETRIES_429:
                    break
                wait = self._retry_after_seconds(resp) or min(
                    self.RETRY_BACKOFF_S * (2 ** attempt),
                    self.RETRY_BACKOFF_MAX_S,
                )
                self._sleep(wait)
            resp.raise_for_status()
            return resp.json()
        finally:
            self._limiter.release_concurrency()

    def _retry_after_seconds(self, resp: httpx.Response) -> float | None:
        """Parse Retry-After (seconds or HTTP-date). Capped to RETRY_AFTER_CAP_S."""
        raw = resp.headers.get("Retry-After")
        if not raw:
            return None
        try:
            seconds = float(raw)
        except ValueError:
            try:
                from email.utils import parsedate_to_datetime

                target = parsedate_to_datetime(raw)
                if target.tzinfo is None:
                    target = target.replace(tzinfo=timezone.utc)
                seconds = (target - datetime.now(timezone.utc)).total_seconds()
            except (TypeError, ValueError):
                return None
        if seconds <= 0:
            return None
        return min(seconds, self.RETRY_AFTER_CAP_S)

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

    def get_shares_float(self, symbol: str) -> dict[str, Any] | None:
        """FMP `/stable/shares-float` for a single symbol (F107-b1, D051 rev).

        The `/profile` endpoint does not carry float share data on the Starter
        tier; the dedicated `/shares-float` endpoint returns
        `{symbol, date, freeFloat, floatShares, outstandingShares, source}`.
        Callers should read `floatShares` (canonical), with a defensive
        fallback to legacy `sharesFloat` for forward-compat. Shares the D044
        rate limiter via `_request`.

        Returns the first record dict, or None if FMP returns an empty array /
        absent record (e.g. ETF, unknown ticker). HTTP errors propagate — the
        service layer decides whether to swallow or surface.
        """
        body = self._request(FMP_EP_SHARES_FLOAT, {"symbol": symbol})
        results = list(body or [])
        if not results:
            return None
        return results[0]

    def get_company_screener_page(
        self,
        market_cap_gte: int,
        exchange: str,
        *,
        is_etf: bool | None = None,
        is_fund: bool | None = None,
        is_actively_trading: bool = True,
        limit: int = 500,
    ) -> list[Any]:
        """Single-exchange FMP company screener call (F105 universe, D038).

        `is_etf` / `is_fund`: `True` includes only, `False` excludes, `None`
        omits the filter (both allowed). Returns FMP's raw list of screener
        rows. Caller should use `get_screener_universe` for the three-exchange
        merge.
        """
        params: dict[str, Any] = {
            "marketCapMoreThan": market_cap_gte,
            "exchange": exchange,
            "isActivelyTrading": "true" if is_actively_trading else "false",
            "limit": limit,
        }
        if is_etf is not None:
            params["isEtf"] = "true" if is_etf else "false"
        if is_fund is not None:
            params["isFund"] = "true" if is_fund else "false"
        body = self._request(FMP_EP_SCREENER, params)
        return list(body or [])

    def get_screener_universe(
        self,
        market_cap_gte: int = 50_000_000_000,
        exchanges: tuple[str, ...] = ("NYSE", "NASDAQ", "AMEX"),
        limit_per_exchange: int = 500,
    ) -> list[dict[str, Any]]:
        """Merged, de-duplicated screener universe across US exchanges (F105, D038).

        Includes common stocks, ADRs, and ETFs (what the user trades);
        excludes mutual funds via `isFund=false`. De-duplicates by `symbol`,
        first-seen wins. Any per-exchange error propagates.
        """
        seen: set[str] = set()
        merged: list[dict[str, Any]] = []
        for exchange in exchanges:
            rows = self.get_company_screener_page(
                market_cap_gte=market_cap_gte,
                exchange=exchange,
                is_fund=False,
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

    def get_fmp_articles(
        self, page: int = 0, limit: int = 20
    ) -> list[dict[str, Any]]:
        """FMP `/stable/fmp-articles` (F112-a news source).

        Returns raw FMP JSON list, sorted by FMP in `date` desc. Field
        normalization is the service layer's job. Shares D044 rate limiter.
        """
        params = {"page": page, "limit": limit}
        body = self._request(FMP_EP_FMP_ARTICLES, params)
        return list(body or [])

    def get_key_metrics_ttm(self, symbol: str) -> dict[str, Any] | None:
        """TTM key metrics (valuation) for a single symbol. Source for PE/PS/PEG/ROCE/FCF/marketCap (D035)."""
        body = self._request(FMP_EP_KEY_METRICS_TTM, {"symbol": symbol})
        results = list(body or [])
        if not results:
            return None
        return results[0]

    def get_earnings_calendar(self, from_date: str, to_date: str) -> list[Any]:
        """FMP `/stable/earnings-calendar` (F204-a).

        from_date / to_date: YYYY-MM-DD strings.
        Returns raw list; field normalization is the service layer's job.
        Expected fields per item: symbol, date, epsEstimated, eps,
        revenueEstimated, revenue, time (BMO/AMC/--).
        """
        params = {"from": from_date, "to": to_date}
        body = self._request(FMP_EP_EARNINGS_CALENDAR, params)
        return list(body or [])


def _fmt_date(d: str | date) -> str:
    if isinstance(d, date):
        return d.isoformat()
    return d
