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

from datetime import date, datetime, timezone

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


# ─────────────────────────────────────────────────────────────────────────────
# Step 4: KeyMetricsRepository — upsert / null-not-erase / get_recent
# ─────────────────────────────────────────────────────────────────────────────

class TestKeyMetricsRepository:
    """Unit tests (sqlite in-memory via db_session fixture) for KeyMetricsRepository."""

    def _base_row(self, ticker: str = "NVDA", fiscal_quarter: str = "Q2 2026") -> dict:
        return {
            "ticker": ticker,
            "fiscal_quarter": fiscal_quarter,
            "period_end_date": date(2026, 7, 31),
            "gross_margin": 0.75,
            "op_margin": 0.60,
            "net_margin": 0.533,
            "fcf_margin": None,
            "roic": None,
            "fetched_at": datetime(2026, 5, 19, 6, 30, tzinfo=timezone.utc),
        }

    def test_upsert_happy_path(self, db_session):
        """First insert creates row; second upsert with changed gross_margin overwrites."""
        from app.repositories.key_metrics_repository import KeyMetricsRepository

        repo = KeyMetricsRepository(db_session)
        row = repo.upsert(self._base_row())
        assert row.ticker == "NVDA"
        assert row.fiscal_quarter == "Q2 2026"
        assert row.gross_margin == pytest.approx(0.75)

        updated = repo.upsert({**self._base_row(), "gross_margin": 0.80})
        assert updated.gross_margin == pytest.approx(0.80)
        assert updated.op_margin == pytest.approx(0.60)

    def test_upsert_null_not_erase(self, db_session):
        """null-not-erase: second upsert with gross_margin=None keeps existing value;
        non-null fcf_margin in second upsert fills the previously-null column."""
        from app.repositories.key_metrics_repository import KeyMetricsRepository

        repo = KeyMetricsRepository(db_session)
        repo.upsert(self._base_row())  # gross_margin=0.75, fcf_margin=None

        row2 = repo.upsert({
            **self._base_row(),
            "gross_margin": None,   # should NOT overwrite 0.75
            "fcf_margin": 0.18,     # should fill in
        })
        assert row2.gross_margin == pytest.approx(0.75), "existing gross_margin must be preserved"
        assert row2.fcf_margin == pytest.approx(0.18), "new fcf_margin must be written"

    def test_get_recent_for_ticker(self, db_session):
        """Returns rows for the correct ticker only, ordered by period_end_date DESC, limited."""
        from app.repositories.key_metrics_repository import KeyMetricsRepository

        repo = KeyMetricsRepository(db_session)
        for q, end in [("Q1 2026", date(2026, 3, 31)), ("Q2 2026", date(2026, 6, 30))]:
            repo.upsert({**self._base_row(ticker="NVDA", fiscal_quarter=q), "period_end_date": end})
        repo.upsert({**self._base_row(ticker="AAPL", fiscal_quarter="Q1 2026"), "period_end_date": date(2026, 3, 31)})

        rows = repo.get_recent_for_ticker("NVDA", limit=4)
        assert len(rows) == 2
        assert all(r.ticker == "NVDA" for r in rows)
        assert rows[0].period_end_date >= rows[1].period_end_date, "should be DESC"

        empty = repo.get_recent_for_ticker("TSLA", limit=4)
        assert empty == []


# ─────────────────────────────────────────────────────────────────────────────
# Step 5: compute_key_metrics_row_from_income_statement — pure function
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeKeyMetricsRow:
    """Unit tests for the pool_helpers pure function."""

    _HAPPY_PAYLOAD = {
        "symbol": "NVDA",
        "period": "Q2",
        "fiscalYear": "2026",
        "date": "2026-07-31",
        "revenue": 30_000,
        "grossProfit": 22_500,
        "operatingIncome": 18_000,
        "netIncome": 16_000,
    }

    def test_happy_path(self):
        """Happy path: correct margins, fiscal_quarter, period_end_date, exact key set."""
        from app.services.cockpit.pool_helpers import compute_key_metrics_row_from_income_statement

        result = compute_key_metrics_row_from_income_statement(self._HAPPY_PAYLOAD)

        assert result is not None
        assert result["ticker"] == "NVDA"
        assert result["fiscal_quarter"] == "Q2 2026"
        assert result["period_end_date"] == date(2026, 7, 31)
        assert result["gross_margin"] == pytest.approx(0.75)
        assert result["op_margin"] == pytest.approx(0.60)
        assert result["net_margin"] == pytest.approx(16_000 / 30_000)
        assert isinstance(result["fetched_at"], datetime)
        assert set(result.keys()) == {
            "ticker", "fiscal_quarter", "period_end_date",
            "gross_margin", "op_margin", "net_margin", "fetched_at",
        }, "must not include fcf_margin or roic"

    @pytest.mark.parametrize("patch,expected_nulls,expect_none", [
        ({"revenue": 0}, {"gross_margin", "op_margin", "net_margin"}, False),
        ({"grossProfit": None}, {"gross_margin"}, False),
        ({"revenue": None}, {"gross_margin", "op_margin", "net_margin"}, False),
        ({"symbol": None}, set(), True),
    ])
    def test_null_and_zero_safety(self, patch, expected_nulls, expect_none):
        """revenue=0 / field=None → margin=None; missing id fields → returns None."""
        from app.services.cockpit.pool_helpers import compute_key_metrics_row_from_income_statement

        payload = {**self._HAPPY_PAYLOAD, **patch}
        result = compute_key_metrics_row_from_income_statement(payload)

        if expect_none:
            assert result is None
            return

        assert result is not None
        for key in expected_nulls:
            assert result[key] is None, f"{key} should be None"
        for key in {"gross_margin", "op_margin", "net_margin"} - expected_nulls:
            assert result[key] is not None, f"{key} should be non-None"


