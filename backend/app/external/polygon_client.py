"""Polygon.io (massive) client wrapper with 5-calls-per-minute token-bucket rate limiter.

API surface is intentionally thin — only the methods F000-c / F003 / F006 need.
"""
from __future__ import annotations

import itertools
import threading
import time
from datetime import date
from typing import Any

from massive import RESTClient

from app.config import settings


class PolygonClient:
    """Thread-safe wrapper over `massive.RESTClient` with a token-bucket rate limiter.

    Polygon Stocks Basic tier allows 5 calls/minute. The bucket holds up to
    `RATE_CAPACITY` tokens and refills one token every `REFILL_INTERVAL_S`.
    """

    RATE_CAPACITY: int = 5
    WINDOW_S: float = 60.0
    REFILL_INTERVAL_S: float = WINDOW_S / RATE_CAPACITY  # 12s

    def __init__(self, api_key: str | None = None, _time_source=time.monotonic, _sleep=time.sleep):
        key = api_key if api_key is not None else settings.polygon_api_key
        if not key:
            raise RuntimeError("POLYGON_API_KEY not set")

        self._client = RESTClient(api_key=key)
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
