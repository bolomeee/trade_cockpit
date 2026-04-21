"""Unit tests for FmpClient wrapper.

Covers:
  - missing API key raises RuntimeError
  - 5 wrapper methods hit correct endpoints with correct params
  - two-phase search (symbol → name fallback)
  - token-bucket rate limiter (burst 50, refill 1/0.2s, refill on time elapse)
  - 429 retry-once-then-raise behavior
"""
from __future__ import annotations

from typing import Callable

import httpx
import pytest

from app.external.fmp_client import (
    FMP_BASE,
    FMP_EP_HIST_EOD,
    FMP_EP_KEY_METRICS_TTM,
    FMP_EP_RATIOS_TTM,
    FMP_EP_SCREENER,
    FMP_EP_SEARCH_NAME,
    FMP_EP_SEARCH_SYMBOL,
    FMP_EP_SMA,
    FMP_EP_TREASURY,
    FmpClient,
    _FmpRateLimiter,
)


class FakeClock:
    def __init__(self, start: float = 1000.0):
        self.now = start
        self.sleeps: list[float] = []

    def time(self) -> float:
        return self.now

    def sleep(self, seconds: float) -> None:
        self.sleeps.append(seconds)
        self.now += seconds


@pytest.fixture
def clock() -> FakeClock:
    return FakeClock()


