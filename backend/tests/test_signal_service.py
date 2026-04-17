from __future__ import annotations

from datetime import date, datetime, timedelta, timezone

import pytest
from sqlalchemy.orm import Session

from app.models import DailyBar, Pullback, Signal, Stock
from app.services.signal_engine import (
    SIGNAL_BUY_ZONE,
    SIGNAL_INSUFFICIENT,
    SIGNAL_NEUTRAL,
    SIGNAL_RETENTION_DAYS,
)
from app.services.signal_service import SignalService
from app.services.watchlist_service import APIError


def _seed_stock(db: Session, ticker: str = "AAPL") -> Stock:
    stock = Stock(
        ticker=ticker,
        name=f"{ticker} Inc.",
        exchange="NASDAQ",
        is_active=True,
        added_at=datetime.now(timezone.utc),
    )
    db.add(stock)
    db.commit()
    db.refresh(stock)
    return stock


def _seed_bars(db: Session, stock_id: int, closes: list[float]) -> None:
    start = date(2025, 1, 1)
    for i, c in enumerate(closes):
        db.add(
            DailyBar(
                stock_id=stock_id,
                date=start + timedelta(days=i),
                open=c,
                high=c,
                low=c,
                close=c,
                volume=1000,
            )
        )
    db.commit()


def test_recompute_writes_insufficient_when_bars_below_150(
    db_session: Session,
) -> None:
    stock = _seed_stock(db_session)
    _seed_bars(db_session, stock.id, [100.0 + i * 0.1 for i in range(140)])
    SignalService(db_session).recompute_for_stock(stock.id)

    signals = db_session.query(Signal).filter_by(stock_id=stock.id).all()
    assert len(signals) == 140
    assert all(s.signal_type == SIGNAL_INSUFFICIENT for s in signals)
    assert all(s.ma150_value is None for s in signals)


def test_recompute_is_idempotent(db_session: Session) -> None:
    stock = _seed_stock(db_session)
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(200)])
    service = SignalService(db_session)

    service.recompute_for_stock(stock.id)
    first_count = db_session.query(Signal).filter_by(stock_id=stock.id).count()
    first_types = [
        s.signal_type
        for s in db_session.query(Signal)
        .filter_by(stock_id=stock.id)
        .order_by(Signal.date)
        .all()
    ]

    service.recompute_for_stock(stock.id)
    second_count = db_session.query(Signal).filter_by(stock_id=stock.id).count()
    second_types = [
        s.signal_type
        for s in db_session.query(Signal)
        .filter_by(stock_id=stock.id)
        .order_by(Signal.date)
        .all()
    ]

    assert first_count == second_count
    assert first_types == second_types


def test_recompute_caps_signals_at_retention_window(db_session: Session) -> None:
    stock = _seed_stock(db_session)
    closes = [100.0 + i * 0.05 for i in range(SIGNAL_RETENTION_DAYS + 30)]
    _seed_bars(db_session, stock.id, closes)
    SignalService(db_session).recompute_for_stock(stock.id)

    count = db_session.query(Signal).filter_by(stock_id=stock.id).count()
    assert count == SIGNAL_RETENTION_DAYS


def test_recompute_records_pullback_with_returns(db_session: Session) -> None:
    stock = _seed_stock(db_session)
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(240)])
    SignalService(db_session).recompute_for_stock(stock.id)

    pullbacks = db_session.query(Pullback).filter_by(stock_id=stock.id).all()
    assert len(pullbacks) >= 1
    first = pullbacks[0]
    assert first.ma150_value is not None
    assert first.distance_pct is not None
    # For a rising series, 10-day horizon should be available; 30-day may or may not
    assert first.return_10d is not None


def test_recompute_neutral_signal_when_insufficient_slope_history(
    db_session: Session,
) -> None:
    stock = _seed_stock(db_session)
    # 155 bars: MA150 exists but < 20 MA values for slope
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(155)])
    SignalService(db_session).recompute_for_stock(stock.id)
    latest = (
        db_session.query(Signal)
        .filter_by(stock_id=stock.id)
        .order_by(Signal.date.desc())
        .first()
    )
    assert latest is not None
    assert latest.signal_type == SIGNAL_NEUTRAL
    assert latest.slope_positive is None


def test_list_board_sorts_by_signal_priority(db_session: Session) -> None:
    stock_bz = _seed_stock(db_session, "AAA")
    stock_neutral = _seed_stock(db_session, "BBB")
    # AAA: rising series landing in buy zone
    _seed_bars(db_session, stock_bz.id, [100.0 + i * 0.05 for i in range(200)])
    # BBB: falling series → NEUTRAL
    _seed_bars(
        db_session, stock_neutral.id, [200.0 - i * 0.1 for i in range(200)]
    )
    service = SignalService(db_session)
    service.recompute_for_stock(stock_bz.id)
    service.recompute_for_stock(stock_neutral.id)

    board = service.list_board()
    assert [item["ticker"] for item in board] == ["AAA", "BBB"]
    assert board[0]["signalType"] == SIGNAL_BUY_ZONE
    assert board[1]["signalType"] == SIGNAL_NEUTRAL


def test_get_ticker_detail_returns_latest_and_history(db_session: Session) -> None:
    stock = _seed_stock(db_session)
    _seed_bars(db_session, stock.id, [100.0 + i * 0.05 for i in range(200)])
    service = SignalService(db_session)
    service.recompute_for_stock(stock.id)

    detail = service.get_ticker_detail("aapl", days=10)
    assert detail["ticker"] == "AAPL"
    assert detail["latest"] is not None
    assert len(detail["history"]) == 10


def test_get_ticker_detail_raises_404_for_unknown(db_session: Session) -> None:
    service = SignalService(db_session)
    with pytest.raises(APIError) as exc:
        service.get_ticker_detail("ZZZZ", days=10)
    assert exc.value.status_code == 404
    assert exc.value.code == "NOT_FOUND"


def test_get_ticker_detail_raises_404_for_inactive(db_session: Session) -> None:
    stock = _seed_stock(db_session, "XXX")
    stock.is_active = False
    db_session.commit()
    service = SignalService(db_session)
    with pytest.raises(APIError) as exc:
        service.get_ticker_detail("XXX", days=10)
    assert exc.value.status_code == 404
