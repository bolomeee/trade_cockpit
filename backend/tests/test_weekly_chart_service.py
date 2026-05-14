"""F216-a tests: aggregate_daily_to_weekly (standards 1-5) + WeeklyChartService (6-9) + regression (10)."""
from __future__ import annotations

from datetime import date, timedelta
from unittest.mock import MagicMock, patch

import pytest

from app.services.cockpit.cockpit_params import WEEKLY
from app.services.cockpit.weekly_chart_service import WeeklyChartService, aggregate_daily_to_weekly
from app.services.watchlist_service import APIError


def _bar(
    d: date,
    o: float = 100.0,
    h: float = 105.0,
    lo: float = 95.0,
    c: float = 102.0,
    v: int = 1000,
) -> dict:
    return {"date": d, "open": o, "high": h, "low": lo, "close": c, "volume": v}


# ── Standards 1-5: aggregate_daily_to_weekly (pure function) ──────────────────


def test_aggregate_empty_returns_empty():
    """Standard 1: empty input → []"""
    assert aggregate_daily_to_weekly([]) == []


def test_aggregate_full_week_five_days():
    """Standard 2: 5 trading days Mon–Fri → 1 weekly bar, correct OHLCV + date=Fri."""
    bars = [
        _bar(date(2026, 5, 4), o=100, h=110, lo=99, c=105, v=1000),   # Mon
        _bar(date(2026, 5, 5), o=105, h=112, lo=103, c=108, v=1200),  # Tue
        _bar(date(2026, 5, 6), o=108, h=115, lo=107, c=110, v=1100),  # Wed
        _bar(date(2026, 5, 7), o=110, h=113, lo=109, c=111, v=900),   # Thu
        _bar(date(2026, 5, 8), o=111, h=116, lo=110, c=114, v=1300),  # Fri
    ]
    result = aggregate_daily_to_weekly(bars)
    assert len(result) == 1
    w = result[0]
    assert w["date"] == date(2026, 5, 8)   # last actual trading day (Friday)
    assert w["open"] == 100                # Monday open
    assert w["high"] == 116               # max high across all days
    assert w["low"] == 99                 # min low across all days
    assert w["close"] == 114              # Friday close
    assert w["volume"] == 5500            # sum of volumes


def test_aggregate_two_weeks_ten_days():
    """Standard 3: 10 trading days across 2 ISO weeks → 2 weekly bars."""
    # ISO week 19 (2026): 2026-05-04 Mon to 2026-05-08 Fri
    # ISO week 20 (2026): 2026-05-11 Mon to 2026-05-15 Fri
    bars = []
    for i in range(5):
        bars.append(_bar(date(2026, 5, 4) + timedelta(days=i)))
    for i in range(5):
        bars.append(_bar(date(2026, 5, 11) + timedelta(days=i)))
    result = aggregate_daily_to_weekly(bars)
    assert len(result) == 2
    assert result[0]["date"] == date(2026, 5, 8)   # end of week 19
    assert result[1]["date"] == date(2026, 5, 15)  # end of week 20


def test_aggregate_short_week_date_is_thursday():
    """Standard 4: Mon–Thu only (Friday holiday) → weekly bar.date = Thursday."""
    bars = [
        _bar(date(2026, 5, 4)),   # Mon
        _bar(date(2026, 5, 5)),   # Tue
        _bar(date(2026, 5, 6)),   # Wed
        _bar(date(2026, 5, 7)),   # Thu  (Friday absent — holiday)
    ]
    result = aggregate_daily_to_weekly(bars)
    assert len(result) == 1
    assert result[0]["date"] == date(2026, 5, 7)  # Thursday, not forced to Friday


def test_aggregate_single_day_equals_ohlcv():
    """Standard 5: single isolated trading day → 1 weekly bar equal to that day's OHLCV."""
    d = date(2026, 5, 6)
    b = _bar(d, o=100, h=110, lo=95, c=105, v=2000)
    result = aggregate_daily_to_weekly([b])
    assert len(result) == 1
    w = result[0]
    assert w["date"] == d
    assert w["open"] == 100
    assert w["high"] == 110
    assert w["low"] == 95
    assert w["close"] == 105
    assert w["volume"] == 2000


# ── Standards 6-9: WeeklyChartService ─────────────────────────────────────────


def test_get_weekly_chart_unknown_ticker_raises_not_found():
    """Standard 6: unknown ticker → APIError with code NOT_FOUND."""
    mock_db = MagicMock()
    with patch("app.services.cockpit.weekly_chart_service.StockRepository") as mock_cls:
        mock_repo = MagicMock()
        mock_repo.get_by_ticker.return_value = None
        mock_cls.return_value = mock_repo

        svc = WeeklyChartService(mock_db)
        with pytest.raises(APIError) as exc_info:
            svc.get_weekly_chart("UNKNOWN")
        assert exc_info.value.code == "NOT_FOUND"


def test_get_weekly_chart_250_bars_returns_50_weekly():
    """Standard 7: 250 daily bars (5/week × 50 weeks) → ~50 weekly bars + non-empty MA10."""
    # Build exactly 250 weekday bars starting 2021-01-04 (Monday)
    start = date(2021, 1, 4)
    bars: list[dict] = []
    d = start
    while len(bars) < 250:
        if d.weekday() < 5:  # Mon–Fri only
            bars.append(_bar(d, c=100 + len(bars) * 0.1))
        d += timedelta(days=1)

    mock_db = MagicMock()
    mock_stock = MagicMock()
    mock_stock.id = 1

    with patch("app.services.cockpit.weekly_chart_service.StockRepository") as mock_cls:
        mock_repo = MagicMock()
        mock_repo.get_by_ticker.return_value = mock_stock
        mock_cls.return_value = mock_repo

        svc = WeeklyChartService(mock_db)
        svc._load_all_bars = MagicMock(return_value=bars)

        result = svc.get_weekly_chart("AAPL", weeks=50)

    assert abs(len(result["weekly_bars"]) - 50) <= 1
    # MA10 must be non-empty when 50 weekly bars available
    assert len(result["weekly_mas"]["10"]) > 0
    assert "30" in result["weekly_mas"]
    assert "40" in result["weekly_mas"]


def test_get_weekly_chart_insufficient_bars_returns_empty():
    """Standard 8: daily_bars < 4 → empty weekly_bars + empty weekly_mas, no error."""
    mock_db = MagicMock()
    mock_stock = MagicMock()
    mock_stock.id = 1

    with patch("app.services.cockpit.weekly_chart_service.StockRepository") as mock_cls:
        mock_repo = MagicMock()
        mock_repo.get_by_ticker.return_value = mock_stock
        mock_cls.return_value = mock_repo

        svc = WeeklyChartService(mock_db)
        svc._load_all_bars = MagicMock(
            return_value=[
                _bar(date(2026, 5, 4)),
                _bar(date(2026, 5, 5)),
                _bar(date(2026, 5, 6)),
            ]  # 3 bars < MIN_DAILY_BARS_FOR_WEEKLY=4
        )

        result = svc.get_weekly_chart("AAPL")

    assert result["ticker"] == "AAPL"
    assert result["weekly_bars"] == []
    assert result["weekly_mas"] == {"10": [], "30": [], "40": []}


def test_weekly_params_constants():
    """Standard 9: WEEKLY.DEFAULT_WEEKS == 50, WEEKLY.WEEKLY_MAS == [10, 30, 40]."""
    assert WEEKLY.DEFAULT_WEEKS == 50
    assert WEEKLY.WEEKLY_MAS == [10, 30, 40]
    assert WEEKLY.MIN_DAILY_BARS_FOR_WEEKLY == 4