# ─────────────────────────────────────────────────────────────────────────────
# Step 6: PoolCacheService — _rebuild_key_metrics integration
# ─────────────────────────────────────────────────────────────────────────────

def _make_income_record(ticker: str, q: str, fy: str, end: str) -> dict:
    """Minimal valid FMP income-statement record."""
    return {
        "symbol": ticker,
        "period": q,
        "fiscalYear": fy,
        "date": end,
        "revenue": 10_000,
        "grossProfit": 7_500,
        "operatingIncome": 5_000,
        "netIncome": 4_000,
    }


class _FakeFmpForKeyMetrics:
    """Minimal FMP stub for PoolCacheService integration tests."""

    def __init__(self, income_by_ticker: dict, error_tickers: set | None = None) -> None:
        self._income = income_by_ticker
        self._errors = error_tickers or set()

    def get_income_statement_quarterly(self, symbol: str, limit: int = 8) -> list[dict]:
        if symbol in self._errors:
            import httpx
            raise httpx.HTTPStatusError(
                "402", request=object(), response=object()  # type: ignore[arg-type]
            )
        return self._income.get(symbol, [])

    # Pool cache core calls — return empty to skip cockpit path
    def get_daily_bars(self, *args, **kwargs) -> list:
        return []

    def get_financial_growth(self, symbol: str):
        return None


class _FakeBreakoutRepo:
    """Returns a fake snapshot with a pre-set ticker list."""

    def __init__(self, tickers: list[str]) -> None:
        class Item:
            def __init__(self, t): self.ticker = t
        class Snapshot:
            def __init__(self, ts): self.items = [Item(t) for t in ts]
        self._snapshot = Snapshot(tickers)

    def get_latest_snapshot(self):
        return self._snapshot


class TestPoolCacheKeyMetricsIntegration:
    """Integration tests for PoolCacheService._rebuild_key_metrics."""

    def _make_service(self, db_session, fmp, tickers: list[str]):
        from app.services.cockpit.pool_cache_service import PoolCacheService
        svc = PoolCacheService(db_session, fmp)
        svc._breakout_repo = _FakeBreakoutRepo(tickers)
        return svc

    def test_rebuild_key_metrics_upserts_successful_tickers(self, db_session):
        """2 tickers × 2 quarters each → 4 rows upserted; failed ticker doesn't block."""
        from app.repositories.key_metrics_repository import KeyMetricsRepository

        income = {
            "NVDA": [
                _make_income_record("NVDA", "Q1", "2026", "2026-04-30"),
                _make_income_record("NVDA", "Q2", "2026", "2026-07-31"),
            ],
            "AAPL": [
                _make_income_record("AAPL", "Q1", "2026", "2026-03-31"),
                _make_income_record("AAPL", "Q2", "2026", "2026-06-30"),
            ],
            "FAIL": [],  # returns empty → zero upserts for this ticker
        }
        fmp = _FakeFmpForKeyMetrics(income, error_tickers={"ERR"})
        svc = self._make_service(db_session, fmp, ["NVDA", "AAPL", "FAIL", "ERR"])

        count = svc._rebuild_key_metrics(["NVDA", "AAPL", "FAIL", "ERR"])

        assert count == 4, f"expected 4 upserted rows, got {count}"
        repo = KeyMetricsRepository(db_session)
        assert len(repo.get_recent_for_ticker("NVDA")) == 2
        assert len(repo.get_recent_for_ticker("AAPL")) == 2
        assert repo.get_recent_for_ticker("FAIL") == []
        assert repo.get_recent_for_ticker("ERR") == []

    def test_rebuild_does_not_affect_cockpit_pool_cache(self, db_session):
        """Full rebuild(): cockpit_pool_cache rows unaffected + key_metrics rows written
        + system_logs contain both rebuilt and key_metrics log entries."""
        from sqlalchemy import select
        from app.models.cockpit_pool_cache import CockpitPoolCache
        from app.models.system_log import SystemLog
        from app.services.cockpit.pool_cache_service import PoolCacheService

        income = {
            "MSFT": [_make_income_record("MSFT", "Q1", "2026", "2026-03-31")],
        }
        fmp = _FakeFmpForKeyMetrics(income)
        svc = PoolCacheService(db_session, fmp)
        svc._breakout_repo = _FakeBreakoutRepo(["MSFT"])

        result = svc.rebuild()

        assert result.status == "ok"
        # cockpit_pool_cache: MSFT has no bars → 0 rows (consistent with existing behavior)
        pool_rows = db_session.execute(select(CockpitPoolCache)).scalars().all()
        assert len(pool_rows) == 0  # no bars → no cockpit row

        # key_metrics: 1 row written
        from app.repositories.key_metrics_repository import KeyMetricsRepository
        km_rows = KeyMetricsRepository(db_session).get_recent_for_ticker("MSFT")
        assert len(km_rows) == 1
        assert km_rows[0].gross_margin == pytest.approx(0.75)

        # system_logs: must have both OK entries
        logs = db_session.execute(select(SystemLog)).scalars().all()
        messages = [l.message for l in logs]
        assert any("rebuilt" in m for m in messages), "should have cockpit rebuild log"
        assert any("key_metrics upserted" in m for m in messages), "should have key_metrics log"