def make_client(
    handler: Callable[[httpx.Request], httpx.Response],
    clock: FakeClock,
    api_key: str = "test-key",
) -> tuple[FmpClient, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    transport = httpx.MockTransport(wrapped)
    http = httpx.Client(base_url=FMP_BASE, transport=transport, timeout=10.0)
    return FmpClient(api_key=api_key, _time_source=clock.time, _sleep=clock.sleep, _http_client=http), captured


def ok(payload) -> httpx.Response:
    return httpx.Response(200, json=payload)


# --- missing key ---------------------------------------------------------

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr("app.external.fmp_client.settings.fmp_api_key", "")
    with pytest.raises(RuntimeError, match="FMP_API_KEY not set"):
        FmpClient()


def test_explicit_empty_key_raises():
    with pytest.raises(RuntimeError, match="FMP_API_KEY not set"):
        FmpClient(api_key="")


# --- method endpoints ----------------------------------------------------

def test_search_tickers_symbol_phase(clock):
    def handler(req):
        return ok([{"symbol": "AAPL", "name": "Apple Inc."}])

    client, calls = make_client(handler, clock)
    result = client.search_tickers("AAPL", limit=5)

    assert result == [{"symbol": "AAPL", "name": "Apple Inc."}]
    assert len(calls) == 1
    assert calls[0].url.path.endswith(FMP_EP_SEARCH_SYMBOL)
    assert calls[0].url.params["query"] == "AAPL"
    assert calls[0].url.params["limit"] == "5"
    assert calls[0].url.params["apikey"] == "test-key"


def test_search_tickers_name_fallback(clock):
    responses = iter([ok([]), ok([{"symbol": "OXY", "name": "Occidental"}])])

    def handler(req):
        return next(responses)

    client, calls = make_client(handler, clock)
    result = client.search_tickers("occidental", limit=10)

    assert result == [{"symbol": "OXY", "name": "Occidental"}]
    assert len(calls) == 2
    assert calls[0].url.path.endswith(FMP_EP_SEARCH_SYMBOL)
    assert calls[1].url.path.endswith(FMP_EP_SEARCH_NAME)
    assert calls[1].url.params["query"] == "occidental"


def test_search_tickers_empty_query(clock):
    def handler(req):
        raise AssertionError("no HTTP call expected for empty query")

    client, calls = make_client(handler, clock)
    assert client.search_tickers("   ") == []
    assert calls == []


def test_get_daily_bars_endpoint(clock):
    def handler(req):
        return ok({"symbol": "AAPL", "historical": [{"date": "2026-04-18", "close": 200.0}]})

    client, calls = make_client(handler, clock)
    result = client.get_daily_bars("AAPL", "2026-01-01", "2026-04-18")

    assert result == [{"date": "2026-04-18", "close": 200.0}]
    assert calls[0].url.path.endswith(FMP_EP_HIST_EOD)
    assert calls[0].url.params["symbol"] == "AAPL"
    assert calls[0].url.params["from"] == "2026-01-01"
    assert calls[0].url.params["to"] == "2026-04-18"


def test_get_daily_bars_bare_list_response(clock):
    def handler(req):
        return ok([{"date": "2026-04-18", "close": 200.0}])

    client, _ = make_client(handler, clock)
    assert client.get_daily_bars("AAPL", "2026-01-01", "2026-04-18") == [
        {"date": "2026-04-18", "close": 200.0}
    ]


def test_get_index_recent_bars_passes_symbol_and_window(clock):
    captured_params: dict[str, str] = {}

    def handler(req):
        captured_params.update(req.url.params)
        return ok([{"date": "2026-04-18", "close": 5500.0}])

    client, calls = make_client(handler, clock)
    result = client.get_index_recent_bars("^GSPC", days=10)

    assert result == [{"date": "2026-04-18", "close": 5500.0}]
    assert calls[0].url.path.endswith(FMP_EP_HIST_EOD)
    assert captured_params["symbol"] == "^GSPC"
    assert "from" in captured_params and "to" in captured_params


def test_get_treasury_10y_latest(clock):
    def handler(req):
        return ok([
            {"date": "2026-04-18", "year10": 4.25},
            {"date": "2026-04-17", "year10": 4.20},
        ])

    client, calls = make_client(handler, clock)
    result = client.get_treasury_10y_latest()

    assert result == {
        "date": "2026-04-18",
        "year10": 4.25,
        "prev_date": "2026-04-17",
        "prev_year10": 4.20,
    }
    assert calls[0].url.path.endswith(FMP_EP_TREASURY)


def test_get_treasury_10y_handles_unsorted(clock):
    # Ensure defensive sort works if FMP order changes.
    def handler(req):
        return ok([
            {"date": "2026-04-17", "year10": 4.20},
            {"date": "2026-04-18", "year10": 4.25},
        ])

    client, _ = make_client(handler, clock)
    result = client.get_treasury_10y_latest()
    assert result["date"] == "2026-04-18"
    assert result["prev_date"] == "2026-04-17"


def test_get_treasury_10y_empty_raises(clock):
    def handler(req):
        return ok([])

    client, _ = make_client(handler, clock)
    with pytest.raises(RuntimeError, match="treasury-rates: empty results"):
        client.get_treasury_10y_latest()


def test_get_ratios_ttm(clock):
    payload = [{"symbol": "AAPL", "priceToEarningsRatioTTM": 33.84, "priceToSalesRatioTTM": 9.12}]

    def handler(req):
        return ok(payload)

    client, calls = make_client(handler, clock)
    result = client.get_ratios_ttm("AAPL")

    assert result == payload[0]
    assert calls[0].url.path.endswith(FMP_EP_RATIOS_TTM)
    assert calls[0].url.params["symbol"] == "AAPL"


def test_get_ratios_ttm_empty_returns_none(clock):
    def handler(req):
        return ok([])

    client, _ = make_client(handler, clock)
    assert client.get_ratios_ttm("ZZZZ") is None


def test_get_key_metrics_ttm(clock):
    payload = [
        {
            "symbol": "AAPL",
            "peRatioTTM": 33.84,
            "priceToSalesRatioTTM": 9.12,
            "pegRatioTTM": 5.75,
            "returnOnCapitalEmployedTTM": 0.6503,
            "freeCashFlowTTM": 104_000_000_000,
            "marketCapTTM": 3_200_000_000_000,
        }
    ]

    def handler(req):
        return ok(payload)

    client, calls = make_client(handler, clock)
    result = client.get_key_metrics_ttm("AAPL")

    assert result == payload[0]
    assert calls[0].url.path.endswith(FMP_EP_KEY_METRICS_TTM)
    assert calls[0].url.params["symbol"] == "AAPL"
    assert calls[0].url.params["apikey"] == "test-key"


def test_get_key_metrics_ttm_empty_returns_none(clock):
    def handler(req):
        return ok([])

    client, _ = make_client(handler, clock)
    assert client.get_key_metrics_ttm("ZZZZ") is None


def test_key_metrics_and_ratios_hit_distinct_paths(clock):
    def handler(req):
        return ok([{"symbol": "AAPL"}])

    client, calls = make_client(handler, clock)
    client.get_ratios_ttm("AAPL")
    client.get_key_metrics_ttm("AAPL")

    assert calls[0].url.path.endswith(FMP_EP_RATIOS_TTM)
    assert calls[1].url.path.endswith(FMP_EP_KEY_METRICS_TTM)


# --- rate limit ----------------------------------------------------------

def test_burst_calls_do_not_sleep(clock):
    def handler(req):
        return ok([])

    client, _ = make_client(handler, clock)
    for _ in range(FmpClient.RATE_CAPACITY):
        client.get_ratios_ttm("AAPL")
    assert clock.sleeps == []


def test_call_after_burst_sleeps_until_refill(clock):
    def handler(req):
        return ok([])

    client, _ = make_client(handler, clock)
    for _ in range(FmpClient.RATE_CAPACITY):
        client.get_ratios_ttm("AAPL")
    assert clock.sleeps == []

    client.get_ratios_ttm("AAPL")

    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] == pytest.approx(FmpClient.REFILL_INTERVAL_S, rel=1e-6)


