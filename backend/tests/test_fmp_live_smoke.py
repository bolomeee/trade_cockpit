"""Live smoke tests against the real FMP /stable/ API (D034).

Opt-in only: these tests hit financialmodelingprep.com and consume the
configured rate budget. Run with `uv run pytest -m live` and a real
`FMP_API_KEY` in the environment. Skipped silently when the key is absent
so CI default pipelines stay hermetic.
"""
from __future__ import annotations

import os
from datetime import date, timedelta

import pytest

from app.external.fmp_client import FmpClient

pytestmark = [
    pytest.mark.live,
    pytest.mark.skipif(
        not os.getenv("FMP_API_KEY"),
        reason="FMP_API_KEY not set; live smoke tests skipped",
    ),
]


@pytest.fixture(scope="module")
def fmp() -> FmpClient:
    return FmpClient()


def test_live_search_symbol_aapl(fmp: FmpClient) -> None:
    results = fmp.search_tickers("AAPL", limit=5)
    assert results, "expected non-empty search results for AAPL"
    symbols = {_field(r, "symbol") for r in results}
    assert "AAPL" in symbols


def test_live_search_name_fallback_microsoft(fmp: FmpClient) -> None:
    # "Microsoft" is not a symbol prefix (MSFT), so /search-symbol returns [];
    # the two-phase fallback in search_tickers should hit /search-name next.
    results = fmp.search_tickers("Microsoft", limit=5)
    assert results, "expected non-empty fallback results for 'Microsoft'"
    symbols = {_field(r, "symbol") for r in results}
    assert "MSFT" in symbols


def test_live_daily_bars_aapl_recent(fmp: FmpClient) -> None:
    today = date.today()
    bars = fmp.get_daily_bars("AAPL", today - timedelta(days=30), today)
    assert bars, "expected at least one EOD bar for AAPL in the last 30 days"
    first = bars[0]
    for field in ("date", "open", "high", "low", "close", "volume"):
        assert _field(first, field) is not None, f"bar missing {field}: {first}"


def test_live_index_recent_bars_gspc(fmp: FmpClient) -> None:
    bars = fmp.get_index_recent_bars("^GSPC", days=10)
    assert bars, "expected non-empty ^GSPC bars"
    assert _field(bars[0], "close") is not None


def test_live_treasury_10y(fmp: FmpClient) -> None:
    data = fmp.get_treasury_10y_latest()
    assert set(("date", "year10", "prev_date", "prev_year10")).issubset(data.keys())
    assert isinstance(data["year10"], (int, float))
    assert data["year10"] > 0


def test_live_ratios_ttm_aapl(fmp: FmpClient) -> None:
    # D036: /stable/ratios-ttm is the source of PE / PS / PEG. Also carries
    # margin/turnover ratios. Assert the valuation fields S3 actually consumes.
    ratios = fmp.get_ratios_ttm("AAPL")
    assert ratios is not None, "expected ratios-ttm payload for AAPL"
    assert ratios.get("symbol") == "AAPL"
    for field in (
        "priceToEarningsRatioTTM",
        "priceToSalesRatioTTM",
        "priceToEarningsGrowthRatioTTM",
    ):
        assert field in ratios, (
            f"ratios-ttm missing {field}; keys sample: {list(ratios.keys())[:15]}"
        )


def test_live_key_metrics_ttm_aapl(fmp: FmpClient) -> None:
    # D036: /stable/key-metrics-ttm is the source of marketCap / ROCE / FCF yield.
    # FCF absolute = marketCap * freeCashFlowYieldTTM (no direct FCF field exists).
    metrics = fmp.get_key_metrics_ttm("AAPL")
    assert metrics is not None, "expected key-metrics-ttm payload for AAPL"
    assert metrics.get("symbol") == "AAPL"
    for field in ("marketCap", "returnOnCapitalEmployedTTM", "freeCashFlowYieldTTM"):
        assert field in metrics, (
            f"key-metrics-ttm missing {field}; keys sample: {list(metrics.keys())[:15]}"
        )


def test_live_screener_large_caps(fmp: FmpClient) -> None:
    # F105 (D038): universe = NYSE/NASDAQ/AMEX actively-traded, marketCap >= 50B.
    # Smoke asserts the merged response is non-trivial and the market-cap floor
    # holds for every returned row.
    universe = fmp.get_screener_universe()
    assert len(universe) >= 50, f"expected >=50 large-cap rows, got {len(universe)}"
    for row in universe[:10]:
        for field in ("symbol", "companyName", "exchange", "marketCap"):
            assert _field(row, field) is not None, f"screener row missing {field}: {row}"
    # Floor check on every row (lenient: FMP's floor is inclusive, we requested > 50B).
    assert all(float(_field(r, "marketCap") or 0) >= 50_000_000_000 for r in universe)


def test_live_sma_or_eod_fallback_aapl(fmp: FmpClient) -> None:
    # F105 (D039): SMA endpoint is the primary path. If Starter tier does not
    # cover it (402/403/404), get_ma150_series_or_eod transparently falls back
    # to EOD — both outcomes are acceptable for this feature.
    result = fmp.get_ma150_series_or_eod("AAPL")
    assert result["source"] in ("sma", "eod_fallback")
    bars = result["bars"]
    assert bars, f"expected non-empty bars, source={result['source']}"
    if result["source"] == "sma":
        # Each SMA row carries its own sma value; window is ~25 trading days.
        assert len(bars) >= 15, f"SMA series unexpectedly short: {len(bars)}"
        assert _field(bars[0], "sma") is not None
        assert _field(bars[0], "close") is not None
    else:
        # EOD fallback window is 260 calendar days → ≥180 trading days expected.
        assert len(bars) >= 180, f"EOD fallback series too short: {len(bars)}"
        for field in ("date", "open", "high", "low", "close", "volume"):
            assert _field(bars[0], field) is not None, f"EOD bar missing {field}"


def _field(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
