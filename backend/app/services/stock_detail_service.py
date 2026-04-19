from __future__ import annotations

import hashlib
from datetime import date
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models import DailyBar, Signal
from app.repositories.pullback_repository import PullbackRepository
from app.repositories.stock_repository import StockRepository
from app.services.watchlist_service import APIError

CHART_WINDOW_DAYS = 250
MA150_PERIOD = 150
FUNDAMENTALS_MOCK_SOURCE = "mock"


class StockDetailService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.stocks = StockRepository(db)
        self.pullbacks = PullbackRepository(db)

    def _resolve_active_stock(self, raw_ticker: str):
        ticker = raw_ticker.strip().upper()
        stock = self.stocks.get_by_ticker(ticker)
        if stock is None or not stock.is_active:
            raise APIError("NOT_FOUND", f"ticker {ticker} not in watchlist", 404)
        return stock

    def get_chart(self, raw_ticker: str) -> dict[str, Any]:
        stock = self._resolve_active_stock(raw_ticker)

        bars_stmt = (
            select(DailyBar)
            .where(DailyBar.stock_id == stock.id)
            .order_by(DailyBar.date.desc())
            .limit(CHART_WINDOW_DAYS)
        )
        bars_desc = list(self.db.execute(bars_stmt).scalars().all())
        bars_asc = list(reversed(bars_desc))

        ma150_points: list[dict[str, Any]] = []
        if bars_asc:
            earliest = bars_asc[0].date
            signals_stmt = (
                select(Signal)
                .where(
                    Signal.stock_id == stock.id,
                    Signal.date >= earliest,
                    Signal.ma150_value.is_not(None),
                )
                .order_by(Signal.date.asc())
            )
            signals = list(self.db.execute(signals_stmt).scalars().all())
            ma150_points = [
                {"date": s.date, "value": s.ma150_value} for s in signals
            ]

        pullback_markers: list[dict[str, Any]] = []
        if bars_asc:
            earliest = bars_asc[0].date
            pullbacks = self.pullbacks.list_by_stock_since(stock.id, earliest)
            pullback_markers = [
                {"date": p.date, "distancePct": p.distance_pct} for p in pullbacks
            ]

        return {
            "ticker": stock.ticker,
            "bars": [
                {
                    "date": b.date,
                    "open": b.open,
                    "high": b.high,
                    "low": b.low,
                    "close": b.close,
                    "volume": b.volume,
                }
                for b in bars_asc
            ],
            "ma150": ma150_points,
            "pullbackMarkers": pullback_markers,
        }

    def get_pullbacks(self, raw_ticker: str) -> list[dict[str, Any]]:
        stock = self._resolve_active_stock(raw_ticker)
        rows = self.pullbacks.list_by_stock(stock.id)
        return [
            {
                "date": p.date,
                "closePrice": p.close_price,
                "ma150Value": p.ma150_value,
                "distancePct": p.distance_pct,
                "return10d": p.return_10d,
                "return20d": p.return_20d,
                "return30d": p.return_30d,
            }
            for p in rows
        ]

    def get_fundamentals(self, raw_ticker: str) -> dict[str, Any]:
        stock = self._resolve_active_stock(raw_ticker)
        return _mock_fundamentals(stock.ticker)


def _mock_fundamentals(ticker: str) -> dict[str, Any]:
    digest = hashlib.sha1(ticker.encode("utf-8")).digest()

    def pick(offset: int, modulus: int, scale: float, floor: float) -> float:
        return round(floor + (digest[offset] % modulus) * scale, 2)

    pe = pick(0, 60, 0.5, 10.0)
    ps = pick(1, 30, 0.2, 1.0)
    peg = pick(2, 30, 0.1, 0.5)
    # ROCE range 0.05–0.40 (5%–40%). Real calc (EBIT / (Total Assets - Total Current Liabilities))
    # deferred to F103; see DECISIONS D032.
    roce = round(0.05 + (digest[12] % 36) * 0.01, 4)
    fcf = float((int.from_bytes(digest[3:7], "big") % 95_000 + 5_000) * 1_000_000)
    market_cap = float((int.from_bytes(digest[7:12], "big") % 2_500 + 50) * 1_000_000_000)

    return {
        "ticker": ticker,
        "priceToEarnings": pe,
        "priceToSales": ps,
        "peg": peg,
        "roce": roce,
        "freeCashFlow": fcf,
        "marketCap": market_cap,
        "source": FUNDAMENTALS_MOCK_SOURCE,
        "updatedAt": date.today(),
    }
