from __future__ import annotations

from datetime import datetime
from typing import Literal

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.news import NewsListResponse
from app.services.news_service import DEFAULT_LIMIT, MAX_LIMIT, NewsService

router = APIRouter(prefix="/api/news", tags=["news"])


def get_news_service(
    fmp: FmpClient = Depends(get_fmp_client),
    db: Session = Depends(get_db),
) -> NewsService:
    return NewsService(fmp, db)


@router.get("/articles", response_model=NewsListResponse)
def list_news_articles(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    since: datetime | None = Query(None),
    window: Literal["calendar-1d", "none"] = Query("calendar-1d"),
    service: NewsService = Depends(get_news_service),
) -> NewsListResponse:
    result = service.list_articles(limit=limit, since=since, window=window)
    return NewsListResponse(data=result.articles, meta=result.meta)
