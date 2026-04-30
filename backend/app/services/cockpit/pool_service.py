"""F205-e: PoolService — 5-layer funnel, RS + fundamental read from weekly cache.

Funnel layers:
  tradable  → market_scan_universe (market_cap / price / ADV / sector)
  trend     → ∩ latest market_breakout_scans (binary F106 proxy; trendScoreMin ignored, D080)
  rs        → cockpit_pool_cache.rs_percentile (weekly rebuild, D081)
  fundamental → cockpit_pool_cache.revenue_growth_yoy (weekly rebuild, D081)
  action    → sort RS desc, limit-cap

Cache miss (empty cockpit_pool_cache): rs=0, fundamental=0, action=0 + WARN log (Q3=A).
ADV = last_price × last_volume (single-day proxy, tech-debt D080).
Trend cap: POOL_TREND_CAP tickers by market_cap desc before RS layer (D080).
"""
from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import date, timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.external.fmp_client import FmpClient
from app.models.cockpit_pool_cache import CockpitPoolCache
from app.models.market_scan_universe import MarketScanUniverse
from app.repositories.earnings_event_repository import EarningsEventRepository
from app.repositories.market_breakout_repository import MarketBreakoutRepository
from app.repositories.market_scan_universe_repository import MarketScanUniverseRepository
from app.repositories.setup_snapshot_repository import SetupSnapshotRepository
from app.repositories.stock_repository import StockRepository
from app.repositories.system_log_repository import SystemLogRepository
from app.services.cockpit.pool_helpers import (
    compute_distance_to_50ma_pct,
    passes_fundamental_sanity,
)

logger = logging.getLogger(__name__)

POOL_TREND_CAP: int = 200


@dataclass
class PoolParams:
    """Query parameters for the pool funnel (mirrors API-CONTRACT.md §GET /api/cockpit/pool)."""

    market_cap_min: int = 20_000_000_000
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

    def _compute_rs_layer(
        self, trend: list[MarketScanUniverse], params: PoolParams
    ) -> dict[str, Any]:
        """Read RS data from cockpit_pool_cache; no FMP calls.

        Cache miss (empty table): return empty rs_tickers + write WARN log (Q3=A).
        """
        if not trend:
            return {"rs_tickers": [], "percentile_map": {}, "cache_by_ticker": {}}

        ticker_set = {u.ticker for u in trend}
        cache_rows = self._db.execute(
            select(CockpitPoolCache).where(CockpitPoolCache.ticker.in_(ticker_set))
        ).scalars().all()

        if not cache_rows:
            logger.warning("pool cache miss: cockpit_pool_cache is empty, returning empty funnel")
            self._log_repo.create(
                "WARN", "pool_service",
                "pool cache miss: run PoolCacheService.rebuild() to populate",
            )
            return {"rs_tickers": [], "percentile_map": {}, "cache_by_ticker": {}}

        cache_by_ticker = {row.ticker: row for row in cache_rows}
        percentile_map = {ticker: row.rs_percentile for ticker, row in cache_by_ticker.items()}

        rs_min = params.rs_percentile_min
        rs_tickers = [
            t for t in ticker_set
            if t in percentile_map and percentile_map[t] >= rs_min
        ]
        return {
            "rs_tickers": rs_tickers,
            "percentile_map": percentile_map,
            "cache_by_ticker": cache_by_ticker,
        }

    def _filter_fundamental(
        self, rs_data: dict[str, Any], params: PoolParams
    ) -> dict[str, Any]:
        """Read revenue_growth_yoy from cache; fail-open on null (D079).

        Returns: {tickers, growth_by_ticker}
        """
        rs_tickers = rs_data["rs_tickers"]
        if not rs_tickers:
            return {"tickers": [], "growth_by_ticker": {}}

        cache_by_ticker: dict[str, CockpitPoolCache] = rs_data["cache_by_ticker"]
        growth_by_ticker: dict[str, float | None] = {
            t: cache_by_ticker[t].revenue_growth_yoy if t in cache_by_ticker else None
            for t in rs_tickers
        }

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
        cache_by_ticker: dict[str, CockpitPoolCache],
        growth_by_ticker: dict[str, float | None],
        today: date,
    ) -> dict[str, Any]:
        cache = cache_by_ticker.get(ticker)
        ma50 = cache.ma50 if cache else None
        close_val = (cache.last_close if cache and cache.last_close else None) or u.last_price or 0.0
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
        tickers = fund_result["tickers"]
        if not tickers:
            return []

        today = date.today()
        percentile_map = rs_data["percentile_map"]
        cache_by_ticker = rs_data["cache_by_ticker"]
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
                ticker, u, snap, in_wl, percentile_map, cache_by_ticker, growth_by_ticker, today
            ))

        return sorted(items, key=lambda x: x["rs_percentile"], reverse=True)
