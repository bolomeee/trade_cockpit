from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest

from app.models import DailyBar, Signal, Stock, SystemLog
from app.services.data_refresh_service import (
    DataRefreshService,
    _fmp_bar_to_dto,
)


class FakeFmp:
    """Programmable FMP stand-in for refresh tests."""

    def __init__(self) -> None:
        # Map ticker -> list of FMP bar dicts (or exception)
        self.bars_by_ticker: dict[str, list | Exception] = {}
        self.calls: list[tuple[str, object, object]] = []

    def get_daily_bars(self, ticker, from_date, to_date):
        self.calls.append((ticker, from_date, to_date))
        entry = self.bars_by_ticker.get(ticker, [])
        if isinstance(entry, Exception):
            raise entry
        return entry


def _bar(d: date, close: float = 100.0) -> dict:
    return {
        "date": d.isoformat(),
        "open": close,
        "high": close + 1,
        "low": close - 1,
        "close": close,
        "volume": 1_000_000,
    }


@pytest.fixture
def make_stock(db_session):
    def _make(ticker: str = "AAPL") -> Stock:
        s = Stock(ticker=ticker, name=f"{ticker} Inc", is_active=True)
        db_session.add(s)
        db_session.commit()
        db_session.refresh(s)
        return s

    return _make


@pytest.fixture
def fmp() -> FakeFmp:
    return FakeFmp()


@pytest.fixture
def service(db_session, fmp) -> DataRefreshService:
    return DataRefreshService(db_session, fmp=fmp)


class TestBarMapping:
    def test_maps_fmp_bar_dict(self):
        bar = _fmp_bar_to_dto(_bar(date(2026, 4, 15), close=150.5))
        assert bar is not None
        assert bar["date"] == date(2026, 4, 15)
        assert bar["open"] == 150.5
        assert bar["close"] == 150.5
        assert bar["volume"] == 1_000_000

    def test_accepts_datetime_prefix_in_date(self):
        bar = _fmp_bar_to_dto(
            {"date": "2026-04-15 00:00:00", "open": 1, "high": 2, "low": 0.5, "close": 1.5, "volume": 10}
        )
        assert bar is not None
        assert bar["date"] == date(2026, 4, 15)

    def test_returns_none_on_missing_fields(self):
        assert _fmp_bar_to_dto({"date": None}) is None
        assert _fmp_bar_to_dto({}) is None
        assert _fmp_bar_to_dto({"date": "2026-04-15"}) is None  # missing OHLCV


class TestBackfillStock:
    def test_persists_bars_and_updates_last_refreshed(
        self, db_session, service, fmp, make_stock
    ):
        stock = make_stock("AAPL")
        today = datetime.now(timezone.utc).date()
        bars = [_bar(today - timedelta(days=i), close=100 + i) for i in range(250)]
        fmp.bars_by_ticker["AAPL"] = bars

        result = service.backfill_stock(stock.id, days=250)
        assert result["status"] == "ok"
        assert result["bars_added"] == 250

        bar_count = db_session.query(DailyBar).filter_by(stock_id=stock.id).count()
        assert bar_count == 250

        db_session.refresh(stock)
        assert stock.last_refreshed_at is not None

    def test_triggers_signal_recompute(self, db_session, service, fmp, make_stock):
        stock = make_stock("AAPL")
        today = datetime.now(timezone.utc).date()
        bars = [_bar(today - timedelta(days=i), close=100 + i * 0.1) for i in range(200)]
        fmp.bars_by_ticker["AAPL"] = bars

        service.backfill_stock(stock.id, days=250)

        signal_count = db_session.query(Signal).filter_by(stock_id=stock.id).count()
        assert signal_count > 0

    def test_backfill_prunes_to_window(self, db_session, service, fmp, make_stock):
        stock = make_stock("AAPL")
        today = datetime.now(timezone.utc).date()
        bars = [_bar(today - timedelta(days=i), close=100.0) for i in range(300)]
        fmp.bars_by_ticker["AAPL"] = bars

        service.backfill_stock(stock.id, days=250)
        assert db_session.query(DailyBar).filter_by(stock_id=stock.id).count() == 250


