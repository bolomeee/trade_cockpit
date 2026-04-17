from __future__ import annotations

from typing import Any

from sqlalchemy.orm import Session

from app.models import Signal, Stock
from app.repositories.signal_repository import SignalRepository
from app.repositories.stock_repository import StockRepository
from app.services.signal_engine import (
    SIGNAL_PRIORITY,
    BarPoint,
    attach_pullback_returns,
    build_signals,
    detect_pullbacks,
)
from app.services.watchlist_service import APIError


class SignalService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SignalRepository(db)
        self.stock_repo = StockRepository(db)

    def recompute_for_stock(self, stock_id: int) -> None:
        bars_orm = self.repo.list_daily_bars(stock_id)
        bars = [BarPoint(date=b.date, close=b.close) for b in bars_orm]
        signals = build_signals(bars)
        pullbacks = detect_pullbacks(signals)
        pullbacks_with_returns = attach_pullback_returns(pullbacks, bars)
        self.repo.replace_signals(stock_id, signals)
        self.repo.replace_pullbacks(stock_id, pullbacks_with_returns)

    def list_board(self) -> list[dict[str, Any]]:
        rows = self.repo.list_latest_per_active_stock()
        items: list[dict[str, Any]] = []
        for stock, signal in rows:
            if signal is None:
                continue
            items.append(_build_board_item(stock, signal))
        items.sort(
            key=lambda item: (
                SIGNAL_PRIORITY.get(item["signalType"], 99),
                item["ticker"],
            )
        )
        return items

    def get_ticker_detail(self, raw_ticker: str, days: int) -> dict[str, Any]:
        ticker = raw_ticker.strip().upper()
        stock = self.stock_repo.get_by_ticker(ticker)
        if stock is None or not stock.is_active:
            raise APIError("NOT_FOUND", f"ticker {ticker} not in watchlist", 404)
        latest = self.repo.get_latest_signal(stock.id)
        history = self.repo.get_signal_history(stock.id, days)
        return {
            "ticker": stock.ticker,
            "name": stock.name,
            "latest": _build_latest_payload(latest) if latest is not None else None,
            "history": [_build_history_entry(s) for s in history],
        }


def _build_board_item(stock: Stock, signal: Signal) -> dict[str, Any]:
    return {
        "ticker": stock.ticker,
        "name": stock.name,
        "signalType": signal.signal_type,
        "date": signal.date,
        "closePrice": signal.close_price,
        "ma150Value": signal.ma150_value,
        "distancePct": signal.distance_pct,
        "slopePositive": signal.slope_positive,
        "slopeValue": signal.slope_value,
    }


def _build_latest_payload(signal: Signal) -> dict[str, Any]:
    return {
        "signalType": signal.signal_type,
        "date": signal.date,
        "closePrice": signal.close_price,
        "ma150Value": signal.ma150_value,
        "distancePct": signal.distance_pct,
        "slopePositive": signal.slope_positive,
        "slopeValue": signal.slope_value,
    }


def _build_history_entry(signal: Signal) -> dict[str, Any]:
    return {
        "date": signal.date,
        "signalType": signal.signal_type,
        "closePrice": signal.close_price,
        "ma150Value": signal.ma150_value,
        "distancePct": signal.distance_pct,
    }
