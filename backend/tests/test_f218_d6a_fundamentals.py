"""F218-d6a tests — T5 数据层: BS+CF client + fundamentals table + supplemental key_metrics + pool_cache 集成.

11 tests / 5 class:
  TestFmpClientBalanceSheetQuarterly ×2
  TestFmpClientCashFlowQuarterly     ×1
  TestComputeFundamentalsRow         ×3
  TestComputeSupplementalKeyMetrics  ×3
  TestFundamentalsRepository         ×1 (comprehensive: upsert + null-not-erase + get_recent)
  TestPoolCacheFundamentalsIntegration ×1
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest


# ─────────────────────────────────────────────────────────────────────────────
# Shared FMP mock helpers
# ─────────────────────────────────────────────────────────────────────────────

def _make_fmp_client(mock_http):
    """Create a FmpClient with a mocked HTTP transport and a fresh rate limiter."""
    from app.external.fmp_client import FmpClient, _FmpRateLimiter
    limiter = _FmpRateLimiter(time_source=lambda: 0.0, sleep=lambda _: None)
    limiter._tokens = float(limiter.RATE_CAPACITY)
    return FmpClient(api_key="test-key", _http_client=mock_http, rate_limiter=limiter)


def _mock_http_ok(payload):
    from unittest.mock import MagicMock
    import httpx
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = 200
    resp.json.return_value = payload
    resp.raise_for_status.return_value = None
    http = MagicMock(spec=httpx.Client)
    http.get.return_value = resp
    return http


def _mock_http_error(status: int = 402):
    from unittest.mock import MagicMock
    import httpx
    req = MagicMock()
    resp = MagicMock(spec=httpx.Response)
    resp.status_code = status
    resp.raise_for_status.side_effect = httpx.HTTPStatusError(
        str(status), request=req, response=resp
    )
    http = MagicMock(spec=httpx.Client)
    http.get.return_value = resp
    return http


# ─────────────────────────────────────────────────────────────────────────────
# TestFmpClientBalanceSheetQuarterly ×2
# ─────────────────────────────────────────────────────────────────────────────

class TestFmpClientBalanceSheetQuarterly:
    """Unit tests (mock httpx) for FmpClient.get_balance_sheet_quarterly."""

    _PAYLOAD = [
        {
            "symbol": "AAPL",
            "date": "2026-03-31",
            "period": "Q2",
            "fiscalYear": "2026",
            "totalDebt": 100_000_000,
            "cashAndShortTermInvestments": 30_000_000,
            "totalStockholdersEquity": 60_000_000,
        }
    ]

    def test_happy_path_returns_list_with_correct_params(self):
        """Success: list returned; params include period=quarter, symbol=AAPL, limit=8."""
        client = _make_fmp_client(_mock_http_ok(self._PAYLOAD))
        result = client.get_balance_sheet_quarterly("AAPL", limit=8)
        assert result == self._PAYLOAD
        from app.external.fmp_client import FMP_EP_BALANCE_SHEET
        # Verify FMP_EP_BALANCE_SHEET constant is correct
        assert FMP_EP_BALANCE_SHEET == "/balance-sheet-statement"
        # Verify params
        call_kwargs = client._http.get.call_args[1]
        params = call_kwargs.get("params", {})
        assert params.get("period") == "quarter"
        assert params.get("limit") == 8
        assert params.get("symbol") == "AAPL"

    def test_http_error_returns_empty_list(self):
        """4xx/5xx → fail-open returns []."""
        client = _make_fmp_client(_mock_http_error(402))
        result = client.get_balance_sheet_quarterly("MSFT", limit=8)
        assert result == []


# ─────────────────────────────────────────────────────────────────────────────
# TestFmpClientCashFlowQuarterly ×1
# ─────────────────────────────────────────────────────────────────────────────

class TestFmpClientCashFlowQuarterly:
    """Unit tests (mock httpx) for FmpClient.get_cash_flow_quarterly."""

    _PAYLOAD = [
        {
            "symbol": "AAPL",
            "date": "2026-03-31",
            "period": "Q2",
            "fiscalYear": "2026",
            "freeCashFlow": 20_000_000,
        }
    ]

    def test_happy_path_returns_list_with_correct_params(self):
        """Success: list returned; params include period=quarter and correct endpoint constant."""
        client = _make_fmp_client(_mock_http_ok(self._PAYLOAD))
        result = client.get_cash_flow_quarterly("AAPL", limit=8)
        assert result == self._PAYLOAD
        from app.external.fmp_client import FMP_EP_CASH_FLOW
        assert FMP_EP_CASH_FLOW == "/cash-flow-statement"
        call_kwargs = client._http.get.call_args[1]
        params = call_kwargs.get("params", {})
        assert params.get("period") == "quarter"
        assert params.get("limit") == 8


# ─────────────────────────────────────────────────────────────────────────────
# Shared test fixtures for pure-function tests
# ─────────────────────────────────────────────────────────────────────────────

_BS_NVDA = {
    "symbol": "NVDA",
    "period": "Q2",
    "fiscalYear": "2026",
    "date": "2026-07-31",
    "totalDebt": 10_000_000_000,
    "cashAndShortTermInvestments": 3_000_000_000,
    "totalStockholdersEquity": 50_000_000_000,
}

_CF_NVDA = {
    "symbol": "NVDA",
    "period": "Q2",
    "fiscalYear": "2026",
    "date": "2026-07-31",
    "freeCashFlow": 8_500_000_000,
}

_IS_NVDA = {
    "symbol": "NVDA",
    "period": "Q2",
    "fiscalYear": "2026",
    "date": "2026-07-31",
    "revenue": 30_000_000_000,
    "netIncome": 16_000_000_000,
}


# ─────────────────────────────────────────────────────────────────────────────
# TestComputeFundamentalsRow ×3
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeFundamentalsRow:
    """Unit tests for compute_fundamentals_row_from_balance_cash pure function."""

    def test_happy_path(self):
        """Happy path: correct field mapping, net_debt, fcf, 8-key output."""
        from app.services.cockpit.pool_helpers import compute_fundamentals_row_from_balance_cash
        row = compute_fundamentals_row_from_balance_cash(_BS_NVDA, _CF_NVDA)
        assert row is not None
        assert row["ticker"] == "NVDA"
        assert row["fiscal_quarter"] == "Q2 2026"
        assert row["period_end_date"] == date(2026, 7, 31)
        assert row["total_debt"] == 10_000_000_000
        assert row["cash"] == 3_000_000_000
        assert row["net_debt"] == 7_000_000_000
        assert row["fcf"] == 8_500_000_000
        assert isinstance(row["fetched_at"], datetime)
        assert set(row.keys()) == {
            "ticker", "fiscal_quarter", "period_end_date",
            "total_debt", "cash", "net_debt", "fcf", "fetched_at",
        }

    @pytest.mark.parametrize("bs_patch,cf_patch,expected_null,expect_none", [
        ({"totalDebt": None}, {}, "net_debt", False),                     # totalDebt null → net_debt null
        ({"cashAndShortTermInvestments": None}, {}, "net_debt", False),   # cash null → net_debt null
        ({}, {"freeCashFlow": None}, "fcf", False),                       # freeCashFlow null → fcf null only
        ({"symbol": "AAPL"}, {}, None, True),                             # symbol mismatch → None
        ({"date": None}, {}, None, True),                                  # missing id field → None
    ])
    def test_null_fields_and_mismatch(self, bs_patch, cf_patch, expected_null, expect_none):
        """Null inputs propagate correctly; id-field mismatch or absence → None."""
        from app.services.cockpit.pool_helpers import compute_fundamentals_row_from_balance_cash
        bs = {**_BS_NVDA, **bs_patch}
        cf = {**_CF_NVDA, **cf_patch}
        row = compute_fundamentals_row_from_balance_cash(bs, cf)
        if expect_none:
            assert row is None
        else:
            assert row is not None
            assert row[expected_null] is None

    def test_missing_id_fields_returns_none(self):
        """If any of symbol/period/fiscalYear/date is absent from BS, return None."""
        from app.services.cockpit.pool_helpers import compute_fundamentals_row_from_balance_cash
        bs_missing = {k: v for k, v in _BS_NVDA.items() if k != "date"}
        result = compute_fundamentals_row_from_balance_cash(bs_missing, _CF_NVDA)
        assert result is None


# ─────────────────────────────────────────────────────────────────────────────
# TestComputeSupplementalKeyMetrics ×3
# ─────────────────────────────────────────────────────────────────────────────

class TestComputeSupplementalKeyMetrics:
    """Unit tests for compute_supplemental_key_metrics_from_is_bs_cf pure function."""

    def test_happy_path(self):
        """Happy path: correct fcf_margin + roic; exactly 5 output keys."""
        from app.services.cockpit.pool_helpers import compute_supplemental_key_metrics_from_is_bs_cf
        row = compute_supplemental_key_metrics_from_is_bs_cf(_IS_NVDA, _BS_NVDA, _CF_NVDA)
        assert row is not None
        assert set(row.keys()) == {"ticker", "fiscal_quarter", "fcf_margin", "roic", "fetched_at"}
        assert row["ticker"] == "NVDA"
        assert row["fiscal_quarter"] == "Q2 2026"
        assert row["fcf_margin"] == pytest.approx(8.5 / 30)
        # roic = 16B / (50B + 10B - 3B) = 16/57
        assert row["roic"] == pytest.approx(16 / 57)
        assert isinstance(row["fetched_at"], datetime)

    def test_roic_denominator_le_zero_returns_null(self):
        """roic denominator ≤ 0 → roic=None (D097 §5, NP-d6a-7)."""
        from app.services.cockpit.pool_helpers import compute_supplemental_key_metrics_from_is_bs_cf
        bs_neg = {**_BS_NVDA, "totalStockholdersEquity": -60_000_000_000}
        row = compute_supplemental_key_metrics_from_is_bs_cf(_IS_NVDA, bs_neg, _CF_NVDA)
        assert row is not None
        assert row["roic"] is None
        # fcf_margin still computable
        assert row["fcf_margin"] == pytest.approx(8.5 / 30)

    def test_fcf_margin_revenue_zero_returns_null(self):
        """revenue=0 → fcf_margin=None; roic may still be computable."""
        from app.services.cockpit.pool_helpers import compute_supplemental_key_metrics_from_is_bs_cf
        is_zero_rev = {**_IS_NVDA, "revenue": 0}
        row = compute_supplemental_key_metrics_from_is_bs_cf(is_zero_rev, _BS_NVDA, _CF_NVDA)
        assert row is not None
        assert row["fcf_margin"] is None
        # roic still computable since netIncome / equity+debt-cash is valid
        assert row["roic"] == pytest.approx(16 / 57)


# ─────────────────────────────────────────────────────────────────────────────
# TestFundamentalsRepository ×1 (comprehensive)
# ─────────────────────────────────────────────────────────────────────────────

class TestFundamentalsRepository:
    """Integration tests (sqlite in-memory) for FundamentalsRepository."""

    def _base_row(self, ticker: str = "NVDA", fiscal_quarter: str = "Q2 2026") -> dict:
        return {
            "ticker": ticker,
            "fiscal_quarter": fiscal_quarter,
            "period_end_date": date(2026, 7, 31),
            "total_debt": 10_000_000_000,
            "cash": 3_000_000_000,
            "net_debt": 7_000_000_000,
            "fcf": 8_500_000_000,
            "fetched_at": datetime(2026, 5, 20, 6, 30, tzinfo=timezone.utc),
        }

    def test_upsert_null_not_erase_and_get_recent(self, db_session):
        """Comprehensive: first insert, null-not-erase update, get_recent ordered DESC."""
        from app.repositories.fundamentals_repository import FundamentalsRepository
        repo = FundamentalsRepository(db_session)

        # First insert: total_debt=10B, fcf=8.5B
        row1 = repo.upsert(self._base_row())
        assert row1.ticker == "NVDA"
        assert row1.total_debt == 10_000_000_000
        assert row1.fcf == 8_500_000_000

        # Second upsert: total_debt=None (should NOT erase), fcf updated to 9B
        row2 = repo.upsert({
            **self._base_row(),
            "total_debt": None,
            "fcf": 9_000_000_000,
        })
        assert row2.total_debt == 10_000_000_000, "null must not erase existing total_debt"
        assert row2.fcf == 9_000_000_000, "non-null fcf must update"

        # Insert a second quarter for get_recent ordering
        repo.upsert({
            **self._base_row(fiscal_quarter="Q1 2026"),
            "period_end_date": date(2026, 3, 31),
        })

        rows = repo.get_recent_for_ticker("NVDA", limit=8)
        assert len(rows) == 2
        assert all(r.ticker == "NVDA" for r in rows)
        assert rows[0].period_end_date >= rows[1].period_end_date, "must be DESC"

        # Different ticker → empty
        assert repo.get_recent_for_ticker("AAPL") == []


# ─────────────────────────────────────────────────────────────────────────────
# Shared stubs for pool_cache integration test
# ─────────────────────────────────────────────────────────────────────────────

def _make_income_record(ticker: str, q: str, fy: str, end: str) -> dict:
    return {
        "symbol": ticker, "period": q, "fiscalYear": fy, "date": end,
        "revenue": 30_000_000_000, "grossProfit": 22_500_000_000,
        "operatingIncome": 18_000_000_000, "netIncome": 16_000_000_000,
    }


def _make_bs_record(ticker: str, q: str, fy: str, end: str) -> dict:
    return {
        "symbol": ticker, "period": q, "fiscalYear": fy, "date": end,
        "totalDebt": 10_000_000_000, "cashAndShortTermInvestments": 3_000_000_000,
        "totalStockholdersEquity": 50_000_000_000,
    }


def _make_cf_record(ticker: str, q: str, fy: str, end: str) -> dict:
    return {
        "symbol": ticker, "period": q, "fiscalYear": fy, "date": end,
        "freeCashFlow": 8_500_000_000,
    }


class _FakeFmpFull:
    """FMP stub providing IS + BS + CF + stubs for cockpit core calls."""

    def __init__(
        self,
        income_by_ticker: dict,
        bs_by_ticker: dict,
        cf_by_ticker: dict,
        empty_bs_tickers: set | None = None,
        empty_cf_tickers: set | None = None,
    ) -> None:
        self._income = income_by_ticker
        self._bs = bs_by_ticker
        self._cf = cf_by_ticker
        self._empty_bs = empty_bs_tickers or set()
        self._empty_cf = empty_cf_tickers or set()

    def get_income_statement_quarterly(self, symbol: str, limit: int = 8) -> list[dict]:
        return self._income.get(symbol, [])

    def get_balance_sheet_quarterly(self, symbol: str, limit: int = 8) -> list[dict]:
        if symbol in self._empty_bs:
            return []
        return self._bs.get(symbol, [])

    def get_cash_flow_quarterly(self, symbol: str, limit: int = 8) -> list[dict]:
        if symbol in self._empty_cf:
            return []
        return self._cf.get(symbol, [])

    def get_daily_bars(self, *args, **kwargs) -> list:
        return []

    def get_financial_growth(self, symbol: str):
        return None


class _FakeBreakoutRepo:
    def __init__(self, tickers: list[str]) -> None:
        class Item:
            def __init__(self, t): self.ticker = t
        class Snapshot:
            def __init__(self, ts): self.items = [Item(t) for t in ts]
        self._snapshot = Snapshot(tickers)

    def get_latest_snapshot(self):
        return self._snapshot


# ─────────────────────────────────────────────────────────────────────────────
# TestPoolCacheFundamentalsIntegration ×1
# ─────────────────────────────────────────────────────────────────────────────

class TestPoolCacheFundamentalsIntegration:
    """End-to-end integration: mock IS/BS/CF → 2 tables written + no regression."""

    def test_rebuild_writes_both_tables_and_logs(self, db_session):
        """Full rebuild():
        - 2 tickers × 2 quarters → 4 fundamentals rows + 4 supplemental km rows (fcf_margin+roic)
        - 1 ticker BS=[] → no fundamentals for that ticker, no regression
        - d3a-written gross/op/net margins preserved (null-not-erase)
        - system_logs contain 3 OK entries (cockpit / key_metrics / fundamentals)
        """
        from sqlalchemy import select
        from app.models.system_log import SystemLog
        from app.repositories.fundamentals_repository import FundamentalsRepository
        from app.repositories.key_metrics_repository import KeyMetricsRepository
        from app.services.cockpit.pool_cache_service import PoolCacheService

        quarters = [("Q1", "2026", "2026-04-30"), ("Q2", "2026", "2026-07-31")]
        tickers = ["NVDA", "AAPL", "SKIP"]

        income_by_ticker = {
            t: [_make_income_record(t, q, fy, end) for q, fy, end in quarters]
            for t in tickers
        }
        bs_by_ticker = {
            t: [_make_bs_record(t, q, fy, end) for q, fy, end in quarters]
            for t in tickers
        }
        cf_by_ticker = {
            t: [_make_cf_record(t, q, fy, end) for q, fy, end in quarters]
            for t in tickers
        }

        # SKIP ticker has no BS → its fundamentals should not be written
        fmp = _FakeFmpFull(income_by_ticker, bs_by_ticker, cf_by_ticker, empty_bs_tickers={"SKIP"})
        svc = PoolCacheService(db_session, fmp)
        svc._breakout_repo = _FakeBreakoutRepo(tickers)

        result = svc.rebuild()
        assert result.status == "ok"

        # fundamentals: NVDA×2 + AAPL×2 = 4; SKIP skipped
        fund_repo = FundamentalsRepository(db_session)
        assert len(fund_repo.get_recent_for_ticker("NVDA")) == 2
        assert len(fund_repo.get_recent_for_ticker("AAPL")) == 2
        assert fund_repo.get_recent_for_ticker("SKIP") == []

        # key_metrics: IS rows (3 tickers × 2q = 6) + supplemental km (2 tickers × 2q = 4)
        # merged via null-not-erase → 6 unique rows (SKIP gets IS-only rows, NVDA+AAPL get all fields)
        km_repo = KeyMetricsRepository(db_session)
        nvda_km = km_repo.get_recent_for_ticker("NVDA")
        assert len(nvda_km) == 2
        # d3a-style gross_margin written from IS; d6a supplemental adds fcf_margin+roic
        for km_row in nvda_km:
            assert km_row.gross_margin == pytest.approx(22_500_000_000 / 30_000_000_000)
            assert km_row.fcf_margin == pytest.approx(8.5 / 30)
            assert km_row.roic == pytest.approx(16 / 57)
        # SKIP ticker: only IS rows, no fcf_margin/roic (BS was empty → supplemental skipped)
        skip_km = km_repo.get_recent_for_ticker("SKIP")
        assert len(skip_km) == 2
        for km_row in skip_km:
            assert km_row.fcf_margin is None
            assert km_row.roic is None

        # system_logs: 3 OK entries
        logs = db_session.execute(select(SystemLog)).scalars().all()
        messages = [l.message for l in logs if l.level == "OK"]
        assert any("rebuilt" in m for m in messages), "cockpit rebuild log missing"
        assert any("key_metrics upserted" in m for m in messages), "key_metrics log missing"
        assert any("fundamentals upserted" in m for m in messages), "fundamentals log missing"

        # fundamentals data sanity spot-check
        nvda_fund = fund_repo.get_recent_for_ticker("NVDA")
        for f in nvda_fund:
            assert f.total_debt == 10_000_000_000
            assert f.cash == 3_000_000_000
            assert f.net_debt == 7_000_000_000
            assert f.fcf == 8_500_000_000