def test_tokens_refill_over_time(clock):
    def handler(req):
        return ok([])

    client, _ = make_client(handler, clock)
    for _ in range(FmpClient.RATE_CAPACITY):
        client.get_ratios_ttm("AAPL")

    clock.now += FmpClient.WINDOW_S  # bucket fully refilled

    for _ in range(FmpClient.RATE_CAPACITY):
        client.get_ratios_ttm("AAPL")

    assert clock.sleeps == []


# --- 429 retry -----------------------------------------------------------

def test_429_retries_once_with_backoff_then_succeeds(clock):
    responses = iter([httpx.Response(429), ok([{"symbol": "AAPL"}])])

    def handler(req):
        return next(responses)

    client, calls = make_client(handler, clock)
    result = client.get_ratios_ttm("AAPL")

    assert result == {"symbol": "AAPL"}
    assert len(calls) == 2
    # one backoff sleep between the two requests
    assert clock.sleeps[-1] == pytest.approx(FmpClient.RETRY_BACKOFF_S, rel=1e-6)


def test_429_twice_raises(clock):
    def handler(req):
        return httpx.Response(429)

    client, calls = make_client(handler, clock)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_ratios_ttm("AAPL")
    assert len(calls) == 2  # original + 1 retry


def test_5xx_does_not_retry(clock):
    call_count = {"n": 0}

    def handler(req):
        call_count["n"] += 1
        return httpx.Response(500)

    client, _ = make_client(handler, clock)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_ratios_ttm("AAPL")
    assert call_count["n"] == 1


# --- F105: screener ------------------------------------------------------

def test_get_company_screener_page_endpoint_and_params(clock):
    def handler(req):
        return ok([{"symbol": "AAPL", "marketCap": 3_000_000_000_000}])

    client, calls = make_client(handler, clock)
    result = client.get_company_screener_page(
        market_cap_gte=50_000_000_000, exchange="NYSE"
    )

    assert result == [{"symbol": "AAPL", "marketCap": 3_000_000_000_000}]
    assert calls[0].url.path.endswith(FMP_EP_SCREENER)
    params = calls[0].url.params
    assert params["marketCapMoreThan"] == "50000000000"
    assert params["exchange"] == "NYSE"
    assert params["limit"] == "500"
    assert params["apikey"] == "test-key"


