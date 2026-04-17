from __future__ import annotations

import logging
import traceback
from typing import Any

from app.external.polygon_client import PolygonClient
from app.models import Stock
from app.repositories.stock_repository import StockRepository
from app.repositories.system_log_repository import SystemLogRepository

READY_BAR_THRESHOLD = 150
SEARCH_LIMIT_MAX = 20
SEARCH_LIMIT_DEFAULT = 10
POLYGON_MATCH_LIMIT = 5

logger = logging.getLogger(__name__)


class APIError(Exception):
    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def derive_data_status(bar_count: int) -> str:
    if bar_count <= 0:
        return "loading"
    if bar_count < READY_BAR_THRESHOLD:
        return "insufficient"
    return "ready"


def _extract_field(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)


def _extract_ticker(obj: Any) -> str | None:
    value = _extract_field(obj, "ticker")
    return value.upper() if isinstance(value, str) else None


class WatchlistService:
    def __init__(self, repo: StockRepository, polygon: PolygonClient) -> None:
        self.repo = repo
        self.polygon = polygon

    def list_watchlist(self) -> list[dict[str, Any]]:
        stocks = self.repo.list_active()
        items: list[dict[str, Any]] = []
        for stock in stocks:
            bar_count = self.repo.count_bars(stock.id)
            items.append(
                {
                    "id": stock.id,
                    "ticker": stock.ticker,
                    "name": stock.name,
                    "exchange": stock.exchange,
                    "added_at": stock.added_at,
                    "last_refreshed_at": stock.last_refreshed_at,
                    "data_status": derive_data_status(bar_count),
                    "latest_signal": None,
                }
            )
        return items

    def add_stock(self, raw_ticker: str) -> Stock:
        ticker = raw_ticker.strip().upper()
        if not ticker:
            raise APIError("VALIDATION_ERROR", "ticker is required", 422)

        existing = self.repo.get_by_ticker(ticker)
        if existing and existing.is_active:
            raise APIError("DUPLICATE", f"{ticker} already in watchlist", 409)

        try:
            results = self.polygon.search_tickers(ticker, limit=POLYGON_MATCH_LIMIT)
        except Exception as exc:
            raise APIError("EXTERNAL_API_ERROR", f"Polygon lookup failed: {exc}", 502) from exc

        match = next(
            (r for r in results if _extract_ticker(r) == ticker),
            None,
        )
        if match is None:
            raise APIError("NOT_FOUND", f"ticker {ticker} not found on Polygon", 404)

        name = _extract_field(match, "name") or ticker
        exchange = _extract_field(match, "primary_exchange")

        if existing and not existing.is_active:
            stock = self.repo.reactivate(existing, name=name, exchange=exchange)
        else:
            stock = self.repo.create(ticker=ticker, name=name, exchange=exchange)

        self._backfill_silently(stock)
        return stock

    def _backfill_silently(self, stock: Stock) -> None:
        """Trigger 250-day backfill; failures are logged but do not fail the POST.

        Deferred import avoids a cycle: DataRefreshService → SignalService →
        (indirect) WatchlistService.APIError.
        """
        from app.services.data_refresh_service import DataRefreshService

        try:
            DataRefreshService(self.repo.db, self.polygon).backfill_stock(stock.id)
        except Exception as exc:  # noqa: BLE001 — boundary
            logger.warning("backfill failed for %s: %s", stock.ticker, exc)
            try:
                SystemLogRepository(self.repo.db).create(
                    level="WARN",
                    source="watchlist",
                    message=f"{stock.ticker} backfill failed: {exc}",
                    detail=traceback.format_exc(),
                )
            except Exception:  # noqa: BLE001
                pass

    def remove_stock(self, raw_ticker: str) -> str:
        ticker = raw_ticker.strip().upper()
        stock = self.repo.get_by_ticker(ticker)
        if stock is None or not stock.is_active:
            raise APIError("NOT_FOUND", f"ticker {ticker} not in watchlist", 404)
        self.repo.soft_delete(stock)
        return ticker

    def search(self, q: str, limit: int) -> list[dict[str, Any]]:
        capped = min(max(1, limit), SEARCH_LIMIT_MAX)
        try:
            results = self.polygon.search_tickers(q, limit=capped)
        except Exception as exc:
            raise APIError("EXTERNAL_API_ERROR", f"Polygon search failed: {exc}", 502) from exc

        items: list[dict[str, Any]] = []
        for r in results:
            t = _extract_ticker(r)
            if not t:
                continue
            items.append(
                {
                    "ticker": t,
                    "name": _extract_field(r, "name") or "",
                    "exchange": _extract_field(r, "primary_exchange"),
                    "type": _extract_field(r, "type"),
                }
            )
        return items

    def build_created_payload(self, stock: Stock) -> dict[str, Any]:
        bar_count = self.repo.count_bars(stock.id)
        return {
            "id": stock.id,
            "ticker": stock.ticker,
            "name": stock.name,
            "exchange": stock.exchange,
            "added_at": stock.added_at,
            "data_status": derive_data_status(bar_count),
        }
