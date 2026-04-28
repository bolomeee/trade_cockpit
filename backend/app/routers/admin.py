"""Admin endpoints: manual triggers for background jobs.

POST /api/admin/refresh-pool-cache — trigger PoolCacheService.rebuild() (F205-e Q5=B).
"""
from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.services.cockpit.pool_cache_service import PoolCacheService

router = APIRouter(prefix="/api/admin", tags=["admin"])


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
