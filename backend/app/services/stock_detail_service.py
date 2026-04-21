from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models import DailyBar, Signal
from app.repositories.pullback_repository import PullbackRepository
from app.repositories.stock_repository import StockRepository
from app.services.signal_engine import compute_ma150_series
from app.services.watchlist_service import APIError

CHART_WINDOW_DAYS = 250
MA150_PERIOD = 150
CHART_FALLBACK_LOOKBACK_DAYS = 400
FUNDAMENTALS_SOURCE_FMP = "fmp"


class StockDetailService:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self.db = db
        self.fmp = fmp
        self.stocks = StockRepository(db)
        self.pullbacks = PullbackRepository(db)

    def _resolve_active_stock(self, raw_ticker: str):
        ticker = raw_ticker.strip().upper()
        stock = self.stocks.get_by_ticker(ticker)
        if stock is None or not stock.is_active:
            raise APIError("NOT_FOUND", f"ticker {ticker} not in watchlist", 404)
        return stock

    def get_chart(self, raw_ticker: str) -> dict[str, Any]:
        ticker = raw_ticker.strip().upper()
        stock = self.stocks.get_by_ticker(ticker)
        if stock is not None and stock.is_active:
            return self._chart_from_watchlist(stock)
        return self._chart_from_fmp_fallback(ticker)

    def _chart_from_watchlist(self, stock: Any) -> dict[str, Any]:
        bars_stmt = (
            select(DailyBar)
            .where(DailyBar.stock_id == stock.id)
            .order_by(DailyBar.date.desc())
            .limit(CHART_WINDOW_DAYS)
        )
        bars_desc = list(self.db.execute(bars_stmt).scalars().all())
        bars_asc = list(reversed(bars_desc))

        bars_payload = [
            {
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in bars_asc
        ]

        ma150_points: list[dict[str, Any]] = []
        pullback_markers: list[dict[str, Any]] = []
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
            pullbacks = self.pullbacks.list_by_stock_since(stock.id, earliest)
            pullback_markers = [
                {"date": p.date, "distancePct": p.distance_pct} for p in pullbacks
            ]

        return self._assemble_chart_payload(
            stock.ticker, bars_payload, ma150_points, pullback_markers
        )

    def _chart_from_fmp_fallback(self, ticker: str) -> dict[str, Any]:
        today = date.today()
        from_d = today - timedelta(days=CHART_FALLBACK_LOOKBACK_DAYS)
        try:
            raw = self.fmp.get_daily_bars(ticker, from_d, today)
        except httpx.HTTPError as exc:
            raise APIError(
                "EXTERNAL_API_ERROR",
                f"FMP chart fetch failed for {ticker}: {exc}",
                502,
            ) from exc

        if not raw:
            raise APIError("NOT_FOUND", f"ticker {ticker} not found", 404)

        normalized = [_normalize_fmp_bar(b) for b in raw]
        bars_asc = sorted(normalized, key=lambda b: b["date"])[-CHART_WINDOW_DAYS:]

        closes = [b["close"] for b in bars_asc]
        ma_series = compute_ma150_series(closes)
        ma150_points = [
            {"date": bars_asc[i]["date"], "value": v}
            for i, v in enumerate(ma_series)
            if v is not None
        ]

        return self._assemble_chart_payload(ticker, bars_asc, ma150_points, [])

    @staticmethod
    def _assemble_chart_payload(
        ticker: str,
        bars: list[dict[str, Any]],
        ma150: list[dict[str, Any]],
        pullback_markers: list[dict[str, Any]],
    ) -> dict[str, Any]:
        return {
            "ticker": ticker,
            "bars": bars,
            "ma150": ma150,
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
        try:
            ratios = self.fmp.get_ratios_ttm(stock.ticker) or {}
            km = self.fmp.get_key_metrics_ttm(stock.ticker) or {}
        except httpx.HTTPError as exc:
            raise APIError(
                "EXTERNAL_API_ERROR",
                f"FMP fundamentals fetch failed: {exc}",
                502,
            ) from exc

        market_cap = _as_float(km.get("marketCap"))
        fcf_yield = _as_float(km.get("freeCashFlowYieldTTM"))
        free_cash_flow = (
            market_cap * fcf_yield
            if market_cap is not None and fcf_yield is not None
            else None
        )

        return {
            "ticker": stock.ticker,
            "priceToEarnings": _as_float(ratios.get("priceToEarningsRatioTTM")),
            "priceToSales": _as_float(ratios.get("priceToSalesRatioTTM")),
            "peg": _as_float(ratios.get("priceToEarningsGrowthRatioTTM")),
            "roce": _as_float(km.get("returnOnCapitalEmployedTTM")),
            "freeCashFlow": free_cash_flow,
            "marketCap": market_cap,
            "source": FUNDAMENTALS_SOURCE_FMP,
            "updatedAt": date.today(),
        }


def _normalize_fmp_bar(b: dict[str, Any]) -> dict[str, Any]:
    raw_date = b["date"]
    d = raw_date if isinstance(raw_date, date) else date.fromisoformat(str(raw_date)[:10])
    return {
        "date": d,
        "open": float(b["open"]),
        "high": float(b["high"]),
        "low": float(b["low"]),
        "close": float(b["close"]),
        "volume": int(b.get("volume") or 0),
    }


def _as_float(v: Any) -> float | None:
    if v is None:
        return None
    try:
        return float(v)
    except (TypeError, ValueError):
        return None
