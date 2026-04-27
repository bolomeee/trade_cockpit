"""F205-c: PoolService — 5-layer funnel orchestration for GET /api/cockpit/pool.

Funnel layers:
  tradable  → market_scan_universe (market_cap / price / ADV / sector)
  trend     → ∩ latest market_breakout_scans (binary F106 proxy; trendScoreMin ignored, D080)
  rs        → FMP get_daily_bars 6-concurrent + SPY closes → compute_return_ratio_250d + percentile
  fundamental → FMP get_financial_growth 6-concurrent → passes_fundamental_sanity (fail-open, D079)
  action    → sort RS desc, limit-cap

ADV = last_price × last_volume (single-day proxy, tech-debt D080).
Trend cap: POOL_TREND_CAP tickers by market_cap desc before RS layer (D080).
"""
from __future__ import annotations

import logging
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field
from datetime import date, datetime, timedelta, timezone
from typing import Any

from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.market_scan_universe import MarketScanUniverse
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.market_breakout_repository import MarketBreakoutRepository
from app.repositories.market_scan_universe_repository import MarketScanUniverseRepository
from app.repositories.setup_snapshot_repository import SetupSnapshotRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.system_log_repository import SystemLogRepository
from app.services.cockpit.pool_helpers import (
    compute_distance_to_50ma_pct,
    compute_return_ratio_250d,
    compute_rs_percentile_map,
    extract_revenue_growth_yoy_pct,
    passes_fundamental_sanity,
)

logger = logging.getLogger(__name__)

POOL_TREND_CAP: int = 200
_FMP_MAX_WORKERS: int = 6
_BARS_LOOKBACK_DAYS: int = 400  # ~280 trading days → guarantees ≥250 for RS computation


@dataclass
class PoolParams:
    """Query parameters for the pool funnel (mirrors API-CONTRACT.md §GET /api/cockpit/pool)."""

    market_cap_min: int = 50_000_000_000
    price_min: float = 10.0
    adv_min: int = 20_000_000
    trend_score_min: int = 3       # accepted but intentionally ignored (D080)
    rs_percentile_min: float = 70.0
    revenue_growth_yoy_min: float = 10.0
    sectors: list[str] = field(default_factory=list)      # empty = all sectors
    setup_types: list[str] = field(default_factory=list)  # empty = all types
    limit: int = 50


