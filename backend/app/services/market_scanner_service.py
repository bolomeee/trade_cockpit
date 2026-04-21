"""F106 multi-signal daily market scanner.

Per ticker we fetch a single SMA-series (or EOD fallback) and evaluate four
independent rules on the same bar sequence, emitting one row per hit:

  - legacy_crossover    (F105 original rule, kept for baseline; not in default API response)
  - a1_stage_breakout   (Stage 1 → 2: long horizontal MA150, first crossover + volume)
  - a2_slope_flip       (MA150 slope recently flipped from ≤0 to >0, close above MA150)
  - b2_ma_pullback      (MA5 dipped near MA150 in recent window, now re-expanding upward)

All thresholds live in scanner_params.py; logic here is structural only.

Per-ticker failures are isolated. If every ticker fails the old snapshot is
preserved (D040). Concurrency model (D044) unchanged: ThreadPoolExecutor with
SCAN_WORKER_COUNT workers sharing the process-level FMP rate limiter.
"""
from __future__ import annotations

import threading
import time
import traceback
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import date, datetime, timezone
from typing import Any, Callable, Protocol

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
from app.services import scanner_params as P
from app.services.signal_engine import SLOPE_WINDOW, compute_ma150_series, compute_slope
from app.services.universe_refresh_service import UniverseRefreshService

LOG_SOURCE = "market_scanner"


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
    hits_by_type: dict[str, int]
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
        empty_counts = {stype: 0 for stype in P.ALL_SIGNAL_TYPES}

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
                    hits_by_type=empty_counts,
                    error=refresh_result.error,
                )

        latest = self.universe_repo.latest_refresh_time()
        if latest is None:
            self.log_repo.create(
                level="OK",
                source=LOG_SOURCE,
                message="scan complete: universe empty",
            )
            return ScannerResult(
                status="ok", total=0, scanned=0, hits=0, failed=0,
                fallback_used=False, scan_date=today, scanned_at=scanned_at,
                hits_by_type=empty_counts,
            )
        active = self.universe_repo.list_active(since=latest)
        scan_start = time.monotonic()

        hits: list[BreakoutScanRow] = []
        scanned_ok = 0
        failed = 0
        fallback_used = False
        fallback_logged = False
        pending_logs: list[tuple[str, str, str | None]] = []
        agg_lock = threading.Lock()

        def _fetch_and_eval(row: MarketScanUniverse) -> tuple[
            str, list[BreakoutScanRow], str | None, str | None
        ]:
            """Return (ticker, hits_for_ticker, source|None, error|None). Thread-safe: no DB writes."""
            ticker = str(row.ticker)
            try:
                payload = self.fmp.get_ma150_series_or_eod(ticker)
                source = payload.get("source")
                bars = payload.get("bars") or []
                ticker_hits = _evaluate_all_rules(
                    row, bars, source, scan_date=today, scanned_at=scanned_at
                )
                return (ticker, ticker_hits, source, None)
            except Exception as exc:  # noqa: BLE001 — isolate per-ticker
                return (ticker, [], None, f"{exc}\n{traceback.format_exc()}")

        if active:
            with ThreadPoolExecutor(
                max_workers=P.SCAN_WORKER_COUNT,
                thread_name_prefix="market-scanner",
            ) as pool:
                futures = [pool.submit(_fetch_and_eval, row) for row in active]
                for fut in as_completed(futures):
                    ticker, ticker_hits, source, err = fut.result()
                    with agg_lock:
                        if err is not None:
                            failed += 1
                            pending_logs.append(
                                (
                                    "ERROR",
                                    f"{ticker} scan failed: {err.splitlines()[0]}",
                                    err,
                                )
                            )
                            continue
                        if source == "eod_fallback":
                            fallback_used = True
                            if not fallback_logged:
                                pending_logs.append(
                                    (
                                        "WARN",
                                        "SMA endpoint unavailable, falling back to EOD",
                                        None,
                                    )
                                )
                                fallback_logged = True
                        hits.extend(ticker_hits)
                        scanned_ok += 1

        duration_s = time.monotonic() - scan_start

        for level, message, detail in pending_logs:
            self.log_repo.create(
                level=level, source=LOG_SOURCE, message=message, detail=detail
            )

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
                hits_by_type=empty_counts,
                error="all tickers failed",
            )

        self.breakout_repo.replace_scan(hits)

        hits_by_type = dict(empty_counts)
        for h in hits:
            hits_by_type[h.signal_type] = hits_by_type.get(h.signal_type, 0) + 1
        by_type_str = " ".join(
            f"{stype}={hits_by_type[stype]}" for stype in P.ALL_SIGNAL_TYPES
        )
        self.log_repo.create(
            level="OK",
            source=LOG_SOURCE,
            message=(
                f"scan complete: hits={len(hits)} scanned={scanned_ok} "
                f"failed={failed} fallback={fallback_used} "
                f"duration_s={duration_s:.2f} workers={P.SCAN_WORKER_COUNT} | {by_type_str}"
            ),
        )
        return ScannerResult(
            status="ok",
            total=len(active), scanned=scanned_ok, hits=len(hits), failed=failed,
            fallback_used=fallback_used,
            scan_date=today, scanned_at=scanned_at,
            hits_by_type=hits_by_type,
        )


