"""F205-e: PoolCacheService — weekly rebuild of RS + fundamental cache (Q1=A: trend-only).

Caches only tickers currently in the trend snapshot (~50).
Called by the weekly cron (Mon 06:30 UTC) and the admin endpoint (Q5=B).
"""
from __future__ import annotations

import logging
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timedelta, timezone

from sqlalchemy import delete
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.cockpit_pool_cache import CockpitPoolCache
from app.repositories.market_breakout_repository import MarketBreakoutRepository
from app.repositories.system_log_repository import SystemLogRepository
from app.services.cockpit.pool_helpers import (
    compute_return_ratio_250d,
    compute_rs_percentile_map,
    extract_revenue_growth_yoy_pct,
)

logger = logging.getLogger(__name__)

_FMP_MAX_WORKERS: int = 6
_BARS_LOOKBACK_DAYS: int = 400  # ~280 trading days, guarantees ≥250 for RS computation


@dataclass
class PoolCacheResult:
    status: str          # "ok" | "error"
    upserted: int
    elapsed_seconds: float
    error: str | None = None


class PoolCacheService:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self._db = db
        self._fmp = fmp
        self._breakout_repo = MarketBreakoutRepository(db)
        self._log_repo = SystemLogRepository(db)

    def rebuild(self) -> PoolCacheResult:
        """Rebuild the pool cache from the latest trend snapshot.

        Transaction: DELETE all rows → INSERT new rows atomically.
        On any exception the transaction is rolled back and ERROR is logged.
        """
        t0 = time.monotonic()
        try:
            tickers = self._load_trend_tickers()
            if not tickers:
                self._log_repo.create(
                    "WARN", "pool_cache",
                    "rebuild skipped: no trend tickers in latest breakout snapshot",
                )
                return PoolCacheResult(status="ok", upserted=0, elapsed_seconds=time.monotonic() - t0)

            today = date.today()
            from_date = today - timedelta(days=_BARS_LOOKBACK_DAYS)

            # SPY closes for RS ratio denominator
            try:
                spy_bars = self._fmp.get_daily_bars("SPY", from_date, today)
            except Exception:
                spy_bars = []
            spy_closes = [b["close"] for b in sorted(spy_bars, key=lambda b: b.get("date", ""))]

            closes_by_ticker = self._fetch_bars_concurrent(tickers, from_date, today)

            # Only tickers with successful bars enter the percentile map
            ratio_by_ticker = {
                t: compute_return_ratio_250d(closes_by_ticker[t], spy_closes)
                for t in tickers
                if t in closes_by_ticker
            }
            percentile_map = compute_rs_percentile_map(ratio_by_ticker)

            growth_by_ticker = self._fetch_growth_concurrent(tickers)

            # Build rows — exclude tickers where bars completely failed
            now = datetime.now(timezone.utc)
            rows = []
            for ticker in tickers:
                if ticker not in closes_by_ticker:
                    continue
                closes = closes_by_ticker[ticker]
                ma50 = sum(closes[-50:]) / 50 if len(closes) >= 50 else None
                last_close = closes[-1] if closes else None
                rows.append(CockpitPoolCache(
                    ticker=ticker,
                    rs_percentile=percentile_map.get(ticker, 0.0),
                    ma50=ma50,
                    last_close=last_close,
                    revenue_growth_yoy=growth_by_ticker.get(ticker),
                    computed_at=now,
                ))

            self._db.execute(delete(CockpitPoolCache))
            for row in rows:
                self._db.add(row)
            self._db.commit()

            elapsed = time.monotonic() - t0
            self._log_repo.create(
                "OK", "pool_cache",
                f"rebuilt N={len(rows)} elapsed={elapsed:.1f}s",
            )
            return PoolCacheResult(status="ok", upserted=len(rows), elapsed_seconds=elapsed)

        except Exception as exc:
            self._db.rollback()
            elapsed = time.monotonic() - t0
            logger.error("pool cache rebuild failed", exc_info=True)
            try:
                self._log_repo.create("ERROR", "pool_cache", f"rebuild failed: {exc}"[:500])
            except Exception:
                pass
            return PoolCacheResult(
                status="error", upserted=0, elapsed_seconds=elapsed, error=str(exc)
            )

    # ── private helpers ───────────────────────────────────────────────────────

    def _load_trend_tickers(self) -> list[str]:
        snapshot = self._breakout_repo.get_latest_snapshot()
        if snapshot is None:
            return []
        # snapshot may have multiple rows per ticker (different signal_types); deduplicate
        return list(dict.fromkeys(item.ticker for item in snapshot.items))

    def _fetch_bars_concurrent(
        self, tickers: list[str], from_date: date, to_date: date
    ) -> dict[str, list[float]]:
        def _one(ticker: str) -> tuple[str, list[float] | None]:
            try:
                bars = self._fmp.get_daily_bars(ticker, from_date, to_date)
                if not bars:
                    return ticker, None
                return ticker, [b["close"] for b in sorted(bars, key=lambda b: b.get("date", ""))]
            except Exception:
                return ticker, None

        result: dict[str, list[float]] = {}
        with ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS) as executor:
            futures = {executor.submit(_one, t): t for t in tickers}
            for future in as_completed(futures):
                ticker, closes = future.result()
                if closes is not None:
                    result[ticker] = closes
        return result

    def _fetch_growth_concurrent(self, tickers: list[str]) -> dict[str, float | None]:
        def _one(ticker: str) -> tuple[str, float | None]:
            try:
                payload = self._fmp.get_financial_growth(ticker)
                return ticker, extract_revenue_growth_yoy_pct(payload)
            except Exception:
                return ticker, None

        result: dict[str, float | None] = {}
        with ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS) as executor:
            futures = {executor.submit(_one, t): t for t in tickers}
            for future in as_completed(futures):
                ticker, growth = future.result()
                result[ticker] = growth
        return result
