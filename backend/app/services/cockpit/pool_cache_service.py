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
from app.repositories.fundamentals_repository import FundamentalsRepository
from app.repositories.key_metrics_repository import KeyMetricsRepository
from app.repositories.market_breakout_repository import MarketBreakoutRepository
from app.repositories.system_log_repository import SystemLogRepository
from app.services.cockpit.pool_helpers import (
    compute_fundamentals_row_from_balance_cash,
    compute_key_metrics_row_from_income_statement,
    compute_return_ratio_250d,
    compute_rs_percentile_map,
    compute_supplemental_key_metrics_from_is_bs_cf,
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
        self._key_metrics_repo = KeyMetricsRepository(db)
        self._fundamentals_repo = FundamentalsRepository(db)

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

            elapsed_cockpit = time.monotonic() - t0
            self._log_repo.create(
                "OK", "pool_cache",
                f"rebuilt N={len(rows)} elapsed={elapsed_cockpit:.1f}s",
            )

            km_upserted, is_by_ticker = self._rebuild_key_metrics(tickers)
            elapsed_km = time.monotonic() - t0
            self._log_repo.create(
                "OK", "pool_cache",
                f"key_metrics upserted={km_upserted} elapsed={elapsed_km:.1f}s",
            )

            fund_upserted, supp_km_upserted = self._rebuild_fundamentals(tickers, is_by_ticker)
            elapsed = time.monotonic() - t0
            self._log_repo.create(
                "OK", "pool_cache",
                f"fundamentals upserted={fund_upserted} supplemental_key_metrics upserted={supp_km_upserted} elapsed={elapsed:.1f}s",
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

    def _fetch_income_statement_concurrent(
        self, tickers: list[str],
    ) -> dict[str, list[dict]]:
        """Fetch quarterly income-statements for all tickers concurrently (fail-open per ticker)."""
        def _one(ticker: str) -> tuple[str, list[dict]]:
            try:
                return ticker, self._fmp.get_income_statement_quarterly(ticker)
            except Exception:
                return ticker, []

        result: dict[str, list[dict]] = {}
        with ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS) as executor:
            futures = {executor.submit(_one, t): t for t in tickers}
            for future in as_completed(futures):
                ticker, records = future.result()
                result[ticker] = records
        return result

    def _rebuild_key_metrics(
        self, tickers: list[str],
    ) -> tuple[int, dict[str, list[dict]]]:
        """Fetch income-statements and upsert key_metrics rows for all pool tickers.

        Fails open per ticker: FMP errors / empty responses skip that ticker without
        aborting the batch.
        Returns (upserted_count, income_statements_by_ticker) — IS dict passed to
        _rebuild_fundamentals to avoid re-fetching the same endpoint (NP-d6a-4).
        """
        statements_by_ticker = self._fetch_income_statement_concurrent(tickers)
        upserted = 0
        for ticker, records in statements_by_ticker.items():
            for record in records:
                row = compute_key_metrics_row_from_income_statement(record)
                if row is None:
                    continue
                try:
                    self._key_metrics_repo.upsert(row)
                    upserted += 1
                except Exception as exc:
                    logger.warning("key_metrics upsert failed ticker=%s: %s", ticker, exc)
        return upserted, statements_by_ticker

    def _fetch_balance_sheet_concurrent(
        self, tickers: list[str],
    ) -> dict[str, list[dict]]:
        """Fetch quarterly balance-sheets for all tickers concurrently (fail-open per ticker)."""
        def _one(ticker: str) -> tuple[str, list[dict]]:
            try:
                return ticker, self._fmp.get_balance_sheet_quarterly(ticker)
            except Exception:
                return ticker, []

        result: dict[str, list[dict]] = {}
        with ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS) as executor:
            futures = {executor.submit(_one, t): t for t in tickers}
            for future in as_completed(futures):
                ticker, records = future.result()
                result[ticker] = records
        return result

    def _fetch_cash_flow_concurrent(
        self, tickers: list[str],
    ) -> dict[str, list[dict]]:
        """Fetch quarterly cash-flow statements for all tickers concurrently (fail-open per ticker)."""
        def _one(ticker: str) -> tuple[str, list[dict]]:
            try:
                return ticker, self._fmp.get_cash_flow_quarterly(ticker)
            except Exception:
                return ticker, []

        result: dict[str, list[dict]] = {}
        with ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS) as executor:
            futures = {executor.submit(_one, t): t for t in tickers}
            for future in as_completed(futures):
                ticker, records = future.result()
                result[ticker] = records
        return result

    def _rebuild_fundamentals(
        self,
        tickers: list[str],
        income_statements_by_ticker: dict[str, list[dict]],
    ) -> tuple[int, int]:
        """Pair IS/BS/CF by fiscal_quarter and upsert; fail-open per ticker (NP-d6a-4/8)."""
        bs_by_ticker = self._fetch_balance_sheet_concurrent(tickers)
        cf_by_ticker = self._fetch_cash_flow_concurrent(tickers)
        _qk = lambda r: f"{r.get('period', '')} {r.get('fiscalYear', '')}"
        fund_upserted = 0
        supp_km_upserted = 0
        for ticker in tickers:
            bs_records = bs_by_ticker.get(ticker, [])
            cf_records = cf_by_ticker.get(ticker, [])
            is_records = income_statements_by_ticker.get(ticker, [])
            if not bs_records or not cf_records:
                continue
            cf_by_quarter = {_qk(r): r for r in cf_records}
            is_by_quarter = {_qk(r): r for r in is_records}
            for bs_record in bs_records:
                q = _qk(bs_record)
                cf_record = cf_by_quarter.get(q)
                if cf_record is None:
                    continue
                fund_row = compute_fundamentals_row_from_balance_cash(bs_record, cf_record)
                if fund_row is not None:
                    try:
                        self._fundamentals_repo.upsert(fund_row)
                        fund_upserted += 1
                    except Exception as exc:
                        logger.warning("fundamentals upsert failed ticker=%s q=%s: %s", ticker, q, exc)
                is_record = is_by_quarter.get(q)
                if is_record is not None:
                    supp_row = compute_supplemental_key_metrics_from_is_bs_cf(
                        is_record, bs_record, cf_record
                    )
                    if supp_row is not None:
                        try:
                            self._key_metrics_repo.upsert(supp_row)
                            supp_km_upserted += 1
                        except Exception as exc:
                            logger.warning("supplemental km upsert failed ticker=%s q=%s: %s", ticker, q, exc)
        return fund_upserted, supp_km_upserted