# ---------------------------------------------------------------------------
# Rule evaluation
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class _BarCtx:
    """Preprocessed bar sequence + derived series, reused across all rule detectors."""

    universe_row: MarketScanUniverse
    scan_date: date
    scanned_at: datetime
    sorted_bars: list[Any]
    closes: list[float]
    volumes: list[int | None]
    ma_series: list[float | None]
    ma5_series: list[float | None]
    slope_today: float | None
    pct_above_today: float | None
    volume_ratio_today: float | None


def _evaluate_all_rules(
    universe_row: MarketScanUniverse,
    bars: list[Any],
    source: Any,
    *,
    scan_date: date,
    scanned_at: datetime,
) -> list[BreakoutScanRow]:
    """Evaluate all four rules against the same bar sequence; return 0..4 hit rows."""
    ctx = _build_bar_ctx(
        universe_row, bars, source, scan_date=scan_date, scanned_at=scanned_at
    )
    if ctx is None:
        return []

    results: list[BreakoutScanRow] = []
    detectors: tuple[Callable[[_BarCtx], BreakoutScanRow | None], ...] = (
        _detect_legacy_crossover,
        _detect_a1_stage_breakout,
        _detect_a2_slope_flip,
        _detect_b2_ma_pullback,
    )
    for detect in detectors:
        hit = detect(ctx)
        if hit is not None:
            results.append(hit)
    return results


def _build_bar_ctx(
    universe_row: MarketScanUniverse,
    bars: list[Any],
    source: Any,
    *,
    scan_date: date,
    scanned_at: datetime,
) -> _BarCtx | None:
    sorted_bars = sorted(bars, key=lambda b: str(_get(b, "date") or ""))
    if len(sorted_bars) < 2:
        return None

    closes = [float(_get(b, "close")) for b in sorted_bars]
    volumes: list[int | None] = []
    for b in sorted_bars:
        v = _get(b, "volume")
        volumes.append(int(v) if v is not None else None)

    if source == "sma":
        ma_series: list[float | None] = []
        for b in sorted_bars:
            raw = _get(b, "sma")
            ma_series.append(float(raw) if raw is not None else None)
    else:
        ma_series = compute_ma150_series(closes)

    ma5_series = _compute_rolling_sma(closes, P.B2_MA_SHORT_WINDOW)

    ma_today = ma_series[-1]
    pct_above_today: float | None = None
    if ma_today is not None and ma_today > 0:
        pct_above_today = (closes[-1] - ma_today) / ma_today * 100.0

    ma_non_null = [v for v in ma_series if v is not None]
    slope_today: float | None = None
    if len(ma_non_null) >= SLOPE_WINDOW:
        slope_today = compute_slope(ma_non_null)

    volume_ratio_today = _compute_volume_ratio(volumes, P.A1_VOLUME_AVG_WINDOW)

    return _BarCtx(
        universe_row=universe_row,
        scan_date=scan_date,
        scanned_at=scanned_at,
        sorted_bars=sorted_bars,
        closes=closes,
        volumes=volumes,
        ma_series=ma_series,
        ma5_series=ma5_series,
        slope_today=slope_today,
        pct_above_today=pct_above_today,
        volume_ratio_today=volume_ratio_today,
    )


