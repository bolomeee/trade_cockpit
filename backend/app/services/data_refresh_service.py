"""Data refresh core: backfill, incremental update, and batch orchestration.

Pulls EOD daily bars from Polygon.io, persists via DailyBarRepository,
prunes to the 250-day window, triggers signal recomputation, and writes
SystemLog entries for success/failure.

Does NOT expose HTTP, does NOT schedule. F003-b wires those.
"""
from __future__ import annotations

import traceback
from datetime import date, datetime, timedelta, timezone
from typing import Any, TypedDict

from sqlalchemy.orm import Session

from app.external.polygon_client import PolygonClient
from app.models import Stock
from app.repositories.daily_bar_repository import (
    DAILY_BAR_WINDOW,
    BarDTO,
    DailyBarRepository,
)
from app.repositories.stock_repository import StockRepository
from app.repositories.system_log_repository import SystemLogRepository
from app.services.signal_service import SignalService

BACKFILL_DEFAULT_DAYS = 250
BACKFILL_CALENDAR_MULTIPLIER = 2  # calendar days ≈ 2× trading days
LOG_SOURCE = "data_refresh"


class RefreshResult(TypedDict):
    stock_id: int
    ticker: str
    bars_added: int
    status: str  # "ok" | "error"
    error: str | None


class BatchResult(TypedDict):
    total: int
    completed: int
    failed: int
    results: list[RefreshResult]


class DataRefreshService:
    def __init__(
        self,
        db: Session,
        polygon: PolygonClient,
        signal_service: SignalService | None = None,
    ) -> None:
        self.db = db
        self.polygon = polygon
        self.bar_repo = DailyBarRepository(db)
        self.stock_repo = StockRepository(db)
        self.log_repo = SystemLogRepository(db)
        self.signal_service = signal_service or SignalService(db)

    def backfill_stock(self, stock_id: int, days: int = BACKFILL_DEFAULT_DAYS) -> RefreshResult:
        stock = self.db.get(Stock, stock_id)
        if stock is None:
            raise ValueError(f"stock {stock_id} not found")

        today = _today_utc()
        from_date = today - timedelta(days=days * BACKFILL_CALENDAR_MULTIPLIER)
        return self._fetch_and_persist(stock, from_date, today, prune=True)

    def increment_stock(self, stock_id: int) -> RefreshResult:
        stock = self.db.get(Stock, stock_id)
        if stock is None:
            raise ValueError(f"stock {stock_id} not found")

        latest = self.bar_repo.get_latest_date(stock_id)
        today = _today_utc()
        if latest is None:
            return self.backfill_stock(stock_id)

        from_date = latest + timedelta(days=1)
        if from_date > today:
            # nothing to fetch; still recompute signals (idempotent) and return ok
            self.signal_service.recompute_for_stock(stock_id)
            _touch_last_refreshed(self.db, stock)
            return RefreshResult(
                stock_id=stock_id,
                ticker=stock.ticker,
                bars_added=0,
                status="ok",
                error=None,
            )
        return self._fetch_and_persist(stock, from_date, today, prune=True)

    def refresh_all(self, stock_ids: list[int]) -> BatchResult:
        results: list[RefreshResult] = []
        completed = 0
        failed = 0
        for sid in stock_ids:
            try:
                r = self.increment_stock(sid)
            except Exception as exc:  # noqa: BLE001 — isolate per-stock failure
                stock = self.db.get(Stock, sid)
                ticker = stock.ticker if stock else f"<id={sid}>"
                self.log_repo.create(
                    level="ERROR",
                    source=LOG_SOURCE,
                    message=f"{ticker} refresh failed: {exc}",
                    detail=traceback.format_exc(),
                )
                results.append(
                    RefreshResult(
                        stock_id=sid,
                        ticker=ticker,
                        bars_added=0,
                        status="error",
                        error=str(exc),
                    )
                )
                failed += 1
                continue

            if r["status"] == "ok":
                self.log_repo.create(
                    level="OK",
                    source=LOG_SOURCE,
                    message=f"{r['ticker']} refreshed ({r['bars_added']} bars)",
                )
                completed += 1
            else:
                self.log_repo.create(
                    level="ERROR",
                    source=LOG_SOURCE,
                    message=f"{r['ticker']} refresh failed: {r['error']}",
                )
                failed += 1
            results.append(r)

        return BatchResult(
            total=len(stock_ids),
            completed=completed,
            failed=failed,
            results=results,
        )

    def purge_old_logs(self) -> int:
        return self.log_repo.purge_older_than()

    # ----- internal -----

    def _fetch_and_persist(
        self,
        stock: Stock,
        from_date: date,
        to_date: date,
        *,
        prune: bool,
    ) -> RefreshResult:
        aggs = self.polygon.get_daily_aggs(stock.ticker, from_date, to_date)
        bars = [b for b in (_agg_to_bar(a) for a in aggs) if b is not None]
        added = self.bar_repo.bulk_upsert(stock.id, bars)
        if prune:
            self.bar_repo.prune_to_window(stock.id, DAILY_BAR_WINDOW)
        self.signal_service.recompute_for_stock(stock.id)
        _touch_last_refreshed(self.db, stock)
        return RefreshResult(
            stock_id=stock.id,
            ticker=stock.ticker,
            bars_added=added,
            status="ok",
            error=None,
        )


def _today_utc() -> date:
    return datetime.now(timezone.utc).date()


def _touch_last_refreshed(db: Session, stock: Stock) -> None:
    stock.last_refreshed_at = datetime.now(timezone.utc)
    db.commit()


def _agg_to_bar(agg: Any) -> BarDTO | None:
    """Convert a polygon Agg (either dict or object) to a BarDTO.

    Polygon returns `timestamp` in ms (UTC). We map:
      t (ms) → date, o/h/l/c → open/high/low/close, v → volume.
    Returns None when any required field is missing (defensive against SDK drift).
    """
    ts_ms = _get(agg, "timestamp")
    if ts_ms is None:
        return None
    try:
        d = datetime.fromtimestamp(ts_ms / 1000, tz=timezone.utc).date()
    except (TypeError, ValueError, OSError):
        return None

    o = _get(agg, "open")
    h = _get(agg, "high")
    low_v = _get(agg, "low")
    c = _get(agg, "close")
    v = _get(agg, "volume")
    if None in (o, h, low_v, c, v):
        return None

    return BarDTO(
        date=d,
        open=float(o),
        high=float(h),
        low=float(low_v),
        close=float(c),
        volume=int(v),
    )


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
