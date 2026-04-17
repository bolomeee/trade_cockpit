"""Unit tests for PolygonClient wrapper.

Covers:
  - missing API key raises RuntimeError
  - each wrapper method forwards args correctly
  - token-bucket rate limiter blocks the 6th call within the 60s window
"""
from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest

from app.external.polygon_client import PolygonClient


@pytest.fixture
def fake_rest_client():
    """Patch massive.RESTClient inside the polygon_client module."""
    with patch("app.external.polygon_client.RESTClient") as m:
        instance = MagicMock()
        m.return_value = instance
        yield instance


class FakeClock:
    """Deterministic monotonic clock + sleep recorder."""

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


def make_client(fake_rest_client, clock: FakeClock, api_key: str = "test-key") -> PolygonClient:
    return PolygonClient(api_key=api_key, _time_source=clock.time, _sleep=clock.sleep)


# --- missing key ---------------------------------------------------------

def test_missing_api_key_raises(monkeypatch):
    monkeypatch.setattr("app.external.polygon_client.settings.polygon_api_key", "")
    with pytest.raises(RuntimeError, match="POLYGON_API_KEY not set"):
        PolygonClient()


def test_explicit_empty_key_raises():
    with pytest.raises(RuntimeError, match="POLYGON_API_KEY not set"):
        PolygonClient(api_key="")


# --- method forwarding ---------------------------------------------------

def test_search_tickers_forwards_args(fake_rest_client, clock):
    fake_rest_client.list_tickers.return_value = iter([{"ticker": "AAPL"}])

    pc = make_client(fake_rest_client, clock)
    result = pc.search_tickers("AAPL", limit=5)

    fake_rest_client.list_tickers.assert_called_once_with(
        search="AAPL",
        market="stocks",
        active=True,
        limit=5,
    )
    assert result == [{"ticker": "AAPL"}]


def test_get_previous_close_forwards_args(fake_rest_client, clock):
    fake_rest_client.get_previous_close_agg.return_value = {"close": 150.0}

    pc = make_client(fake_rest_client, clock)
    result = pc.get_previous_close("AAPL")

    fake_rest_client.get_previous_close_agg.assert_called_once_with(
        ticker="AAPL", adjusted=True
    )
    assert result == {"close": 150.0}


def test_get_daily_aggs_forwards_args(fake_rest_client, clock):
    fake_rest_client.list_aggs.return_value = iter([{"c": 100.0}, {"c": 101.0}])

    pc = make_client(fake_rest_client, clock)
    result = pc.get_daily_aggs("AAPL", "2026-01-01", "2026-04-17")

    fake_rest_client.list_aggs.assert_called_once_with(
        ticker="AAPL",
        multiplier=1,
        timespan="day",
        from_="2026-01-01",
        to="2026-04-17",
        adjusted=True,
    )
    assert result == [{"c": 100.0}, {"c": 101.0}]


# --- rate limit ----------------------------------------------------------

def test_first_five_calls_do_not_sleep(fake_rest_client, clock):
    fake_rest_client.get_previous_close_agg.return_value = None
    pc = make_client(fake_rest_client, clock)

    for _ in range(PolygonClient.RATE_CAPACITY):
        pc.get_previous_close("AAPL")

    assert clock.sleeps == []


def test_sixth_call_within_window_sleeps_until_refill(fake_rest_client, clock):
    fake_rest_client.get_previous_close_agg.return_value = None
    pc = make_client(fake_rest_client, clock)

    for _ in range(PolygonClient.RATE_CAPACITY):
        pc.get_previous_close("AAPL")
    assert clock.sleeps == []

    pc.get_previous_close("AAPL")

    assert len(clock.sleeps) == 1
    assert clock.sleeps[0] == pytest.approx(PolygonClient.REFILL_INTERVAL_S, rel=1e-6)


def test_tokens_refill_over_time(fake_rest_client, clock):
    fake_rest_client.get_previous_close_agg.return_value = None
    pc = make_client(fake_rest_client, clock)

    for _ in range(PolygonClient.RATE_CAPACITY):
        pc.get_previous_close("AAPL")

    clock.now += PolygonClient.WINDOW_S  # full window elapsed → bucket full again

    for _ in range(PolygonClient.RATE_CAPACITY):
        pc.get_previous_close("AAPL")

    assert clock.sleeps == []