def _make_row(ctx: _BarCtx, signal_type: str) -> BreakoutScanRow:
    ma_today = ctx.ma_series[-1]
    assert ma_today is not None  # guarded by each detector
    assert ctx.pct_above_today is not None
    assert ctx.slope_today is not None
    volume_today = ctx.volumes[-1] if ctx.volumes else None
    return BreakoutScanRow(
        scan_date=ctx.scan_date,
        ticker=str(ctx.universe_row.ticker),
        company_name=str(ctx.universe_row.company_name),
        signal_type=signal_type,
        close_price=ctx.closes[-1],
        ma150_value=ma_today,
        pct_above_ma150=ctx.pct_above_today,
        slope_value=ctx.slope_today,
        market_cap=int(ctx.universe_row.market_cap),
        scanned_at=ctx.scanned_at,
        volume=volume_today,
        volume_ratio_20=ctx.volume_ratio_today,
    )


# -- Individual detectors ----------------------------------------------------


def _detect_legacy_crossover(ctx: _BarCtx) -> BreakoutScanRow | None:
    """F105 original rule: prev_close<prev_ma, today_close>=ma, pct<=10, slope>0."""
    if ctx.slope_today is None or ctx.slope_today <= 0:
        return None
    if ctx.pct_above_today is None or ctx.pct_above_today > P.LEGACY_PCT_ABOVE_MA_LIMIT:
        return None

    ma_today = ctx.ma_series[-1]
    ma_prev = ctx.ma_series[-2]
    if ma_today is None or ma_prev is None:
        return None

    close_today = ctx.closes[-1]
    close_prev = ctx.closes[-2]
    if not (close_prev < ma_prev and close_today >= ma_today):
        return None

    return _make_row(ctx, P.SIGNAL_LEGACY_CROSSOVER)


def _detect_a1_stage_breakout(ctx: _BarCtx) -> BreakoutScanRow | None:
    """A1: long horizontal MA150 + first crossover + volume confirmation.

    Requires ≥ A1_HORIZONTAL_WINDOW_DAYS non-null MA150 values. MA150 range over
    those days must be within A1_HORIZONTAL_RANGE_PCT; today is the first close
    ≥ MA150 (previous close was below); today volume ≥ 1.5 × 20-day avg.
    Slope only needs to be ≥ 0 (freshly-flat MA also qualifies).
    """
    if ctx.slope_today is None:
        return None
    if P.A1_REQUIRE_SLOPE_NONNEGATIVE and ctx.slope_today < 0:
        return None

    ma_today = ctx.ma_series[-1]
    ma_prev = ctx.ma_series[-2]
    if ma_today is None or ma_prev is None:
        return None

    close_today = ctx.closes[-1]
    close_prev = ctx.closes[-2]
    if not (close_prev < ma_prev and close_today >= ma_today):
        return None

    # Horizontal-ness test over the prior A1_HORIZONTAL_WINDOW_DAYS bars
    # (excluding today). Use bars [-(N+1):-1] — the last N bars before today.
    window_ma = ctx.ma_series[-(P.A1_HORIZONTAL_WINDOW_DAYS + 1):-1]
    window_ma = [v for v in window_ma if v is not None]
    if len(window_ma) < P.A1_HORIZONTAL_WINDOW_DAYS:
        return None
    ma_min = min(window_ma)
    ma_max = max(window_ma)
    if ma_min <= 0:
        return None
    range_pct = (ma_max - ma_min) / ma_min * 100.0
    if range_pct > P.A1_HORIZONTAL_RANGE_PCT:
        return None

    # Volume confirmation
    vr = ctx.volume_ratio_today
    if vr is None or vr < P.A1_VOLUME_RATIO_MIN:
        return None

    return _make_row(ctx, P.SIGNAL_A1_STAGE_BREAKOUT)


