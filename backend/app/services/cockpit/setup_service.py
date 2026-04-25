"""F202-a: SetupService — compute and store daily setup snapshots for all watchlist stocks."""

from __future__ import annotations

from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.market_index import MarketIndex
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.market_regime_repository import MarketRegimeRepository
from app.repositories.setup_snapshot_repository import SetupSnapshotRepository
from app.repositories.stock_repository import StockRepository
from app.services.cockpit.cockpit_params import SETUP
from app.services.watchlist_service import APIError

# ── Setup type constants ───────────────────────────────────────────────────────

SETUP_BREAKOUT = "BREAKOUT"
SETUP_PULLBACK = "PULLBACK"
SETUP_RECLAIM = "RECLAIM"
SETUP_EARNINGS_DRIFT = "EARNINGS_DRIFT"
SETUP_EXTENDED = "EXTENDED"
SETUP_BROKEN = "BROKEN"
SETUP_NONE = "NONE"

_ACTIONABLE_TYPES = {SETUP_BREAKOUT, SETUP_PULLBACK, SETUP_RECLAIM, SETUP_EARNINGS_DRIFT}

# suggestedAction → summary bucket
_ACTION_TO_BUCKET = {
    "enter": "ready",
    "watch": "near",
    "wait": "near",
    "reduce": "extended",
    "exit": "broken",
    None: "none",
}

# Allowed quality sets keyed by READY_QUALITY_MIN
_QUALITY_SETS: dict[str, set[str]] = {
    "A": {"A"},
    "B": {"A", "B"},
    "C": {"A", "B", "C"},
}

# suggestedAction sort priority
_ACTION_ORDER = {"enter": 0, "watch": 1, "wait": 2, None: 3, "reduce": 4, "exit": 5}

# ── Pure functions ─────────────────────────────────────────────────────────────


def _compute_mas(closes: list[float]) -> dict[int, float | None]:
    """Compute simple moving averages for SETUP.MA_PERIODS. None when insufficient data."""
    result: dict[int, float | None] = {}
    n = len(closes)
    for period in SETUP.MA_PERIODS:
        if n >= period:
            result[period] = sum(closes[-period:]) / period
        else:
            result[period] = None
    return result


def _compute_trend_score(last_close: float, mas: dict[int, float | None]) -> int:
    """
    5-point ladder: close>MA10(+1), MA10>MA21(+1), MA21>MA50(+1), MA50>MA150(+1), MA150>MA200(+1).
    A None MA value counts as False for that condition.
    """
    periods = SETUP.MA_PERIODS  # [10, 21, 50, 150, 200]
    score = 0
    values = [last_close] + [mas.get(p) for p in periods]  # [close, ma10, ma21, ma50, ma150, ma200]
    for i in range(len(values) - 1):
        higher = values[i]
        lower = values[i + 1]
        if higher is not None and lower is not None and higher > lower:
            score += 1
    return score


def _compute_volume_status(volumes: list[int]) -> str | None:
    """HIGH / NORMAL / LOW based on last volume vs VOLUME_MA_PERIOD-day average."""
    period = SETUP.VOLUME_MA_PERIOD
    if len(volumes) < period + 1:
        return None
    avg = sum(volumes[-(period + 1):-1]) / period
    if avg == 0:
        return None
    ratio = volumes[-1] / avg
    if ratio > SETUP.VOLUME_HIGH_RATIO:
        return "HIGH"
    if ratio < SETUP.VOLUME_LOW_RATIO:
        return "LOW"
    return "NORMAL"


