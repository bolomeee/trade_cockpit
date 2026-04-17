from __future__ import annotations

from datetime import date, timedelta

import pytest

from app.models import Stock
from app.repositories.daily_bar_repository import BarDTO, DailyBarRepository


@pytest.fixture
def stock(db_session) -> Stock:
    s = Stock(ticker="AAPL", name="Apple", is_active=True)
    db_session.add(s)
    db_session.commit()
    db_session.refresh(s)
    return s


def _bar(d: date, close: float = 100.0) -> BarDTO:
    return BarDTO(date=d, open=close, high=close, low=close, close=close, volume=1000)


def _make_bars(start: date, n: int) -> list[BarDTO]:
    return [_bar(start + timedelta(days=i), 100.0 + i) for i in range(n)]


class TestDailyBarRepository:
    def test_get_latest_date_empty(self, db_session, stock):
        repo = DailyBarRepository(db_session)
        assert repo.get_latest_date(stock.id) is None

    def test_bulk_upsert_inserts_and_counts(self, db_session, stock):
        repo = DailyBarRepository(db_session)
        bars = _make_bars(date(2026, 1, 1), 5)
        added = repo.bulk_upsert(stock.id, bars)
        assert added == 5
        assert repo.count_bars(stock.id) == 5
        assert repo.get_latest_date(stock.id) == date(2026, 1, 5)

    def test_bulk_upsert_is_idempotent(self, db_session, stock):
        repo = DailyBarRepository(db_session)
        bars = _make_bars(date(2026, 1, 1), 5)
        repo.bulk_upsert(stock.id, bars)
        added2 = repo.bulk_upsert(stock.id, bars)
        assert added2 == 0
        assert repo.count_bars(stock.id) == 5

    def test_bulk_upsert_preserves_existing_rows(self, db_session, stock):
        """Existing rows are NOT overwritten on conflict."""
        repo = DailyBarRepository(db_session)
        original = [_bar(date(2026, 1, 1), 100.0)]
        repo.bulk_upsert(stock.id, original)

        different = [_bar(date(2026, 1, 1), 999.0), _bar(date(2026, 1, 2), 200.0)]
        added = repo.bulk_upsert(stock.id, different)
        assert added == 1  # only Jan 2 inserted

        # Jan 1 close unchanged
        from sqlalchemy import select

        from app.models import DailyBar

        row = db_session.execute(
            select(DailyBar).where(DailyBar.date == date(2026, 1, 1))
        ).scalar_one()
        assert row.close == 100.0

    def test_prune_to_window_keeps_latest_n(self, db_session, stock):
        repo = DailyBarRepository(db_session)
        bars = _make_bars(date(2025, 1, 1), 300)
        repo.bulk_upsert(stock.id, bars)
        assert repo.count_bars(stock.id) == 300

        deleted = repo.prune_to_window(stock.id, max_rows=250)
        assert deleted == 50
        assert repo.count_bars(stock.id) == 250
        # earliest remaining date = original[50]
        from sqlalchemy import select

        from app.models import DailyBar

        min_date = db_session.execute(
            select(DailyBar.date).where(DailyBar.stock_id == stock.id).order_by(DailyBar.date.asc())
        ).scalar()
        assert min_date == date(2025, 1, 1) + timedelta(days=50)

    def test_prune_noop_when_below_window(self, db_session, stock):
        repo = DailyBarRepository(db_session)
        repo.bulk_upsert(stock.id, _make_bars(date(2026, 1, 1), 100))
        deleted = repo.prune_to_window(stock.id, max_rows=250)
        assert deleted == 0
        assert repo.count_bars(stock.id) == 100

    def test_bulk_upsert_empty_list(self, db_session, stock):
        repo = DailyBarRepository(db_session)
        assert repo.bulk_upsert(stock.id, []) == 0
