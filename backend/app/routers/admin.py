"""Admin endpoints: manual triggers for background jobs.

POST /api/admin/refresh-universe    — trigger UniverseRefreshService.refresh().
POST /api/admin/refresh-pool-cache  — trigger PoolCacheService.rebuild() (F205-e Q5=B).
POST /api/admin/refresh-earnings    — trigger EarningsService.fetch_and_store().
POST /api/admin/refresh-setup       — trigger SetupService.compute_and_store_all().
"""
from __future__ import annotations

import time

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.services.cockpit.earnings_service import EarningsService
from app.services.cockpit.pool_cache_service import PoolCacheService
from app.services.cockpit.setup_service import SetupService
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
