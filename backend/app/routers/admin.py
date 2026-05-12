"""Admin endpoints: manual triggers for background jobs.

POST /api/admin/refresh-universe    — trigger UniverseRefreshService.refresh().
POST /api/admin/refresh-pool-cache  — trigger PoolCacheService.rebuild() (F205-e Q5=B).
POST /api/admin/refresh-earnings    — trigger EarningsService.fetch_and_store().
POST /api/admin/refresh-setup       — trigger SetupService.compute_and_store_all().
POST /api/admin/refresh-regime      — trigger regime ETF refresh + score recompute.
POST /api/admin/refresh-scanner     — trigger full market breakout scan.
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.services.cockpit.earnings_service import EarningsService
from app.services.cockpit.market_regime_service import MarketRegimeService
from app.services.cockpit.pool_cache_service import PoolCacheService
from app.services.cockpit.setup_service import SetupService
from app.services.market_refresh_service import MarketRefreshService
from app.services.market_scanner_service import MarketScannerService
from app.services.universe_refresh_service import UniverseRefreshService

router = APIRouter(prefix="/api/admin", tags=["admin"])


@router.post("/refresh-universe")
def refresh_universe(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> dict:
    """Manually trigger a universe refresh from FMP screener."""
    result = UniverseRefreshService(db=db, fmp=fmp).refresh()
    return {"status": result.status, "upserted": result.upserted, "skipped": result.skipped, "error": result.error}


@router.post("/refresh-pool-cache")
def refresh_pool_cache(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> dict:
    """Manually trigger a pool cache rebuild.

    Returns the PoolCacheResult as JSON. Safe to call multiple times;
    each call replaces the entire cache table.
    """
    result = PoolCacheService(db=db, fmp=fmp).rebuild()
    return {
        "status": result.status,
        "upserted": result.upserted,
        "elapsed_seconds": round(result.elapsed_seconds, 2),
        "error": result.error,
    }


@router.post("/refresh-earnings")
def refresh_earnings(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> dict:
    """Manually trigger an earnings calendar refresh (today-7 to today+30).

    Safe to call multiple times; existing records are upserted, not duplicated.
    """
    result = EarningsService(db=db, fmp=fmp).fetch_and_store()
    return result


@router.post("/refresh-setup")
def refresh_setup(db: Session = Depends(get_db)) -> dict:
    """Manually trigger a setup snapshot scan for all active watchlist tickers.

    Equivalent to the nightly 22:30 UTC cron. Can take 10-30s depending on
    watchlist size. Returns count of snapshots written and elapsed time.
    """
    t0 = time.monotonic()
    SetupService(db).compute_and_store_all()
    return {"status": "ok", "elapsed_seconds": round(time.monotonic() - t0, 2)}


@router.post("/refresh-regime")
def refresh_regime(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> dict:
    """Manually trigger regime ETF refresh + market regime score recompute.

    Equivalent to the nightly 22:15 UTC cron. Fetches 400 days of history for
    14 regime ETFs from FMP, then recomputes and stores a new regime snapshot.
    """
    t0 = time.monotonic()
    etf_result = MarketRefreshService(db=db, fmp=fmp).refresh_regime_etfs()
    snapshot = MarketRegimeService(db).compute_and_store()
    return {
        "status": "ok",
        "etf_completed": etf_result.completed,
        "etf_failed": etf_result.failed,
        "regime": snapshot.regime,
        "market_score": snapshot.market_score,
        "date": str(snapshot.date),
        "elapsed_seconds": round(time.monotonic() - t0, 2),
    }


@router.post("/refresh-scanner")
def refresh_scanner(
    db: Session = Depends(get_db),
    fmp: FmpClient = Depends(get_fmp_client),
) -> dict:
    """Manually trigger a full market breakout scan.

    Equivalent to the daily 06:15 UTC cron. Scans the full pool universe
    (~500 tickers) for MA150 breakout/pullback signals. Takes 3-6 minutes
    due to FMP rate limits. Returns scan summary.
    """
    t0 = time.monotonic()
    result = MarketScannerService(db=db, fmp=fmp).run_scan()
    return {
        "status": result.status,
        "scanned": result.scanned,
        "hits": result.hits,
        "failed": result.failed,
        "hits_by_type": result.hits_by_type,
        "scan_date": str(result.scan_date),
        "elapsed_seconds": round(time.monotonic() - t0, 2),
    }
