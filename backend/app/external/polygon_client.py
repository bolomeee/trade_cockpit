"""Polygon.io (massive) client wrapper with 5-calls-per-minute token-bucket rate limiter.

API surface is intentionally thin — only the methods F000-c / F003 / F006 need.
"""
from __future__ import annotations

import itertools
import threading
import time
from datetime import date
from typing import Any

import httpx
from massive import RESTClient

from app.config import settings

POLYGON_HTTP_BASE = "https://api.polygon.io"
INDEX_SYMBOL_PREFIX = "I:"


class PolygonClient:
    """Thread-safe wrapper over `massive.RESTClient` with a token-bucket rate limiter.

    Polygon Stocks Basic tier allows 5 calls/minute. The bucket holds up to
    `RATE_CAPACITY` tokens and refills one token every `REFILL_INTERVAL_S`.
    """

    RATE_CAPACITY: int = 5
    WINDOW_S: float = 60.0
    REFILL_INTERVAL_S: float = WINDOW_S / RATE_CAPACITY  # 12s

    def __init__(
        self,
        api_key: str | None = None,
        _time_source=time.monotonic,
        _sleep=time.sleep,
        _http_client: httpx.Client | None = None,
    ):
        key = api_key if api_key is not None else settings.polygon_api_key
        if not key:
            raise RuntimeError("POLYGON_API_KEY not set")

        self._api_key = key
        self._client = RESTClient(api_key=key)
        self._http = _http_client if _http_client is not None else httpx.Client(base_url=POLYGON_HTTP_BASE, timeout=10.0)
        self._lock = threading.Lock()
        self._time = _time_source
        self._sleep = _sleep

        self._tokens: float = float(self.RATE_CAPACITY)
        self._last_refill: float = self._time()

    def _acquire(self) -> None:
        while True:
            with self._lock:
                now = self._time()
                elapsed = now - self._last_refill
                if elapsed > 0:
                    refill = elapsed / self.REFILL_INTERVAL_S
                    self._tokens = min(float(self.RATE_CAPACITY), self._tokens + refill)
                    self._last_refill = now

                if self._tokens >= 1.0:
                    self._tokens -= 1.0
                    return

                wait = (1.0 - self._tokens) * self.REFILL_INTERVAL_S

            self._sleep(wait)

    def search_tickers(self, query: str, limit: int = 10) -> list[Any]:
        # `list_tickers` auto-paginates; `limit` is page size, not result cap.
        # Slice the iterator so we consume only one page's worth of HTTP calls.
        self._acquire()
        iterator = self._client.list_tickers(
            search=query,
            market="stocks",
            active=True,
            limit=limit,
        )
        return list(itertools.islice(iterator, limit))

    def get_previous_close(self, ticker: str) -> Any:
        self._acquire()
        return self._client.get_previous_close_agg(ticker=ticker, adjusted=True)

    def get_index_recent_aggs(self, symbol: str, days: int = 10) -> list[Any]:
        # Polygon indices share the aggregates endpoint with an "I:" prefix.
        # Using daily aggs so we get both latest close and prior close for change_pct.
        from datetime import datetime, timedelta, timezone

        ticker = f"{INDEX_SYMBOL_PREFIX}{symbol}"
        today = datetime.now(timezone.utc).date()
        from_ = today - timedelta(days=days)
        self._acquire()
        return list(
            self._client.list_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=from_,
                to=today,
                adjusted=True,
            )
        )

    def get_treasury_10y_latest(self) -> dict[str, Any]:
        # massive SDK does not wrap /fed/v1/treasury-yields; call HTTP directly.
        # Returns {"date": str, "yield_10_year": float, "prev_date": str|None, "prev_yield_10_year": float|None}
        self._acquire()
        resp = self._http.get(
            "/fed/v1/treasury-yields",
            params={"limit": 2, "sort": "date.desc", "apiKey": self._api_key},
        )
        resp.raise_for_status()
        body = resp.json()
        results = body.get("results") or []
        if not results:
            raise RuntimeError("treasury-yields: empty results")
        latest = results[0]
        prev = results[1] if len(results) > 1 else {}
        return {
            "date": latest.get("date"),
            "yield_10_year": latest.get("yield_10_year"),
            "prev_date": prev.get("date"),
            "prev_yield_10_year": prev.get("yield_10_year"),
        }

    def get_daily_aggs(self, ticker: str, from_date: str | date, to_date: str | date) -> list[Any]:
        self._acquire()
        return list(
            self._client.list_aggs(
                ticker=ticker,
                multiplier=1,
                timespan="day",
                from_=from_date,
                to=to_date,
                adjusted=True,
            )
        )
