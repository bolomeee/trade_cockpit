"""Tests for F203-a CockpitChart 数据层 + 接入层.

Sprint Contract 标准 S1–S15:
  S1.  _compute_ma_series period=10, closes=15 bars → 6 points (前 9 bar 不输出)
  S2.  _compute_ma_series period >= len(bars) → []
  S3.  _compute_atr_series 已知 OHLC → Wilder ATR 三位小数吻合
  S4.  _compute_avwap_series anchor=bars[0].date → len=bars, first=typical_price[0]
  S5.  _compute_avwap_series anchor 晚于 bars[-1] → []
  S6.  _compute_avwap_series anchor 早于 bars[0] → 等同 anchor=bars[0]
  S7.  _resolve_anchor: explicit / earnings / none 三 case
  S8.  CockpitChartService.get_chart 集成（250 bars + earnings → response 结构正确）
  S9.  service mas=[5,250] → 2 key; mas=[5] → 1 key; mas=[] → {}
  S10. router GET /api/cockpit/chart/NVDA 默认参数 → 200, mas keys=[10,21,50,150,200]
  S11. router ?mas=10,500 → 422 (500 > MA_MAX)
  S12. router ?days=50 → 422 (< MIN_DAYS)
  S13. router ?anchor=not-a-date → 422
  S14. ticker 不在 DB 且 FMP miss → 404
  S15. 全量回归（在 CI 运行，单独文件 not included here）
"""
from __future__ import annotations

import pytest
from datetime import date, datetime, timezone, timedelta
from typing import Any

from app.models.stock import Stock
from app.models.daily_bar import DailyBar
from app.models.earnings_event import EarningsEvent
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.services.cockpit.chart_service import (
    CockpitChartService,
    _compute_ma_series,
    _compute_atr_series,
    _compute_avwap_series,
    _resolve_anchor,
)


# ── Helpers ───────────────────────────────────────────────────────────────────


def _make_bar(i: int, close: float = 100.0) -> dict[str, Any]:
    return {
        "date": date(2024, 1, 1) + timedelta(days=i),
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": 1_000_000,
    }