def test_get_company_screener_page_bool_serialization(clock):
    captured: dict[str, str] = {}

    def handler(req):
        captured.update(req.url.params)
        return ok([])

    client, _ = make_client(handler, clock)
    client.get_company_screener_page(
        market_cap_gte=1, exchange="NYSE", is_etf=False, is_actively_trading=True
    )
    assert captured["isEtf"] == "false"
    assert captured["isActivelyTrading"] == "true"

    captured.clear()
    client.get_company_screener_page(
        market_cap_gte=1, exchange="NYSE", is_etf=True, is_actively_trading=False
    )
    assert captured["isEtf"] == "true"
    assert captured["isActivelyTrading"] == "false"


def test_get_screener_universe_merges_three_exchanges_and_dedupes(clock):
    # Per-exchange payloads: NYSE→[AAPL, MSFT], NASDAQ→[AAPL, GOOG], AMEX→[TSLA]
    responses = iter([
        ok([{"symbol": "AAPL", "exchange": "NYSE"}, {"symbol": "MSFT", "exchange": "NYSE"}]),
        ok([{"symbol": "AAPL", "exchange": "NASDAQ"}, {"symbol": "GOOG", "exchange": "NASDAQ"}]),
        ok([{"symbol": "TSLA", "exchange": "AMEX"}]),
    ])

    def handler(req):
        return next(responses)

    client, calls = make_client(handler, clock)
    result = client.get_screener_universe()

    assert len(calls) == 3
    # first-seen wins → AAPL keeps the NYSE entry
    assert [r["symbol"] for r in result] == ["AAPL", "MSFT", "GOOG", "TSLA"]
    assert result[0]["exchange"] == "NYSE"
    # Each call targets the screener endpoint, one exchange per call
    exchanges_requested = [c.url.params["exchange"] for c in calls]
    assert exchanges_requested == ["NYSE", "NASDAQ", "AMEX"]
    for c in calls:
        assert c.url.path.endswith(FMP_EP_SCREENER)
        assert c.url.params["marketCapMoreThan"] == "50000000000"


def test_get_screener_universe_skips_non_dict_rows(clock):
    # Defensive: if FMP returns unexpected string/None entries, they're skipped.
    responses = iter([
        ok([{"symbol": "AAPL"}, "junk", None]),
        ok([]),
        ok([]),
    ])

    def handler(req):
        return next(responses)

    client, _ = make_client(handler, clock)
    result = client.get_screener_universe()
    assert [r["symbol"] for r in result] == ["AAPL"]


# --- F105: sma -----------------------------------------------------------

def test_get_sma_series_endpoint_and_params(clock):
    def handler(req):
        return ok([{"date": "2026-04-18", "close": 200.0, "sma": 180.0}])

    client, calls = make_client(handler, clock)
    result = client.get_sma_series(
        "AAPL",
        period_length=150,
        from_date="2026-03-14",
        to_date="2026-04-18",
    )

    assert result == [{"date": "2026-04-18", "close": 200.0, "sma": 180.0}]
    assert calls[0].url.path.endswith(FMP_EP_SMA)
    params = calls[0].url.params
    assert params["symbol"] == "AAPL"
    assert params["periodLength"] == "150"
    assert params["timeframe"] == "1day"
    assert params["from"] == "2026-03-14"
    assert params["to"] == "2026-04-18"


