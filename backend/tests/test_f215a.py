"""Tests for F215-a: Risk cap (RISK_ON 1.5%→1.25%) + EMA 10/21.

Sprint Contract standards covered:
  #1  _compute_ema_series(bars, 10) hand-calc fixture verified to 1e-6
  #2  _compute_ema_series period=21, α=2/22 correct
  #3  CockpitChartService.get_chart() returns emas key with non-empty lists (bars >= 22)
  #5  REGIME.SINGLE_TRADE_RISK_PCT["RISK_ON"] == 1.25 (params unit) +
      MarketRegimeService.compute_and_store() RISK_ON → single_trade_risk_pct=1.25
  #6  GET /api/cockpit/chart/NVDA returns emas with non-empty emas['10'] / emas['21']
  #7  GET /api/cockpit/regime with RISK_ON snapshot → singleTradeRiskPct=1.25
"""
from __future__ import annotations

import json
from datetime import date, datetime, timedelta, timezone
from typing import Any

import pytest

from app.models.daily_bar import DailyBar
from app.models.market_index import MarketIndex
from app.models.market_regime_snapshot import MarketRegimeSnapshot
from app.models.stock import Stock
from app.services.cockpit.chart_service import (
    CockpitChartService,
    _compute_ema_series,
)
from app.services.cockpit.cockpit_params import REGIME, SHARED
from app.services.cockpit.market_regime_service import MarketRegimeService


# ── helpers ───────────────────────────────────────────────────────────────────


def _make_bar(i: int, close: float) -> dict[str, Any]:
    return {
        "date": date(2024, 1, 1) + timedelta(days=i),
        "open": close - 1,
        "high": close + 2,
        "low": close - 2,
        "close": close,
        "volume": 1_000_000,
    }


