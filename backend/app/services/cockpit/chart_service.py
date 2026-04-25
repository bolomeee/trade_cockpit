"""F203-a: CockpitChart service — OHLCV + multi-MA + Wilder ATR + AVWAP."""
from __future__ import annotations

from datetime import date, timedelta
from typing import Any

import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models import DailyBar, Stock
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.stock_repository import StockRepository
from app.services.cockpit.cockpit_params import CHART
from app.services.watchlist_service import APIError

# FMP on-demand lookback: need days + max MA period headroom
_FMP_LOOKBACK_DAYS = 600


# ── Pure functions ─────────────────────────────────────────────────────────────


def _compute_ma_series(bars: list[dict[str, Any]], period: int) -> list[dict[str, Any]]:
    """SMA series over bars close prices.

    Returns [{date, value}] starting from bar index period-1 (no None placeholders).
    Returns [] when period >= len(bars).
    """
    n = len(bars)
    if period <= 0 or period >= n:
        return []
    result = []
    window_sum = sum(b["close"] for b in bars[:period])
    result.append({"date": bars[period - 1]["date"], "value": window_sum / period})
    for i in range(period, n):
        window_sum += bars[i]["close"] - bars[i - period]["close"]
        result.append({"date": bars[i]["date"], "value": window_sum / period})
    return result


def _compute_atr_series(bars: list[dict[str, Any]], period: int) -> list[dict[str, Any]]:
    """Wilder ATR series.

    ATR_seed = SMA(TR, period) for the first period bars.
    ATR_i = (ATR_{i-1} * (period-1) + TR_i) / period for subsequent bars.
    Returns [{date, value}] starting after the first `period` bars (index period onward).
    """
    n = len(bars)
    if period <= 0 or n < period + 1:
        return []

    trs: list[float] = []
    for i in range(1, n):
        high = bars[i]["high"]
        low = bars[i]["low"]
        prev_close = bars[i - 1]["close"]
        tr = max(high - low, abs(high - prev_close), abs(low - prev_close))
        trs.append(tr)

    # trs has n-1 elements; trs[0] corresponds to bars[1]
    if len(trs) < period:
        return []

    seed_atr = sum(trs[:period]) / period
    result = [{"date": bars[period]["date"], "value": seed_atr}]

    current_atr = seed_atr
    for i in range(period, len(trs)):
        current_atr = (current_atr * (period - 1) + trs[i]) / period
        result.append({"date": bars[i + 1]["date"], "value": current_atr})
    return result


def _compute_avwap_series(bars: list[dict[str, Any]], anchor: date) -> list[dict[str, Any]]:
    """Cumulative VWAP anchored at `anchor` date (inclusive).

    anchor before bars[0] → treated as bars[0].date.
    anchor after bars[-1] → returns [].
    Skips bars where cumulative volume is 0.
    """
    if not bars:
        return []

    effective_anchor = max(anchor, bars[0]["date"])
    if effective_anchor > bars[-1]["date"]:
        return []

    result = []
    cum_pv = 0.0
    cum_v = 0.0
    for b in bars:
        if b["date"] < effective_anchor:
            continue
        typical = (b["high"] + b["low"] + b["close"]) / 3.0
        cum_pv += typical * b["volume"]
        cum_v += b["volume"]
        if cum_v > 0:
            result.append({"date": b["date"], "value": cum_pv / cum_v})
    return result


def _resolve_anchor(
    explicit_anchor: date | None,
    earnings_repo: EarningsEventRepository,
    ticker: str,
    today: date,
) -> date | None:
    """Return anchor date for AVWAP.

    Priority: explicit_anchor → most recent past earnings (≤ today) → None.
    """
    if explicit_anchor is not None:
        return explicit_anchor

    # Query the most recent earnings_date <= today for this ticker
    from app.models.earnings_event import EarningsEvent  # local to avoid circular

    result = (
        earnings_repo._db.query(EarningsEvent)
        .filter(
            EarningsEvent.ticker == ticker,
            EarningsEvent.earnings_date <= today,
        )
        .order_by(EarningsEvent.earnings_date.desc())
        .first()
    )
    return result.earnings_date if result is not None else None


