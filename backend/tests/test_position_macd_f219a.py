"""F219-a: GET /api/cockpit/positions items[] contain macdDivergence field.

Sprint Contract standard #11.
"""
from __future__ import annotations

from datetime import date, datetime, timezone

import pytest

from app.models.position import Position
from app.models.setup_snapshot import SetupSnapshot
from app.models.stock import Stock


def _seed_stock(db_session, ticker: str) -> Stock:
    stock = Stock(ticker=ticker, name=f"{ticker} Corp", is_active=True, added_at=datetime.now(timezone.utc))
    db_session.add(stock)
    db_session.flush()
    return stock


def _seed_position(db_session, ticker: str) -> Position:
    pos = Position(
        ticker=ticker,
        entry_price=100.0,
        entry_date=date(2026, 4, 1),
        shares=10,
        stop_price=95.0,
        target_2r=110.0,
        target_3r=115.0,
        setup_type="BREAKOUT",
        status="OPEN",
        created_at=datetime.now(timezone.utc),
        updated_at=datetime.now(timezone.utc),
    )
    db_session.add(pos)
    db_session.flush()
    return pos


def _seed_snapshot(db_session, ticker: str, macd_divergence: str | None) -> SetupSnapshot:
    snap = SetupSnapshot(
        ticker=ticker,
        scan_date=date.today(),
        setup_type="BREAKOUT",
        setup_quality="B",
        entry_price=102.0,
        stop_price=95.0,
        target_2r=112.0,
        target_3r=117.0,
        distance_to_entry_pct=2.0,
        reward_risk=2.0,
        rs_percentile=75.0,
        volume_status="NORMAL",
        trend_score=4,
        earnings_risk="SAFE",
        ready_signal=False,
        suggested_action="watch",
        macd_divergence=macd_divergence,
        scanned_at=datetime.now(timezone.utc),
    )
    db_session.add(snap)
    db_session.flush()
    return snap


class TestPositionMacdDivergenceField:
    """#11: GET /api/cockpit/positions items[] contain macdDivergence field."""

    def test_s11_macd_divergence_null_when_no_snapshot(self, client, db_session) -> None:
        """No setup_snapshot for ticker → macdDivergence = null."""
        _seed_position(db_session, "NOSNAPSHOT")
        db_session.commit()

        resp = client.get("/api/cockpit/positions")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        item = next((i for i in items if i["ticker"] == "NOSNAPSHOT"), None)
        assert item is not None
        assert "macdDivergence" in item
        assert item["macdDivergence"] is None

    def test_s11_macd_divergence_none_from_snapshot(self, client, db_session) -> None:
        """Snapshot with macd_divergence=None → macdDivergence = null."""
        _seed_stock(db_session, "AAPL")
        _seed_position(db_session, "AAPL")
        _seed_snapshot(db_session, "AAPL", macd_divergence=None)
        db_session.commit()

        resp = client.get("/api/cockpit/positions")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        item = next((i for i in items if i["ticker"] == "AAPL"), None)
        assert item is not None
        assert item["macdDivergence"] is None

    def test_s11_macd_divergence_bearish_from_snapshot(self, client, db_session) -> None:
        """Snapshot with macd_divergence='bearish' → macdDivergence = 'bearish'."""
        _seed_stock(db_session, "NVDA")
        _seed_position(db_session, "NVDA")
        _seed_snapshot(db_session, "NVDA", macd_divergence="bearish")
        db_session.commit()

        resp = client.get("/api/cockpit/positions")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        item = next((i for i in items if i["ticker"] == "NVDA"), None)
        assert item is not None
        assert item["macdDivergence"] == "bearish"

    def test_s11_macd_divergence_bullish_from_snapshot(self, client, db_session) -> None:
        """Snapshot with macd_divergence='bullish' → macdDivergence = 'bullish'."""
        _seed_stock(db_session, "MSFT")
        _seed_position(db_session, "MSFT")
        _seed_snapshot(db_session, "MSFT", macd_divergence="bullish")
        db_session.commit()

        resp = client.get("/api/cockpit/positions")
        assert resp.status_code == 200
        items = resp.json()["data"]["items"]
        item = next((i for i in items if i["ticker"] == "MSFT"), None)
        assert item is not None
        assert item["macdDivergence"] == "bullish"