class TestIncrementStock:
    def test_increment_from_empty_is_backfill(self, db_session, service, fmp, make_stock):
        stock = make_stock("AAPL")
        today = datetime.now(timezone.utc).date()
        bars = [_bar(today - timedelta(days=i)) for i in range(10)]
        fmp.bars_by_ticker["AAPL"] = bars

        result = service.increment_stock(stock.id)
        assert result["status"] == "ok"
        assert db_session.query(DailyBar).filter_by(stock_id=stock.id).count() == 10

    def test_increment_adds_without_prune_when_below_window(
        self, db_session, service, fmp, make_stock
    ):
        stock = make_stock("AAPL")
        today = datetime.now(timezone.utc).date()
        base = today - timedelta(days=210)
        for i in range(200):
            db_session.add(
                DailyBar(
                    stock_id=stock.id,
                    date=base + timedelta(days=i),
                    open=100,
                    high=100,
                    low=100,
                    close=100,
                    volume=1,
                )
            )
        db_session.commit()

        latest = base + timedelta(days=199)
        new_bars = [_bar(latest + timedelta(days=i), close=100.0) for i in range(1, 6)]
        fmp.bars_by_ticker["AAPL"] = new_bars

        result = service.increment_stock(stock.id)
        assert result["status"] == "ok"
        assert db_session.query(DailyBar).filter_by(stock_id=stock.id).count() == 205

    def test_increment_prunes_when_over_window(
        self, db_session, service, fmp, make_stock
    ):
        stock = make_stock("AAPL")
        today = datetime.now(timezone.utc).date()
        base = today - timedelta(days=260)
        for i in range(250):
            db_session.add(
                DailyBar(
                    stock_id=stock.id,
                    date=base + timedelta(days=i),
                    open=100,
                    high=100,
                    low=100,
                    close=100,
                    volume=1,
                )
            )
        db_session.commit()

        latest = base + timedelta(days=249)
        new_bars = [_bar(latest + timedelta(days=i), close=100.0) for i in range(1, 4)]
        fmp.bars_by_ticker["AAPL"] = new_bars

        service.increment_stock(stock.id)
        assert db_session.query(DailyBar).filter_by(stock_id=stock.id).count() == 250


class TestRefreshAll:
    def test_isolates_failure_per_stock(self, db_session, service, fmp, make_stock):
        s1 = make_stock("AAA")
        s2 = make_stock("BBB")
        s3 = make_stock("CCC")
        today = datetime.now(timezone.utc).date()

        fmp.bars_by_ticker["AAA"] = [_bar(today - timedelta(days=i)) for i in range(5)]
        fmp.bars_by_ticker["BBB"] = RuntimeError("fmp exploded")
        fmp.bars_by_ticker["CCC"] = [_bar(today - timedelta(days=i)) for i in range(5)]

        result = service.refresh_all([s1.id, s2.id, s3.id])
        assert result["total"] == 3
        assert result["completed"] == 2
        assert result["failed"] == 1

        assert db_session.query(DailyBar).filter_by(stock_id=s1.id).count() == 5
        assert db_session.query(DailyBar).filter_by(stock_id=s2.id).count() == 0
        assert db_session.query(DailyBar).filter_by(stock_id=s3.id).count() == 5

        errors = db_session.query(SystemLog).filter_by(level="ERROR").all()
        assert len(errors) == 1
        assert "BBB" in errors[0].message

    def test_logs_ok_per_successful_stock(self, db_session, service, fmp, make_stock):
        s1 = make_stock("AAA")
        s2 = make_stock("BBB")
        today = datetime.now(timezone.utc).date()
        fmp.bars_by_ticker["AAA"] = [_bar(today - timedelta(days=i)) for i in range(3)]
        fmp.bars_by_ticker["BBB"] = [_bar(today - timedelta(days=i)) for i in range(4)]

        service.refresh_all([s1.id, s2.id])

        ok_logs = db_session.query(SystemLog).filter_by(level="OK").all()
        assert len(ok_logs) == 2
        messages = {log.message for log in ok_logs}
        assert any("AAA" in m and "3 bars" in m for m in messages)
        assert any("BBB" in m and "4 bars" in m for m in messages)