# ── Service ────────────────────────────────────────────────────────────────────


class CockpitChartService:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self._db = db
        self._fmp = fmp
        self._stocks = StockRepository(db)
        self._earnings = EarningsEventRepository(db)

    def get_chart(
        self,
        ticker: str,
        mas: list[int] | None = None,
        days: int | None = None,
        anchor: date | None = None,
    ) -> dict[str, Any]:
        """Assemble chart payload per API-CONTRACT §GET /api/cockpit/chart/{ticker}."""
        ticker = ticker.strip().upper()
        resolved_mas = mas if mas is not None else list(CHART.DEFAULT_MAS)
        resolved_days = days if days is not None else CHART.DEFAULT_DAYS
        today = date.today()

        bars = self._load_bars(ticker, resolved_days)

        resolved_anchor = _resolve_anchor(anchor, self._earnings, ticker, today)

        ma_series: dict[str, list[dict[str, Any]]] = {}
        for period in resolved_mas:
            ma_series[str(period)] = _compute_ma_series(bars, period)

        atr_series = _compute_atr_series(bars, CHART.ATR_PERIOD)

        if resolved_anchor is not None:
            avwap_series = _compute_avwap_series(bars, resolved_anchor)
        else:
            avwap_series = []

        return {
            "ticker": ticker,
            "bars": bars,
            "mas": ma_series,
            "atr": atr_series,
            "avwap": {"anchor": resolved_anchor, "series": avwap_series},
        }

    def _load_bars(self, ticker: str, days: int) -> list[dict[str, Any]]:
        """Load bars from DB; fallback to FMP on-demand if missing/insufficient."""
        stock = self._stocks.get_by_ticker(ticker)

        if stock is not None:
            bars = self._bars_from_db(stock, days)
            if bars:
                return bars

        # FMP on-demand fallback (D041: not written to daily_bars)
        return self._bars_from_fmp(ticker, days)

    def _bars_from_db(self, stock: Stock, days: int) -> list[dict[str, Any]]:
        stmt = (
            select(DailyBar)
            .where(DailyBar.stock_id == stock.id)
            .order_by(DailyBar.date.desc())
            .limit(days)
        )
        rows = list(self._db.execute(stmt).scalars().all())
        if not rows:
            return []
        rows_asc = list(reversed(rows))
        return [
            {
                "date": b.date,
                "open": b.open,
                "high": b.high,
                "low": b.low,
                "close": b.close,
                "volume": b.volume,
            }
            for b in rows_asc
        ]

    def _bars_from_fmp(self, ticker: str, days: int) -> list[dict[str, Any]]:
        today = date.today()
        from_d = today - timedelta(days=_FMP_LOOKBACK_DAYS)
        try:
            raw = self._fmp.get_daily_bars(ticker, from_d, today)
        except httpx.HTTPError as exc:
            raise APIError(
                "EXTERNAL_API_ERROR",
                f"FMP chart fetch failed for {ticker}: {exc}",
                502,
            ) from exc

        if not raw:
            raise APIError("NOT_FOUND", f"ticker {ticker} not found", 404)

        normalized = [_normalize_bar(b) for b in raw if _bar_valid(b)]
        seen: dict[date, dict] = {}
        for b in sorted(normalized, key=lambda x: x["date"]):
            seen[b["date"]] = b
        bars_asc = list(seen.values())[-days:]

        if not bars_asc:
            raise APIError("NOT_FOUND", f"ticker {ticker} not found", 404)
        return bars_asc


# ── Bar normalization helpers ─────────────────────────────────────────────────


def _bar_valid(b: dict[str, Any]) -> bool:
    try:
        return all(b.get(f) is not None for f in ("date", "open", "high", "low", "close"))
    except Exception:
        return False


def _normalize_bar(b: dict[str, Any]) -> dict[str, Any]:
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