def _seed_stock_with_bars(db, ticker: str, n: int) -> Stock:
    stock = Stock(
        ticker=ticker,
        name=f"{ticker} Corp",
        is_active=True,
        added_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.flush()
    end = date.today()
    start = end - timedelta(days=n - 1)
    for i in range(n):
        db.add(DailyBar(
            stock_id=stock.id,
            date=start + timedelta(days=i),
            open=100.0,
            high=102.0,
            low=98.0,
            close=100.0 + i * 0.01,
            volume=1_000_000,
        ))
    db.commit()
    return stock


def _insert_closes(db, symbol: str, closes: list[float]) -> None:
    start = date(2024, 1, 1)
    for i, close in enumerate(closes):
        d = start + timedelta(days=i)
        prev = closes[i - 1] if i > 0 else None
        pct = (close - prev) / prev * 100 if prev else None
        db.add(MarketIndex(symbol=symbol, name=symbol, date=d, close=close, prev_close=prev, change_pct=pct))
    db.commit()


def _bull_200() -> list[float]:
    return [100.0] * 199 + [120.0]


def _bull_51() -> list[float]:
    return [100.0] * 50 + [101.0]


def _iwm_rs_bull() -> list[float]:
    return [100.0] * 199 + [140.0]


# ── Standard #1: EMA10 hand-calc fixture ─────────────────────────────────────


class TestComputeEmaSeries:
    def test_s1_ema10_hand_calc_to_1e6(self):
        """#1: EMA10 on known closes matches hand-calculated values to 1e-6."""
        closes = [float(10 + i) for i in range(15)]  # 10,11,...,24
        bars = [_make_bar(i, closes[i]) for i in range(15)]

        alpha = 2.0 / 11.0
        seed = sum(closes[:10]) / 10  # SMA(10) of [10..19] = 14.5

        expected = [seed]
        ema = seed
        for i in range(10, 15):
            ema = alpha * closes[i] + (1 - alpha) * ema
            expected.append(ema)

        result = _compute_ema_series(bars, 10)
        assert len(result) == 6  # bars 9..14
        assert result[0]["date"] == bars[9]["date"]
        for j, point in enumerate(result):
            assert abs(point["value"] - expected[j]) < 1e-6

    def test_s1_constant_series_ema_equals_constant(self):
        """Constant close → EMA should equal that constant at every step."""
        bars = [_make_bar(i, 100.0) for i in range(25)]
        result = _compute_ema_series(bars, 10)
        assert len(result) == 16
        for point in result:
            assert abs(point["value"] - 100.0) < 1e-9

    def test_s2_ema21_alpha_2_22(self):
        """#2: EMA21 uses α=2/22; with 25 bars starting after index 20."""
        closes = [float(50 + i) for i in range(25)]
        bars = [_make_bar(i, closes[i]) for i in range(25)]

        alpha = 2.0 / 22.0
        seed = sum(closes[:21]) / 21

        expected = [seed]
        ema = seed
        for i in range(21, 25):
            ema = alpha * closes[i] + (1 - alpha) * ema
            expected.append(ema)

        result = _compute_ema_series(bars, 21)
        assert len(result) == 5  # bars 20..24
        for j, point in enumerate(result):
            assert abs(point["value"] - expected[j]) < 1e-6

    def test_period_gte_len_returns_empty(self):
        bars = [_make_bar(i, 100.0) for i in range(10)]
        assert _compute_ema_series(bars, 10) == []
        assert _compute_ema_series(bars, 15) == []
        assert _compute_ema_series(bars, 0) == []


# ── Standard #3: Service returns emas key ─────────────────────────────────────


class TestGetChartReturnsEmas:
    def test_s3_get_chart_contains_emas_key(self, db_session, fake_fmp):
        """#3: get_chart() returns dict with emas key containing non-empty lists."""
        _seed_stock_with_bars(db_session, "AAPL", 260)
        svc = CockpitChartService(db_session, fake_fmp)
        result = svc.get_chart("AAPL", days=250)
        assert "emas" in result
        assert "10" in result["emas"]
        assert "21" in result["emas"]
        assert len(result["emas"]["10"]) > 0
        assert len(result["emas"]["21"]) > 0

    def test_s3_emas_keys_are_always_10_and_21(self, db_session, fake_fmp):
        """EMA keys are always 10 and 21 regardless of ?mas parameter."""
        _seed_stock_with_bars(db_session, "TSLA", 260)
        svc = CockpitChartService(db_session, fake_fmp)
        result = svc.get_chart("TSLA", mas=[50, 150], days=250)
        assert set(result["emas"].keys()) == {"10", "21"}


# ── Standard #5: RISK_ON → single_trade_risk_pct=1.25 ────────────────────────


class TestRiskOnCapAt125:
    def test_s5_params_risk_on_equals_125(self):
        """#5 (unit): REGIME.SINGLE_TRADE_RISK_PCT['RISK_ON'] == 1.25 (SRS §10)."""
        assert REGIME.SINGLE_TRADE_RISK_PCT["RISK_ON"] == 1.25

    def test_s5_other_regime_risk_unchanged(self):
        """Other 4 regime tiers are unchanged by F215-a."""
        assert REGIME.SINGLE_TRADE_RISK_PCT["CONSTRUCTIVE"] == 1.0
        assert REGIME.SINGLE_TRADE_RISK_PCT["NEUTRAL"] == 0.75
        assert REGIME.SINGLE_TRADE_RISK_PCT["DEFENSIVE"] == 0.5
        assert REGIME.SINGLE_TRADE_RISK_PCT["RISK_OFF"] == 0.0

    def test_s5_service_risk_on_snapshot_has_125(self, db_session):
        """#5 (integration): compute_and_store() RISK_ON → single_trade_risk_pct=1.25."""
        for sym in ["SPY", "QQQ"]:
            _insert_closes(db_session, sym, _bull_200())
        _insert_closes(db_session, "IWM", _iwm_rs_bull())
        for sym in SHARED.SECTOR_ETFS:
            _insert_closes(db_session, sym, _bull_51())

        snap = MarketRegimeService(db_session).compute_and_store(date(2026, 1, 1))
        assert snap.regime == "RISK_ON"
        assert snap.single_trade_risk_pct == 1.25


# ── Standard #6: Router returns emas field ────────────────────────────────────


class TestChartRouterEmasField:
    def test_s6_chart_endpoint_returns_emas(self, client, db_session):
        """#6: GET /api/cockpit/chart/NVDA returns emas['10'] and emas['21'] non-empty."""
        _seed_stock_with_bars(db_session, "NVDA", 260)
        resp = client.get("/api/cockpit/chart/NVDA?mas=50,150&days=250")
        assert resp.status_code == 200
        body = resp.json()
        emas = body["data"]["emas"]
        assert "10" in emas and "21" in emas
        assert len(emas["10"]) > 0
        assert len(emas["21"]) > 0

    def test_s6_emas_param_ignored_fixed_series_returned(self, client, db_session):
        """?emas= is silently ignored; response always returns fixed EMA10/EMA21."""
        _seed_stock_with_bars(db_session, "MSFT", 260)
        resp = client.get("/api/cockpit/chart/MSFT?emas=5,10")
        assert resp.status_code == 200
        emas = resp.json()["data"]["emas"]
        assert set(emas.keys()) == {"10", "21"}


# ── Standard #7: Regime router returns singleTradeRiskPct=1.25 ───────────────


class TestRegimeRouterRiskOnField:
    def test_s7_regime_router_risk_on_returns_125(self, client, db_session):
        """#7: GET /api/cockpit/regime with RISK_ON snapshot → singleTradeRiskPct=1.25."""
        snap = MarketRegimeSnapshot(
            date=date(2026, 5, 12),
            regime="RISK_ON",
            market_score=92,
            spy_trend_score=25,
            qqq_trend_score=20,
            iwm_breadth_score=15,
            sector_participation_score=20,
            risk_appetite_score=6,
            volatility_stress_score=6,
            allowed_exposure_pct=90.0,
            single_trade_risk_pct=1.25,
            preferred_setups=json.dumps(["BREAKOUT", "CAPITULATION", "RECLAIM"]),
            avoid_setups=json.dumps([]),
            computed_at=datetime(2026, 5, 12, 22, 0, 0, tzinfo=timezone.utc),
        )
        db_session.add(snap)
        db_session.commit()
        resp = client.get("/api/cockpit/regime")
        assert resp.status_code == 200
        body = resp.json()
        assert body["data"]["singleTradeRiskPct"] == 1.25