def _seed_stock_with_bars(db, ticker: str, n_bars: int, end_date: date | None = None) -> Stock:
    """Seed stock + bars ending at end_date (default: today)."""
    if end_date is None:
        end_date = date.today()
    stock = Stock(
        ticker=ticker,
        name=f"{ticker} Corp",
        is_active=True,
        added_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.flush()
    start_date = end_date - timedelta(days=n_bars - 1)
    for i in range(n_bars):
        bar = DailyBar(
            stock_id=stock.id,
            date=start_date + timedelta(days=i),
            open=100.0,
            high=102.0,
            low=98.0,
            close=100.0 + i * 0.01,
            volume=1_000_000,
        )
        db.add(bar)
    db.commit()
    return stock


# ── S1–S2: _compute_ma_series ─────────────────────────────────────────────────


class TestComputeMaSeries:
    def test_s1_period_10_length_15_returns_6_points(self):
        bars = [_make_bar(i, close=float(100 + i)) for i in range(15)]
        result = _compute_ma_series(bars, 10)
        assert len(result) == 6  # bars 9..14
        # First point: SMA of bars 0..9
        expected_first = sum(100.0 + i for i in range(10)) / 10
        assert abs(result[0]["value"] - expected_first) < 1e-9
        assert result[0]["date"] == bars[9]["date"]

    def test_s2_period_gte_length_returns_empty(self):
        bars = [_make_bar(i) for i in range(10)]
        assert _compute_ma_series(bars, 10) == []
        assert _compute_ma_series(bars, 15) == []
        assert _compute_ma_series(bars, 0) == []


# ── S3: _compute_atr_series ───────────────────────────────────────────────────


class TestComputeAtrSeries:
    def test_s3_wilder_atr_matches_hand_calc(self):
        d = [date(2024, 1, 1) + timedelta(days=i) for i in range(4)]
        bars = [
            {"date": d[0], "open": 9, "high": 10, "low": 8, "close": 9, "volume": 1},
            {"date": d[1], "open": 9, "high": 11, "low": 9, "close": 10, "volume": 1},
            {"date": d[2], "open": 10, "high": 13, "low": 8, "close": 11, "volume": 1},
            {"date": d[3], "open": 11, "high": 12, "low": 10, "close": 11, "volume": 1},
        ]
        # period=2:
        # TR1 = max(11-9, |11-9|, |9-9|)  = 2
        # TR2 = max(13-8, |13-10|, |8-10|) = 5
        # TR3 = max(12-10,|12-11|,|10-11|) = 2
        # seed = (2+5)/2 = 3.5, date=d[2]
        # ATR  = (3.5*1+2)/2 = 2.75, date=d[3]
        result = _compute_atr_series(bars, period=2)
        assert len(result) == 2
        assert result[0]["date"] == d[2]
        assert round(result[0]["value"], 3) == 3.500
        assert result[1]["date"] == d[3]
        assert round(result[1]["value"], 3) == 2.750


# ── S4–S6: _compute_avwap_series ─────────────────────────────────────────────


class TestComputeAvwapSeries:
    def _bars(self, n: int = 5) -> list[dict[str, Any]]:
        return [
            {
                "date": date(2024, 1, 1) + timedelta(days=i),
                "open": 100.0,
                "high": 102.0,
                "low": 98.0,
                "close": 100.0,
                "volume": 1_000_000,
            }
            for i in range(n)
        ]

    def test_s4_anchor_at_first_bar(self):
        bars = self._bars(5)
        result = _compute_avwap_series(bars, anchor=bars[0]["date"])
        assert len(result) == 5
        # First value = typical_price = (102+98+100)/3 = 100.0
        assert abs(result[0]["value"] - 100.0) < 1e-6
        assert result[0]["date"] == bars[0]["date"]

    def test_s5_anchor_after_last_bar_returns_empty(self):
        bars = self._bars(5)
        after = bars[-1]["date"] + timedelta(days=1)
        assert _compute_avwap_series(bars, anchor=after) == []

    def test_s6_anchor_before_first_bar_treated_as_first(self):
        bars = self._bars(5)
        before = bars[0]["date"] - timedelta(days=10)
        result_before = _compute_avwap_series(bars, anchor=before)
        result_first = _compute_avwap_series(bars, anchor=bars[0]["date"])
        assert len(result_before) == len(result_first)
        for a, b in zip(result_before, result_first):
            assert a["date"] == b["date"]
            assert abs(a["value"] - b["value"]) < 1e-9


# ── S7: _resolve_anchor ────────────────────────────────────────────────────────


class TestResolveAnchor:
    def test_s7_explicit_anchor_takes_priority(self, db_session):
        explicit = date(2024, 6, 1)
        repo = EarningsEventRepository(db_session)
        result = _resolve_anchor(explicit, repo, "NVDA", date.today())
        assert result == explicit

    def test_s7_returns_most_recent_past_earnings(self, db_session):
        today = date(2025, 1, 10)
        past = date(2025, 1, 5)
        older = date(2024, 12, 1)
        future = date(2025, 2, 1)
        for d in [past, older, future]:
            e = EarningsEvent(
                ticker="NVDA",
                earnings_date=d,
                fetched_at=datetime.now(timezone.utc),
            )
            db_session.add(e)
        db_session.commit()
        repo = EarningsEventRepository(db_session)
        result = _resolve_anchor(None, repo, "NVDA", today)
        assert result == past  # most recent <= today

    def test_s7_no_earnings_returns_none(self, db_session):
        repo = EarningsEventRepository(db_session)
        result = _resolve_anchor(None, repo, "AAPL", date.today())
        assert result is None


# ── S8: CockpitChartService integration ───────────────────────────────────────


class TestCockpitChartServiceIntegration:
    def test_s8_full_integration_with_db(self, db_session, fake_fmp):
        stock = _seed_stock_with_bars(db_session, "NVDA", 260)
        today = date.today()
        past_earnings = today - timedelta(days=30)
        e = EarningsEvent(
            ticker="NVDA",
            earnings_date=past_earnings,
            fetched_at=datetime.now(timezone.utc),
        )
        db_session.add(e)
        db_session.commit()

        svc = CockpitChartService(db_session, fake_fmp)
        result = svc.get_chart("NVDA", mas=[10, 21, 50, 150, 200], days=250)

        assert result["ticker"] == "NVDA"
        assert len(result["bars"]) == 250
        assert set(result["mas"].keys()) == {"10", "21", "50", "150", "200"}
        assert len(result["atr"]) > 0
        assert result["avwap"]["anchor"] == past_earnings
        assert len(result["avwap"]["series"]) > 0


# ── S9: service mas param variations ─────────────────────────────────────────


class TestServiceMasVariations:
    def test_s9_mas_list_controls_keys(self, db_session, fake_fmp):
        _seed_stock_with_bars(db_session, "TSLA", 260)
        svc = CockpitChartService(db_session, fake_fmp)

        r2 = svc.get_chart("TSLA", mas=[5, 250], days=250)
        assert set(r2["mas"].keys()) == {"5", "250"}

        r1 = svc.get_chart("TSLA", mas=[5], days=250)
        assert set(r1["mas"].keys()) == {"5"}

        r0 = svc.get_chart("TSLA", mas=[], days=250)
        assert r0["mas"] == {}


# ── S10–S14: router / API tests ───────────────────────────────────────────────


class TestCockpitChartRouter:
    def test_s10_default_params_returns_200(self, client, db_session):
        _seed_stock_with_bars(db_session, "NVDA", 260)
        # db_session and client share the same engine via conftest fixtures
        resp = client.get("/api/cockpit/chart/NVDA")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["ticker"] == "NVDA"
        assert set(body["data"]["mas"].keys()) == {"10", "21", "50", "150", "200"}

    def test_s11_invalid_ma_period_returns_422(self, client):
        resp = client.get("/api/cockpit/chart/NVDA?mas=10,500")
        assert resp.status_code == 422

    def test_s12_days_too_small_returns_422(self, client):
        resp = client.get("/api/cockpit/chart/NVDA?days=50")
        assert resp.status_code == 422

    def test_s13_invalid_anchor_returns_422(self, client):
        resp = client.get("/api/cockpit/chart/NVDA?anchor=not-a-date")
        assert resp.status_code == 422

    def test_s14_ticker_not_in_db_fmp_miss_returns_404(self, client, fake_fmp):
        fake_fmp.daily_bars_results = []  # FMP returns empty
        resp = client.get("/api/cockpit/chart/UNKNOWN_TICKER_XYZ")
        assert resp.status_code == 404