def test_get_sma_series_default_window(clock, monkeypatch):
    from datetime import datetime as real_dt, timezone as real_tz

    fixed = real_dt(2026, 4, 18, tzinfo=real_tz.utc)

    class FixedDT(real_dt):
        @classmethod
        def now(cls, tz=None):
            return fixed if tz is None else fixed.astimezone(tz)

    monkeypatch.setattr("app.external.fmp_client.datetime", FixedDT)

    captured: dict[str, str] = {}

    def handler(req):
        captured.update(req.url.params)
        return ok([])

    client, _ = make_client(handler, clock)
    client.get_sma_series("AAPL")

    assert captured["to"] == "2026-04-18"
    assert captured["from"] == "2026-01-18"  # F106: 90 calendar days before (was 35 pre-F106)


def test_get_sma_series_bare_list(clock):
    def handler(req):
        return ok([{"date": "2026-04-18", "sma": 180.0}])

    client, _ = make_client(handler, clock)
    assert client.get_sma_series("AAPL", from_date="2026-03-14", to_date="2026-04-18") == [
        {"date": "2026-04-18", "sma": 180.0}
    ]


def test_get_sma_series_dict_wrapped_payload(clock):
    def handler(req):
        return ok({"symbol": "AAPL", "historical": [{"date": "2026-04-18", "sma": 180.0}]})

    client, _ = make_client(handler, clock)
    assert client.get_sma_series("AAPL", from_date="2026-03-14", to_date="2026-04-18") == [
        {"date": "2026-04-18", "sma": 180.0}
    ]


# --- F105: ma150 fallback ------------------------------------------------

def test_get_ma150_series_or_eod_primary_sma(clock):
    def handler(req):
        assert req.url.path.endswith(FMP_EP_SMA)
        return ok([{"date": "2026-04-18", "close": 200.0, "sma": 180.0}])

    client, calls = make_client(handler, clock)
    result = client.get_ma150_series_or_eod("AAPL")

    assert result["source"] == "sma"
    assert result["bars"] == [{"date": "2026-04-18", "close": 200.0, "sma": 180.0}]
    assert len(calls) == 1


@pytest.mark.parametrize("fallback_status", [402, 403, 404])
def test_get_ma150_series_or_eod_fallback_on_tier_errors(clock, fallback_status):
    responses = iter([
        httpx.Response(fallback_status),
        ok([{"date": "2026-04-18", "close": 200.0}]),
    ])

    def handler(req):
        return next(responses)

    client, calls = make_client(handler, clock)
    result = client.get_ma150_series_or_eod("AAPL")

    assert result["source"] == "eod_fallback"
    assert result["bars"] == [{"date": "2026-04-18", "close": 200.0}]
    assert len(calls) == 2
    assert calls[0].url.path.endswith(FMP_EP_SMA)
    assert calls[1].url.path.endswith(FMP_EP_HIST_EOD)


def test_get_ma150_series_or_eod_no_fallback_on_500(clock):
    # 500 triggers the existing _request behaviour (no retry on 5xx) and must
    # surface rather than mask an upstream outage behind an EOD fallback.
    def handler(req):
        return httpx.Response(500)

    client, calls = make_client(handler, clock)
    with pytest.raises(httpx.HTTPStatusError):
        client.get_ma150_series_or_eod("AAPL")
    assert len(calls) == 1
    assert calls[0].url.path.endswith(FMP_EP_SMA)


# --- F105-a5: shared limiter + concurrency cap --------------------------

def _make_client_with_limiter(
    handler: Callable[[httpx.Request], httpx.Response],
    limiter: _FmpRateLimiter,
) -> tuple[FmpClient, list[httpx.Request]]:
    captured: list[httpx.Request] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        captured.append(request)
        return handler(request)

    transport = httpx.MockTransport(wrapped)
    http = httpx.Client(base_url=FMP_BASE, transport=transport, timeout=10.0)
    return (
        FmpClient(
            api_key="test-key",
            _http_client=http,
            rate_limiter=limiter,
        ),
        captured,
    )


