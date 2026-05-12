"""D041: shared last-close loader — daily_bars batch + serial FMP fallback."""
from __future__ import annotations

import logging
from datetime import date, timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.daily_bar import DailyBar
from app.models.stock import Stock

logger = logging.getLogger(__name__)

_FMP_LOOKBACK_DAYS = 30


class LastCloseLoader:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self._db = db
        self._fmp = fmp

    def load(self, tickers: list[str]) -> dict[str, float | None]:
        """D041: batch close from daily_bars for watchlist tickers; serial FMP for others."""
        if not tickers:
            return {}

        result: dict[str, float | None] = {t: None for t in tickers}

        # Step 1: find which tickers are in stocks (watchlist)
        stocks_q = self._db.execute(
            select(Stock.ticker, Stock.id).where(Stock.ticker.in_(tickers))
        ).all()
        watchlist_map: dict[int, str] = {row.id: row.ticker for row in stocks_q}
        watchlist_tickers: set[str] = {row.ticker for row in stocks_q}

        # Step 2: batch query latest close from daily_bars for watchlist stocks
        if watchlist_map:
            stock_ids = list(watchlist_map.keys())
            subq = (
                select(DailyBar.stock_id, func.max(DailyBar.date).label("max_date"))
                .where(DailyBar.stock_id.in_(stock_ids))
                .group_by(DailyBar.stock_id)
                .subquery()
            )
            bars = self._db.execute(
                select(DailyBar.stock_id, DailyBar.close)
                .join(
                    subq,
                    (DailyBar.stock_id == subq.c.stock_id)
                    & (DailyBar.date == subq.c.max_date),
                )
            ).all()
            for bar in bars:
                ticker = watchlist_map[bar.stock_id]
                result[ticker] = bar.close

        # Step 3: serial FMP fallback for non-watchlist tickers
        non_watchlist = [t for t in tickers if t not in watchlist_tickers]
        for ticker in non_watchlist:
            result[ticker] = self._fmp_latest_close(ticker)

        return result

    def _fmp_latest_close(self, ticker: str) -> float | None:
        """Fetch the most recent EOD close from FMP (D041, not written to DB)."""
        today = date.today()
        from_date = today - timedelta(days=_FMP_LOOKBACK_DAYS)
        try:
            raw = self._fmp.get_daily_bars(ticker, from_date, today)
        except Exception:
            logger.warning("FMP fallback failed for %s", ticker)
            return None
        if not raw:
            return None
        last = sorted(raw, key=lambda b: b.get("date", ""))[-1]
        close = last.get("close") or last.get("adjClose")
        if close is None:
            return None
        return float(close)
