"""F105 daily market breakout scanner (D039/D040/D042).

Reads the active universe, fetches MA150 series per ticker from FMP (SMA
primary / EOD fallback handled transparently by the client), applies the
breakout rule (prev_close<prev_ma, close>=ma, pct<=10, slope>0) and
overwrites the `market_breakout_scans` snapshot in a single transaction.

Per-ticker failures are isolated. If every ticker fails the old snapshot is
preserved (D040); the only "clear" paths are:
  - at least one ticker scanned OK (hits may be 0 → snapshot becomes empty)
  - the active universe is empty and cold-start refresh succeeded with rows
"""
from __future__ import annotations

import traceback
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Protocol

from sqlalchemy.orm import Session

from app.models.market_scan_universe import MarketScanUniverse
from app.repositories.market_breakout_repository import (
    BreakoutScanRow,
    MarketBreakoutRepository,
)
from app.repositories.market_scan_universe_repository import (
    MarketScanUniverseRepository,
)
from app.repositories.system_log_repository import SystemLogRepository
from app.services.signal_engine import SLOPE_WINDOW, compute_ma150_series, compute_slope
from app.services.universe_refresh_service import UniverseRefreshService

LOG_SOURCE = "market_scanner"
PCT_ABOVE_MA_LIMIT = 10.0


class _FmpClientLike(Protocol):
    def get_screener_universe(
        self,
        market_cap_gte: int = ...,
        exchanges: tuple[str, ...] = ...,
        limit_per_exchange: int = ...,
    ) -> list[dict[str, Any]]: ...

    def get_ma150_series_or_eod(self, symbol: str) -> dict[str, Any]: ...


@dataclass
class ScannerResult:
    status: str  # "ok" | "error"
    total: int
    scanned: int
    hits: int
    failed: int
    fallback_used: bool
    scan_date: date
    scanned_at: datetime
    error: str | None = None


class MarketScannerService:
    def __init__(self, db: Session, fmp: _FmpClientLike) -> None:
        self.db = db
        self.fmp = fmp
        self.universe_repo = MarketScanUniverseRepository(db)
        self.breakout_repo = MarketBreakoutRepository(db)
        self.log_repo = SystemLogRepository(db)

    def run_scan(self, scan_date: date | None = None) -> ScannerResult:
        scanned_at = datetime.now(timezone.utc)
        today = scan_date or scanned_at.date()

        # Cold start (D038): empty table → trigger one universe refresh.
        if self.universe_repo.count() == 0:
            refresh_result = UniverseRefreshService(self.db, self.fmp).refresh()
            if refresh_result.status != "ok":
                self.log_repo.create(
                    level="ERROR",
                    source=LOG_SOURCE,
                    message=f"cold-start universe refresh failed: {refresh_result.error}",
                )
                return ScannerResult(
                    status="error",
                    total=0, scanned=0, hits=0, failed=0,
                    fallback_used=False,
                    scan_date=today, scanned_at=scanned_at,
                    error=refresh_result.error,
                )

        latest = self.universe_repo.latest_refresh_time()
        if latest is None:
            # refresh succeeded but table still empty → treat as empty universe, no-op
            self.log_repo.create(
                level="OK",
                source=LOG_SOURCE,
                message="scan complete: universe empty",
            )
            return ScannerResult(
                status="ok", total=0, scanned=0, hits=0, failed=0,
                fallback_used=False, scan_date=today, scanned_at=scanned_at,
            )
        active = self.universe_repo.list_active(since=latest)

        hits: list[BreakoutScanRow] = []
        scanned_ok = 0
        failed = 0
        fallback_used = False
        fallback_logged = False

        for row in active:
            try:
                payload = self.fmp.get_ma150_series_or_eod(row.ticker)
                source = payload.get("source")
                bars = payload.get("bars") or []
                if source == "eod_fallback":
                    fallback_used = True
                    if not fallback_logged:
                        self.log_repo.create(
                            level="WARN",
                            source=LOG_SOURCE,
                            message="SMA endpoint unavailable, falling back to EOD",
                        )
                        fallback_logged = True

                hit = _evaluate_breakout(row, bars, source, scan_date=today, scanned_at=scanned_at)
                if hit is not None:
                    hits.append(hit)
                scanned_ok += 1
            except Exception as exc:  # noqa: BLE001 — isolate per-ticker
                self.log_repo.create(
                    level="ERROR",
                    source=LOG_SOURCE,
                    message=f"{row.ticker} scan failed: {exc}",
                    detail=traceback.format_exc(),
                )
                failed += 1
                continue

        # D040: if every active ticker failed, do NOT clear old snapshot.
        if len(active) > 0 and scanned_ok == 0:
            self.log_repo.create(
                level="ERROR",
                source=LOG_SOURCE,
                message=f"scan aborted: all {failed} tickers failed; old snapshot preserved",
            )
            return ScannerResult(
                status="error",
                total=len(active), scanned=0, hits=0, failed=failed,
                fallback_used=fallback_used,
                scan_date=today, scanned_at=scanned_at,
                error="all tickers failed",
            )

        self.breakout_repo.replace_scan(hits)

        self.log_repo.create(
            level="OK",
            source=LOG_SOURCE,
            message=(
                f"scan complete: hits={len(hits)} scanned={scanned_ok} "
                f"failed={failed} fallback={fallback_used}"
            ),
        )
        return ScannerResult(
            status="ok",
            total=len(active), scanned=scanned_ok, hits=len(hits), failed=failed,
            fallback_used=fallback_used,
            scan_date=today, scanned_at=scanned_at,
        )


def _evaluate_breakout(
    universe_row: MarketScanUniverse,
    bars: list[Any],
    source: Any,
    *,
    scan_date: date,
    scanned_at: datetime,
) -> BreakoutScanRow | None:
    """Pure breakout check. Returns row on hit, None otherwise.

    Raises on malformed bar payloads — caller catches and logs ERROR.
    """
    sorted_bars = sorted(bars, key=lambda b: str(_get(b, "date") or ""))
    if len(sorted_bars) < 2:
        return None

    closes = [float(_get(b, "close")) for b in sorted_bars]

    if source == "sma":
        ma_series: list[float | None] = []
        for b in sorted_bars:
            raw = _get(b, "sma")
            ma_series.append(float(raw) if raw is not None else None)
    else:
        ma_series = compute_ma150_series(closes)

    close_today = closes[-1]
    close_prev = closes[-2]
    ma_today = ma_series[-1]
    ma_prev = ma_series[-2]
    if ma_today is None or ma_prev is None:
        return None

    # Rule 1: upward cross
    if not (close_prev < ma_prev and close_today >= ma_today):
        return None

    # Rule 2: pct above MA within 10%
    pct_above = (close_today - ma_today) / ma_today * 100.0
    if pct_above > PCT_ABOVE_MA_LIMIT:
        return None

    # Rule 3: MA150 slope positive (last SLOPE_WINDOW non-None values)
    ma_non_null = [v for v in ma_series if v is not None]
    if len(ma_non_null) < SLOPE_WINDOW:
        return None
    slope = compute_slope(ma_non_null)
    if slope is None or slope <= 0:
        return None

    return BreakoutScanRow(
        scan_date=scan_date,
        ticker=universe_row.ticker,
        company_name=universe_row.company_name,
        close_price=close_today,
        ma150_value=ma_today,
        pct_above_ma150=pct_above,
        slope_value=slope,
        market_cap=int(universe_row.market_cap),
        scanned_at=scanned_at,
    )


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
