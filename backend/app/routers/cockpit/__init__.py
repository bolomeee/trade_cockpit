from fastapi import APIRouter

from app.routers.cockpit import earnings, regime

router = APIRouter()
router.include_router(earnings.router)
router.include_router(regime.router)