def _detect_a2_slope_flip(ctx: _BarCtx) -> BreakoutScanRow | None:
    """A2: slope(MA150, 20) today > 0, AND within A2_FLIP_LOOKBACK_DAYS some day had slope ≤ 0."""
    if ctx.slope_today is None or ctx.slope_today <= 0:
        return None

    close_today = ctx.closes[-1]
    ma_today = ctx.ma_series[-1]
    if ma_today is None or close_today <= ma_today:
        return None

    # Walk backward up to A2_FLIP_LOOKBACK_DAYS days and recompute slope on each.
    ma_non_null = [v for v in ctx.ma_series if v is not None]
    if len(ma_non_null) < SLOPE_WINDOW + 1:
        return None

    flipped = False
    # end exclusive; we already evaluated today's slope above.
    for days_back in range(1, P.A2_FLIP_LOOKBACK_DAYS + 1):
        # Need SLOPE_WINDOW ma150 values ending at (today - days_back).
        end_idx = len(ma_non_null) - days_back
        if end_idx < SLOPE_WINDOW:
            break
        past_slope = compute_slope(ma_non_null[:end_idx])
        if past_slope is None:
            continue
        if past_slope <= 0:
            flipped = True
            break

    if not flipped:
        return None

    return _make_row(ctx, P.SIGNAL_A2_SLOPE_FLIP)


def _detect_b2_ma_pullback(ctx: _BarCtx) -> BreakoutScanRow | None:
    """B2: uptrend + MA5 recently hugged MA150 (proximity ≤ threshold) and now re-expanding."""
    if ctx.slope_today is None or ctx.slope_today <= 0:
        return None

    ma5_today = ctx.ma5_series[-1]
    ma150_today = ctx.ma_series[-1]
    if ma5_today is None or ma150_today is None or ma150_today <= 0:
        return None
    if ma5_today <= ma150_today:
        return None

    today_gap_pct = (ma5_today - ma150_today) / ma150_today * 100.0

    # Compute gap history for the past B2_LOOKBACK_DAYS days (excluding today).
    gaps: list[float] = []
    window = ctx.ma5_series[-(P.B2_LOOKBACK_DAYS + 1):-1]
    ma150_window = ctx.ma_series[-(P.B2_LOOKBACK_DAYS + 1):-1]
    if len(window) < P.B2_LOOKBACK_DAYS or len(ma150_window) < P.B2_LOOKBACK_DAYS:
        return None
    for m5, m150 in zip(window, ma150_window):
        if m5 is None or m150 is None or m150 <= 0:
            continue
        gaps.append((m5 - m150) / m150 * 100.0)
    if not gaps:
        return None

    recent_min_gap = min(gaps)
    # Proximity means |gap| within threshold (could have been slightly below MA150).
    if abs(recent_min_gap) > P.B2_PROXIMITY_PCT:
        return None
    if today_gap_pct - recent_min_gap < P.B2_EXPANSION_DELTA_PCT:
        return None

    return _make_row(ctx, P.SIGNAL_B2_MA_PULLBACK)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _compute_rolling_sma(values: list[float], window: int) -> list[float | None]:
    out: list[float | None] = []
    running = 0.0
    for i, v in enumerate(values):
        running += v
        if i >= window:
            running -= values[i - window]
        if i + 1 >= window:
            out.append(running / window)
        else:
            out.append(None)
    return out


def _compute_volume_ratio(volumes: list[int | None], window: int) -> float | None:
    if len(volumes) < window + 1:
        return None
    today_vol = volumes[-1]
    if today_vol is None:
        return None
    past = volumes[-(window + 1):-1]
    clean = [v for v in past if v is not None and v > 0]
    if len(clean) < window:
        return None
    avg = sum(clean) / len(clean)
    if avg <= 0:
        return None
    return today_vol / avg


def _get(obj: Any, name: str) -> Any:
    if isinstance(obj, dict):
        return obj.get(name)
    return getattr(obj, name, None)