class PoolService:
    def __init__(self, db: Session, fmp: FmpClient) -> None:
        self._db = db
        self._fmp = fmp
        self._universe_repo = MarketScanUniverseRepository(db)
        self._breakout_repo = MarketBreakoutRepository(db)
        self._setup_repo = SetupSnapshotRepository(db)
        self._stock_repo = StockRepository(db)
        self._earnings_repo = EarningsEventRepository(db)
        self._log_repo = SystemLogRepository(db)

    def get_pool(self, params: PoolParams) -> dict[str, Any]:
        """Run 5-layer funnel; return {funnel, items} ready for PoolResponse serialisation."""
        universe = self._get_universe()
        universe_by_ticker = {u.ticker: u for u in universe}

        tradable = self._filter_tradable(universe, params)
        trend = self._filter_trend(tradable, params)
        rs_data = self._compute_rs_layer(trend, params)
        fund_result = self._filter_fundamental(rs_data, params)
        items = self._build_items(fund_result, rs_data, universe_by_ticker, params)

        return {
            "funnel": {
                "tradable": len(tradable),
                "trend": len(trend),
                "rs": len(rs_data["rs_tickers"]),
                "fundamental": len(fund_result["tickers"]),
                "action": len(items),
            },
            "items": items[: params.limit],
        }

    # ── private layer methods ────────────────────────────────────────────────

    def _get_universe(self) -> list[MarketScanUniverse]:
        """Load all tickers from the most recent universe refresh."""
        latest = self._universe_repo.latest_refresh_time()
        if latest is None:
            return []
        since = latest - timedelta(minutes=5)
        return self._universe_repo.list_active(since=since)

    def _filter_tradable(
        self, universe: list[MarketScanUniverse], params: PoolParams
    ) -> list[MarketScanUniverse]:
        result = [
            u for u in universe
            if (u.market_cap or 0) >= params.market_cap_min
            and (u.last_price or 0.0) >= params.price_min
            and (u.last_price or 0.0) * (u.last_volume or 0) >= params.adv_min
        ]
        if params.sectors:
            sector_set = set(params.sectors)
            result = [u for u in result if u.sector in sector_set]
        return result

    def _filter_trend(
        self, tradable: list[MarketScanUniverse], params: PoolParams
    ) -> list[MarketScanUniverse]:
        snapshot = self._breakout_repo.get_latest_snapshot()
        if snapshot is None:
            return []

        breakout_tickers = {item.ticker for item in snapshot.items}
        trend = [u for u in tradable if u.ticker in breakout_tickers]

        if len(trend) > POOL_TREND_CAP:
            dropped = len(trend) - POOL_TREND_CAP
            self._log_repo.create(
                "WARN",
                "pool_service",
                f"pool trend cap hit, dropped {dropped} tickers",
            )
            trend = sorted(trend, key=lambda u: u.market_cap or 0, reverse=True)[:POOL_TREND_CAP]

        return trend

    def _fetch_bars_concurrent(
        self, tickers: list[str], from_date: date, to_date: date
    ) -> dict[str, list[float]]:
        """Fetch EOD closes for tickers concurrently; silently skip failures."""
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

    def _compute_rs_layer(
        self, trend: list[MarketScanUniverse], params: PoolParams
    ) -> dict[str, Any]:
        """Fetch 250-day bars for trend tickers + SPY; return RS data dict.

        Returns: {rs_tickers, percentile_map, closes_by_ticker}
        """
        if not trend:
            return {"rs_tickers": [], "percentile_map": {}, "closes_by_ticker": {}}

        today = date.today()
        from_date = today - timedelta(days=_BARS_LOOKBACK_DAYS)

        try:
            spy_bars = self._fmp.get_daily_bars("SPY", from_date, today)
        except Exception:
            spy_bars = []
        spy_closes = [b["close"] for b in sorted(spy_bars, key=lambda b: b.get("date", ""))]

        tickers = [u.ticker for u in trend]
        closes_by_ticker = self._fetch_bars_concurrent(tickers, from_date, today)

        ratio_by_ticker = {
            t: compute_return_ratio_250d(closes_by_ticker.get(t) or [], spy_closes)
            for t in tickers
        }
        percentile_map = compute_rs_percentile_map(ratio_by_ticker)

        rs_min = params.rs_percentile_min
        rs_tickers = [t for t in tickers if percentile_map.get(t, 0.0) >= rs_min]
        return {
            "rs_tickers": rs_tickers,
            "percentile_map": percentile_map,
            "closes_by_ticker": closes_by_ticker,
        }

    def _filter_fundamental(
        self, rs_data: dict[str, Any], params: PoolParams
    ) -> dict[str, Any]:
        """Fetch revenue growth for RS tickers; fail-open on missing data (D079).

        Returns: {tickers, growth_by_ticker}
        """
        rs_tickers = rs_data["rs_tickers"]
        if not rs_tickers:
            return {"tickers": [], "growth_by_ticker": {}}

        growth_by_ticker: dict[str, float | None] = {}

        def _fetch_growth(ticker: str) -> tuple[str, float | None]:
            payload = self._fmp.get_financial_growth(ticker)
            return ticker, extract_revenue_growth_yoy_pct(payload)

        with ThreadPoolExecutor(max_workers=_FMP_MAX_WORKERS) as executor:
            futures = {executor.submit(_fetch_growth, t): t for t in rs_tickers}
            for future in as_completed(futures):
                ticker, growth = future.result()
                growth_by_ticker[ticker] = growth

        threshold = params.revenue_growth_yoy_min
        passing = [
            t for t in rs_tickers
            if passes_fundamental_sanity(growth_by_ticker.get(t), threshold)
        ]
        return {"tickers": passing, "growth_by_ticker": growth_by_ticker}

    def _make_item(
        self,
        ticker: str,
        u: MarketScanUniverse,
        snap: Any,
        in_wl: bool,
        percentile_map: dict[str, float],
        closes_by_ticker: dict[str, list[float]],
        growth_by_ticker: dict[str, float | None],
        today: date,
    ) -> dict[str, Any]:
        """Build the item dict for a single ticker."""
        closes = closes_by_ticker.get(ticker)
        ma50 = sum(closes[-50:]) / 50 if closes and len(closes) >= 50 else None
        close_val = (closes[-1] if closes else None) or u.last_price or 0.0
        earnings = self._earnings_repo.get_next_earnings(ticker, today)
        e_date = earnings.earnings_date if earnings else None
        return {
            "ticker": ticker,
            "name": u.company_name,
            "sector": u.sector,
            "price": u.last_price,
            "trend_score": snap.trend_score if snap else None,
            "rs_percentile": percentile_map.get(ticker, 0.0),
            "setup_type": snap.setup_type if snap else None,
            "distance_to_pivot_pct": snap.distance_to_entry_pct if snap else None,
            "distance_to_50ma_pct": compute_distance_to_50ma_pct(close_val, ma50),
            "earnings_date": e_date,
            "days_until_earnings": (e_date - today).days if e_date else None,
            "revenue_growth_yoy": growth_by_ticker.get(ticker),
            "suggested_action": (snap.suggested_action if snap else None) or "watch",
            "in_watchlist": in_wl,
        }

    def _build_items(
        self,
        fund_result: dict[str, Any],
        rs_data: dict[str, Any],
        universe_by_ticker: dict[str, MarketScanUniverse],
        params: PoolParams,
    ) -> list[dict[str, Any]]:
        """Enrich fundamental tickers; apply setupTypes filter; sort RS desc."""
        tickers = fund_result["tickers"]
        if not tickers:
            return []

        today = date.today()
        percentile_map = rs_data["percentile_map"]
        closes_by_ticker = rs_data["closes_by_ticker"]
        growth_by_ticker = fund_result["growth_by_ticker"]

        watchlist_set = {s.ticker for s in self._stock_repo.list_active()}
        wl_in_pool = [t for t in tickers if t in watchlist_set]
        snapshots = {s.ticker: s for s in self._setup_repo.get_latest_for_tickers(wl_in_pool)}
        setup_types_filter = set(params.setup_types) if params.setup_types else None

        items: list[dict[str, Any]] = []
        for ticker in tickers:
            u = universe_by_ticker.get(ticker)
            if u is None:
                continue
            in_wl = ticker in watchlist_set
            snap = snapshots.get(ticker)
            if setup_types_filter and in_wl and (snap is None or snap.setup_type not in setup_types_filter):
                continue
            items.append(self._make_item(
                ticker, u, snap, in_wl, percentile_map, closes_by_ticker, growth_by_ticker, today
            ))

        return sorted(items, key=lambda x: x["rs_percentile"], reverse=True)
