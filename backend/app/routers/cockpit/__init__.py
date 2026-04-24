from fastapi import APIRouter

from app.routers.cockpit import earnings

router = APIRouter()
router.include_router(earnings.router)
