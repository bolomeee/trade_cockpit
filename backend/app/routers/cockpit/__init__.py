from fastapi import APIRouter

from app.routers.cockpit import earnings, regime, setup
from app.routers.cockpit.actions import router as actions_router
from app.routers.cockpit.chart import router as chart_router
from app.routers.cockpit.decision import router as decision_router
from app.routers.cockpit.pending_orders import router as pending_orders_router
from app.routers.cockpit.positions import router as positions_router
from app.routers.cockpit.user_settings import router as user_settings_router

router = APIRouter()
router.include_router(earnings.router)
router.include_router(regime.router)
router.include_router(setup.router)
router.include_router(chart_router)
router.include_router(user_settings_router)
router.include_router(decision_router)
router.include_router(positions_router)
router.include_router(pending_orders_router)
router.include_router(actions_router)
