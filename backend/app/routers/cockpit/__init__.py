from fastapi import APIRouter

from app.routers.cockpit import earnings, regime, setup
from app.routers.cockpit.chart import router as chart_router

router = APIRouter()
router.include_router(earnings.router)
router.include_router(regime.router)
router.include_router(setup.router)
router.include_router(chart_router)
