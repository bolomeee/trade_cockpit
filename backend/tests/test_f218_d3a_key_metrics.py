"""F218-d3a tests — T2 数据层: income-statement client + key_metrics 表 + pool_cache 集成.

Build order (wip commits):
  Step 1: TestFmpClientIncomeStatementQuarterly (×2)
  Step 2: (no new tests — ORM model verification via import)
  Step 3: (no new tests — alembic migration verified via CLI)
  Step 4: TestKeyMetricsRepository (×3)
  Step 5: TestComputeKeyMetricsRow (×3)
  Step 6: TestPoolCacheKeyMetricsIntegration (×2)
"""
from __future__ import annotations

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Step 1: FMP client — get_income_statement_quarterly
# ─────────────────────────────────────────────────────────────────────────────

class TestFmpClientIncomeStatementQuarterly:
    """Unit tests (mock httpx) for FmpClient.get_income_statement_quarterly."""

    def _make_client(self, mock_http):
        """Create a FmpClient with a mocked HTTP transport and a fresh rate limiter."""
        from app.external.fmp_client import FmpClient, _FmpRateLimiter
        limiter = _FmpRateLimiter(
            time_source=lambda: 0.0,
            sleep=lambda _: None,
        )
        # Pre-fill tokens so rate limiter never blocks
        limiter._tokens = float(limiter.RATE_CAPACITY)
        return FmpClient(
            api_key="test-key",
            _http_client=mock_http,
            rate_limiter=limiter,
        )

    def test_happy_path_returns_raw_list(self):
        """Successful response: returns list of dicts, params contain period=quarter & limit=8."""
        from unittest.mock import MagicMock
        import httpx

        payload = [
            {
                "symbol": "AAPL",
                "date": "2026-03-31",
                "period": "Q2",
                "fiscalYear": "2026",
                "revenue": 100_000,
                "grossProfit": 40_000,
                "operatingIncome": 25_000,
                "netIncome": 20_000,
            }
        ]

        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 200
        mock_response.json.return_value = payload
        mock_response.raise_for_status.return_value = None

        mock_http = MagicMock(spec=httpx.Client)
        mock_http.get.return_value = mock_response

        client = self._make_client(mock_http)
        result = client.get_income_statement_quarterly("AAPL", limit=8)

        assert result == payload

        call_args = mock_http.get.call_args
        params_sent = call_args[1]["params"] if "params" in call_args[1] else call_args[0][1]
        assert params_sent.get("period") == "quarter"
        assert params_sent.get("limit") == 8
        assert params_sent.get("symbol") == "AAPL"

    def test_http_error_returns_empty_list(self):
        """4xx/5xx or network error → fail-open returns []."""
        from unittest.mock import MagicMock
        import httpx

        mock_request = MagicMock()
        mock_response = MagicMock(spec=httpx.Response)
        mock_response.status_code = 402
        mock_response.raise_for_status.side_effect = httpx.HTTPStatusError(
            "402", request=mock_request, response=mock_response
        )

        mock_http = MagicMock(spec=httpx.Client)
        mock_http.get.return_value = mock_response

        client = self._make_client(mock_http)
        result = client.get_income_statement_quarterly("MSFT", limit=8)

        assert result == []