def _classify_setup_type(
    last_close: float,
    mas: dict[int, float | None],
    highs: list[float],
    trend_score: int,
    had_recent_earnings: bool,
    prev_closes: list[float],
) -> tuple[str, float | None, float | None, float | None, float | None]:
    """
    Returns (setup_type, entry_price, stop_price, target_2r, target_3r).
    Priority: BROKEN > EXTENDED > EARNINGS_DRIFT > BREAKOUT > PULLBACK > RECLAIM > NONE.
    """
    ma10 = mas.get(10)
    ma21 = mas.get(21)
    ma50 = mas.get(50)
    ma150 = mas.get(150)

    def _targets(entry: float, stop: float) -> tuple[float, float]:
        risk = entry - stop
        if risk <= 0:
            return entry, entry
        return entry + 2 * risk, entry + 3 * risk

    # 1. BROKEN
    if ma150 is not None and last_close < ma150:
        return SETUP_BROKEN, None, None, None, None

    if ma50 is None:
        return SETUP_NONE, None, None, None, None

    # 2. EXTENDED
    if (last_close - ma50) / ma50 * 100 > SETUP.EXTENDED_MA50_PCT:
        return SETUP_EXTENDED, None, None, None, None

    tick = SETUP.ENTRY_TICK_PCT / 100

    # 3. EARNINGS_DRIFT
    if had_recent_earnings and ma21 is not None and last_close > ma21:
        entry = round(last_close * (1 + tick), 4)
        stop = round(ma21 * (1 - SETUP.EARNINGS_DRIFT_STOP_MA21_PCT / 100), 4)
        t2r, t3r = _targets(entry, stop)
        return SETUP_EARNINGS_DRIFT, entry, stop, round(t2r, 4), round(t3r, 4)

    # 4. BREAKOUT
    if len(highs) >= SETUP.PIVOT_LOOKBACK_BARS and trend_score >= 3:
        pivot = max(highs[-SETUP.PIVOT_LOOKBACK_BARS:])
        lower_bound = pivot * (1 - SETUP.BREAKOUT_ZONE_PCT / 100)
        if last_close >= lower_bound:
            entry = round(pivot, 4)
            stop = round(ma50 * (1 - SETUP.BREAKOUT_STOP_MA50_PCT / 100), 4)
            t2r, t3r = _targets(entry, stop)
            return SETUP_BREAKOUT, entry, stop, round(t2r, 4), round(t3r, 4)

    # 5. PULLBACK
    if ma21 is not None and trend_score >= 3:
        lower_support = ma150 if ma150 is not None else ma50 * (1 - SETUP.PULLBACK_FALLBACK_SUPPORT_PCT / 100)
        upper_ceiling = ma50 * (1 + SETUP.PULLBACK_ZONE_ABOVE_MA50_PCT / 100)
        pullback_floor = ma50 * (1 - SETUP.PULLBACK_FLOOR_MA50_PCT / 100)
        if lower_support <= last_close <= upper_ceiling and last_close > pullback_floor:
            entry = round(ma21, 4)
            stop = round(ma21 * (1 - SETUP.PULLBACK_STOP_MA21_PCT / 100), 4)
            t2r, t3r = _targets(entry, stop)
            return SETUP_PULLBACK, entry, stop, round(t2r, 4), round(t3r, 4)

    # 6. RECLAIM
    if trend_score >= 2 and last_close > ma50:
        lookback = prev_closes[-SETUP.RECLAIM_LOOKBACK_BARS:]
        if any(c < ma50 for c in lookback):
            entry = round(ma50 * (1 + tick), 4)
            stop = round(ma50 * (1 - SETUP.RECLAIM_STOP_MA50_PCT / 100), 4)
            t2r, t3r = _targets(entry, stop)
            return SETUP_RECLAIM, entry, stop, round(t2r, 4), round(t3r, 4)

    return SETUP_NONE, None, None, None, None


def _compute_earnings_risk(earnings_event: Any | None, today: date) -> str:
    """DANGER / CAUTION / SAFE based on days to next earnings."""
    if earnings_event is None:
        return "SAFE"
    days = (earnings_event.earnings_date - today).days
    if days <= SETUP.EARNINGS_DANGER_DAYS:
        return "DANGER"
    if days <= SETUP.EARNINGS_CAUTION_DAYS:
        return "CAUTION"
    return "SAFE"