def test_shared_limiter_depletes_across_instances(clock):
    """Two FmpClient instances sharing one limiter deplete the same bucket."""
    limiter = _FmpRateLimiter(time_source=clock.time, sleep=clock.sleep)

    def handler(req):
        return ok([])

    client_a, _ = _make_client_with_limiter(handler, limiter)
    client_b, _ = _make_client_with_limiter(handler, limiter)

    # Client A drains the bucket.
    for _ in range(_FmpRateLimiter.RATE_CAPACITY):
        client_a.get_ratios_ttm("AAPL")
    assert clock.sleeps == []

    # Client B's next call must wait on the shared bucket.
    client_b.get_ratios_ttm("MSFT")
    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] == pytest.approx(
        _FmpRateLimiter.REFILL_INTERVAL_S, rel=1e-6
    )


def test_concurrency_semaphore_caps_inflight_at_limit():
    """Semaphore(CONCURRENCY_LIMIT) blocks the (LIMIT+1)-th concurrent caller."""
    import threading

    limiter = _FmpRateLimiter()
    acquired = threading.Barrier(_FmpRateLimiter.CONCURRENCY_LIMIT + 1, timeout=2.0)
    release_event = threading.Event()
    inflight_peak = {"n": 0}
    inflight_lock = threading.Lock()
    inflight_now = {"n": 0}

    def worker() -> None:
        limiter.acquire_concurrency()
        try:
            with inflight_lock:
                inflight_now["n"] += 1
                if inflight_now["n"] > inflight_peak["n"]:
                    inflight_peak["n"] = inflight_now["n"]
            release_event.wait(timeout=1.5)
        finally:
            with inflight_lock:
                inflight_now["n"] -= 1
            limiter.release_concurrency()

    threads = [
        threading.Thread(target=worker)
        for _ in range(_FmpRateLimiter.CONCURRENCY_LIMIT)
    ]
    for t in threads:
        t.start()

    # Give the N workers a moment to acquire.
    import time as _t

    deadline = _t.monotonic() + 1.0
    while inflight_now["n"] < _FmpRateLimiter.CONCURRENCY_LIMIT and _t.monotonic() < deadline:
        _t.sleep(0.01)

    assert inflight_now["n"] == _FmpRateLimiter.CONCURRENCY_LIMIT

    # Attempting one more must block (non-blocking acquire returns False).
    assert limiter._semaphore.acquire(blocking=False) is False

    release_event.set()
    for t in threads:
        t.join(timeout=2.0)
        assert not t.is_alive()

    assert inflight_peak["n"] == _FmpRateLimiter.CONCURRENCY_LIMIT


def test_semaphore_released_even_on_http_error(clock):
    """_request must release the semaphore on 5xx so future calls aren't blocked."""
    limiter = _FmpRateLimiter(time_source=clock.time, sleep=clock.sleep)

    def handler(req):
        return httpx.Response(500)

    client, _ = _make_client_with_limiter(handler, limiter)

    # Exhaust nothing — just verify that after CONCURRENCY_LIMIT failed calls
    # the semaphore still has capacity available.
    for _ in range(_FmpRateLimiter.CONCURRENCY_LIMIT):
        with pytest.raises(httpx.HTTPStatusError):
            client.get_ratios_ttm("AAPL")

    # If release_concurrency() was skipped, this non-blocking acquire would fail.
    assert limiter._semaphore.acquire(blocking=False) is True
    limiter._semaphore.release()


def test_default_rate_limiter_is_process_singleton():
    from app.external.fmp_client import default_rate_limiter, reset_default_rate_limiter

    reset_default_rate_limiter()
    try:
        a = default_rate_limiter()
        b = default_rate_limiter()
        assert a is b
    finally:
        reset_default_rate_limiter()


# --- deprecated guard ----------------------------------------------------

def test_polygon_client_module_marked_deprecated():
    """Ensure the rollback-anchor module advertises its DEPRECATED status."""
    from app.external import polygon_client

    assert polygon_client.__doc__ is not None
    assert "DEPRECATED" in polygon_client.__doc__
    assert "D034" in polygon_client.__doc__
