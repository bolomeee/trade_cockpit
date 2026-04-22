from __future__ import annotations

import logging
import traceback
from typing import Any

from app.external.fmp_client import FmpClient
from app.models import Stock
from app.repositories.stock_repository import StockRepository
from app.repositories.system_log_repository import SystemLogRepository

READY_BAR_THRESHOLD = 150
SEARCH_LIMIT_MAX = 20
SEARCH_LIMIT_DEFAULT = 10
FMP_MATCH_LIMIT = 5

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
    # FMP search endpoints return `symbol`; fall back to `ticker` for resilience.
    value = _extract_field(obj, "symbol") or _extract_field(obj, "ticker")
    return value.upper() if isinstance(value, str) else None


def _extract_exchange(obj: Any) -> Any:
    # FMP: exchangeShortName (e.g. "NASDAQ"); fall back to legacy `primary_exchange`.
    return _extract_field(obj, "exchangeShortName") or _extract_field(obj, "primary_exchange")


def _extract_type(obj: Any) -> Any:
    # FMP `search-symbol` returns `type` (e.g. "stock"/"etf"); pass through.
    return _extract_field(obj, "type")


class WatchlistService:
    def __init__(self, repo: StockRepository, fmp: FmpClient) -> None:
        self.repo = repo
        self.fmp = fmp

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
            results = self.fmp.search_tickers(ticker, limit=FMP_MATCH_LIMIT)
        except Exception as exc:
            raise APIError("EXTERNAL_API_ERROR", f"FMP lookup failed: {exc}", 502) from exc

        match = next(
            (r for r in results if _extract_ticker(r) == ticker),
            None,
        )
        if match is None:
            raise APIError("NOT_FOUND", f"ticker {ticker} not found on FMP", 404)

        name = _extract_field(match, "name") or ticker
        exchange = _extract_exchange(match)

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
            DataRefreshService(self.repo.db, self.fmp).backfill_stock(stock.id)
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
            results = self.fmp.search_tickers(q, limit=capped)
        except Exception as exc:
            raise APIError("EXTERNAL_API_ERROR", f"FMP search failed: {exc}", 502) from exc

        items: list[dict[str, Any]] = []
        for r in results:
            t = _extract_ticker(r)
            if not t:
                continue
            items.append(
                {
                    "ticker": t,
                    "name": _extract_field(r, "name") or "",
                    "exchange": _extract_exchange(r),
                    "type": _extract_type(r),
                }
            )
        return items

    def bulk_add_stocks(self, tickers: list[str]) -> dict[str, Any]:
        seen: set[str] = set()
        added: list[dict[str, Any]] = []
        skipped_duplicate: list[str] = []
        not_found: list[str] = []

        for raw in tickers:
            ticker = raw.strip().upper()
            if not ticker or ticker in seen:
                continue
            seen.add(ticker)

            try:
                stock = self.add_stock(ticker)
                added.append(self.build_created_payload(stock))
            except APIError as exc:
                if exc.code == "DUPLICATE":
                    skipped_duplicate.append(ticker)
                elif exc.code == "NOT_FOUND":
                    not_found.append(ticker)
                else:
                    raise

        return {"added": added, "skipped_duplicate": skipped_duplicate, "not_found": not_found}

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