def _compute_setup_quality(
    setup_type: str,
    trend_score: int,
    rs_percentile: float,
) -> str | None:
    """A / B / C / None (for NONE/BROKEN/EXTENDED)."""
    if setup_type in (SETUP_NONE, SETUP_BROKEN, SETUP_EXTENDED):
        return None
    if trend_score >= SETUP.QUALITY_A_TREND_MIN and rs_percentile >= SETUP.QUALITY_A_RS_MIN:
        return "A"
    if trend_score >= SETUP.QUALITY_B_TREND_MIN and rs_percentile >= SETUP.QUALITY_B_RS_MIN:
        return "B"
    if trend_score >= SETUP.QUALITY_C_TREND_MIN and rs_percentile >= SETUP.QUALITY_C_RS_MIN:
        return "C"
    return None


def _compute_ready_signal(
    trend_score: int,
    rs_percentile: float,
    setup_quality: str | None,
    distance_to_entry_pct: float | None,
    reward_risk: float | None,
    earnings_risk: str,
    regime: str,
) -> bool:
    """7-condition AND gate (all must be True)."""
    allowed_qualities = _QUALITY_SETS.get(SETUP.READY_QUALITY_MIN, {"A", "B"})
    return (
        trend_score >= SETUP.READY_TREND_MIN
        and rs_percentile >= SETUP.READY_RS_MIN
        and setup_quality in allowed_qualities
        and distance_to_entry_pct is not None
        and 0 <= distance_to_entry_pct <= SETUP.READY_DIST_MAX_PCT
        and reward_risk is not None
        and reward_risk >= SETUP.READY_REWARD_RISK_MIN
        and earnings_risk != "DANGER"
        and regime != "RISK_OFF"
    )


def _compute_suggested_action(
    setup_type: str,
    ready_signal: bool,
    distance_to_entry_pct: float | None,
) -> str | None:
    """enter / watch / wait / reduce / exit / None."""
    if ready_signal:
        return "enter"
    if setup_type in _ACTIONABLE_TYPES:
        if distance_to_entry_pct is not None and 0 <= distance_to_entry_pct <= SETUP.READY_DIST_MAX_PCT * 2:
            return "watch"
        return "wait"
    if setup_type == SETUP_EXTENDED:
        return "reduce"
    if setup_type == SETUP_BROKEN:
        return "exit"
    return None


def _percentile_rank(values: list[float], value: float) -> int:
    """0-100 percentile rank of value within values list."""
    if len(values) <= 1:
        return int(SETUP.RS_SPY_FALLBACK_PCT)
    below = sum(1 for v in values if v < value)
    return int(below / len(values) * 100)


# ── SetupService ───────────────────────────────────────────────────────────────


