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
    # Connectivity check only. Observed 2026-04-19: FMP /stable/ratios-ttm now
    # returns margin/turnover TTM ratios and no longer includes valuation
    # ratios (P/E, P/B, ROE) — those appear to have moved to /stable/key-metrics-ttm.
    # S3 fundamentals integration must account for this when mapping fields.
    ratios = fmp.get_ratios_ttm("AAPL")
    assert ratios is not None, "expected ratios-ttm payload for AAPL"
    assert ratios.get("symbol") == "AAPL"
    assert "grossProfitMarginTTM" in ratios, (
        f"unexpected ratios-ttm shape: {list(ratios.keys())[:10]}"
    )


def _field(obj, name: str):
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
