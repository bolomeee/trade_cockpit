from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from app.routers import signals, stocks, watchlist
from app.services.watchlist_service import APIError

app = FastAPI(title="MA150 Tracker API", version="0.1.0")


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