class SetupService:
    def __init__(self, db: Session) -> None:
        self.db = db
        self.repo = SetupSnapshotRepository(db)
        self.stock_repo = StockRepository(db)
        self.earnings_repo = EarningsEventRepository(db)
        self.regime_repo = MarketRegimeRepository(db)

    def compute_and_store_all(self, today: date | None = None) -> int:
        today = today or date.today()

        # Current regime (fallback NEUTRAL when cold-start)
        latest_regime = self.regime_repo.get_latest()
        regime = latest_regime.regime if latest_regime else "NEUTRAL"

        # Active stocks
        stocks = self.stock_repo.list_active()

        # SPY historical closes for RS percentile
        spy_closes = self._get_spy_closes()

        # Compute raw RS ratios per ticker
        spy_return = self._compute_return(spy_closes)

        bars_per_ticker: dict[str, tuple] = {}
        for stock in stocks:
            bars_per_ticker[stock.ticker] = self._get_stock_bars(stock.id)

        # First pass: compute rs_ratio per ticker
        rs_ratios: dict[str, float] = {}
        for stock in stocks:
            closes, _, _, volumes = bars_per_ticker[stock.ticker]
            stock_return = self._compute_return(closes)
            if spy_return is not None and abs(spy_return) > 0.001:
                rs_ratios[stock.ticker] = stock_return / spy_return if stock_return is not None else 0.0
            else:
                rs_ratios[stock.ticker] = stock_return if stock_return is not None else 0.0

        all_ratios = list(rs_ratios.values())

        # Second pass: build full snapshots
        rows: list[dict] = []
        for stock in stocks:
            closes, highs, lows, volumes = bars_per_ticker[stock.ticker]
            if len(closes) < 10:
                # Insufficient data — write NONE row
                earnings_ev = self.earnings_repo.get_next_earnings(stock.ticker, today)
                earnings_risk = _compute_earnings_risk(earnings_ev, today)
                rows.append({
                    "ticker": stock.ticker,
                    "scan_date": today,
                    "setup_type": SETUP_NONE,
                    "setup_quality": None,
                    "entry_price": None,
                    "stop_price": None,
                    "target_2r": None,
                    "target_3r": None,
                    "distance_to_entry_pct": None,
                    "reward_risk": None,
                    "rs_percentile": SETUP.RS_SPY_FALLBACK_PCT,
                    "volume_status": None,
                    "trend_score": 0,
                    "earnings_risk": earnings_risk,
                    "ready_signal": False,
                    "suggested_action": None,
                    "scanned_at": datetime.now(timezone.utc),
                })
                continue

            mas = _compute_mas(closes)
            trend_score = _compute_trend_score(closes[-1], mas)
            volume_status = _compute_volume_status(volumes)
            rs_percentile = float(_percentile_rank(all_ratios, rs_ratios[stock.ticker]))

            earnings_ev = self.earnings_repo.get_next_earnings(stock.ticker, today)
            earnings_risk = _compute_earnings_risk(earnings_ev, today)

            # Determine if had recent earnings (drift scenario)
            had_recent_earnings = self._had_recent_earnings(stock.ticker, today)

            setup_type, entry, stop, t2r, t3r = _classify_setup_type(
                closes[-1], mas, highs, trend_score, had_recent_earnings, closes[:-1]
            )

            dist = None
            if entry is not None and closes[-1] > 0:
                dist = round((entry - closes[-1]) / closes[-1] * 100, 4)

            rr = None
            if entry is not None and stop is not None and t2r is not None and entry > stop:
                rr = round((t2r - entry) / (entry - stop), 4)

            setup_quality = _compute_setup_quality(setup_type, trend_score, rs_percentile)

            ready = _compute_ready_signal(
                trend_score, rs_percentile, setup_quality, dist, rr, earnings_risk, regime
            )
            action = _compute_suggested_action(setup_type, ready, dist)

            rows.append({
                "ticker": stock.ticker,
                "scan_date": today,
                "setup_type": setup_type,
                "setup_quality": setup_quality,
                "entry_price": entry,
                "stop_price": stop,
                "target_2r": t2r,
                "target_3r": t3r,
                "distance_to_entry_pct": dist,
                "reward_risk": rr,
                "rs_percentile": rs_percentile,
                "volume_status": volume_status,
                "trend_score": trend_score,
                "earnings_risk": earnings_risk,
                "ready_signal": ready,
                "suggested_action": action,
                "scanned_at": datetime.now(timezone.utc),
            })

        count = self.repo.upsert_batch(rows)

        cutoff = today - timedelta(days=SETUP.SETUP_RETENTION_DAYS)
        self.repo.delete_before(cutoff)

        return count

    def get_setup_monitor_data(
        self,
        filter_str: str | None = None,
        today: date | None = None,
    ) -> dict:
        today = today or date.today()
        active_stocks = self.stock_repo.list_active()
        active_tickers = [s.ticker for s in active_stocks]
        name_map = {s.ticker: s.name for s in active_stocks}
        all_rows = self.repo.get_latest_all_active(active_tickers)

        if not all_rows:
            return {
                "summary": {"total": 0, "ready": 0, "near": 0, "extended": 0, "broken": 0, "none": 0},
                "items": [],
            }

        # Build summary
        summary: dict[str, int] = {"total": len(all_rows), "ready": 0, "near": 0, "extended": 0, "broken": 0, "none": 0}
        for row in all_rows:
            bucket = _ACTION_TO_BUCKET.get(row.suggested_action, "none")
            summary[bucket] = summary.get(bucket, 0) + 1

        # Apply filter
        if filter_str:
            wanted = {f.strip() for f in filter_str.split(",") if f.strip()}
            filtered = [r for r in all_rows if _ACTION_TO_BUCKET.get(r.suggested_action, "none") in wanted]
        else:
            filtered = all_rows

        items = [_row_to_dict(r, name_map.get(r.ticker)) for r in filtered]
        return {"summary": summary, "items": items}

    # ── Private helpers ────────────────────────────────────────────────────────

    def _get_spy_closes(self) -> list[float]:
        stmt = (
            select(MarketIndex.close)
            .where(MarketIndex.symbol == "SPY")
            .order_by(MarketIndex.date.asc())
            .limit(SETUP.RS_LOOKBACK_DAYS)
        )
        return [float(r) for r in self.db.execute(stmt).scalars().all()]

    def _compute_return(self, closes: list[float]) -> float | None:
        if len(closes) < 2:
            return None
        first = closes[0]
        if first == 0:
            return None
        return (closes[-1] - first) / first

    def _get_stock_bars(self, stock_id: int) -> tuple[list[float], list[float], list[float], list[int]]:
        from app.models.daily_bar import DailyBar
        stmt = (
            select(DailyBar)
            .where(DailyBar.stock_id == stock_id)
            .order_by(DailyBar.date.asc())
            .limit(260)
        )
        bars = list(self.db.execute(stmt).scalars().all())
        closes = [float(b.close) for b in bars]
        highs = [float(b.high) for b in bars]
        lows = [float(b.low) for b in bars]
        volumes = [int(b.volume) for b in bars]
        return closes, highs, lows, volumes

    def _had_recent_earnings(self, ticker: str, today: date) -> bool:
        """True if there was an earnings event within EARNINGS_DRIFT_MAX_DAYS before today."""
        from app.models.earnings_event import EarningsEvent
        cutoff = today - timedelta(days=SETUP.EARNINGS_DRIFT_MAX_DAYS)
        stmt = (
            select(EarningsEvent)
            .where(
                EarningsEvent.ticker == ticker,
                EarningsEvent.earnings_date >= cutoff,
                EarningsEvent.earnings_date < today,
            )
            .limit(1)
        )
        return self.db.execute(stmt).scalar_one_or_none() is not None


def _row_to_dict(r: Any, stock_name: str | None = None) -> dict:
    """Convert SetupSnapshot ORM row to API-CONTRACT camelCase dict."""
    return {
        "ticker": r.ticker,
        "stockName": stock_name,
        "setupType": r.setup_type,
        "setupQuality": r.setup_quality,
        "entryPrice": r.entry_price,
        "stopPrice": r.stop_price,
        "target2r": r.target_2r,
        "target3r": r.target_3r,
        "distanceToEntryPct": r.distance_to_entry_pct,
        "rewardRisk": r.reward_risk,
        "rsPercentile": r.rs_percentile,
        "volumeStatus": r.volume_status,
        "trendScore": r.trend_score,
        "earningsRisk": r.earnings_risk,
        "readySignal": r.ready_signal,
        "suggestedAction": r.suggested_action,
        "scanDate": r.scan_date.isoformat() if r.scan_date else None,
    }
