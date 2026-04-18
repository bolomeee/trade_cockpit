import os
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.database import SessionLocal
from app.external.polygon_client import PolygonClient
from app.routers import data, journal, logs, market, signals, stocks, watchlist
from app.services.refresh_job import shutdown_scheduler, start_scheduler
from app.services.watchlist_service import APIError


def _polygon_factory() -> PolygonClient:
    return PolygonClient()


@asynccontextmanager
async def lifespan(_: FastAPI):
    if os.getenv("MA150_DISABLE_SCHEDULER") != "1":
        start_scheduler(SessionLocal, _polygon_factory)
    try:
        yield
    finally:
        shutdown_scheduler()


app = FastAPI(title="MA150 Tracker API", version="0.1.0", lifespan=lifespan)


@app.exception_handler(APIError)
async def handle_api_error(_: Request, exc: APIError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={"error": {"code": exc.code, "message": exc.message}},
    )


@app.exception_handler(RequestValidationError)
async def handle_validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content={
            "error": {
                "code": "VALIDATION_ERROR",
                "message": "; ".join(
                    f"{'.'.join(str(p) for p in e['loc'])}: {e['msg']}" for e in exc.errors()
                )
                or "validation failed",
            }
        },
    )


@app.get("/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(watchlist.router)
app.include_router(stocks.router)
app.include_router(signals.router)
app.include_router(data.router)
app.include_router(market.router)
app.include_router(journal.router)
app.include_router(logs.router)
