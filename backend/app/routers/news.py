from __future__ import annotations

from fastapi import APIRouter, Depends, Query

from app.dependencies import get_fmp_client
from app.external.fmp_client import FmpClient
from app.schemas.news import NewsArticle
from app.schemas.watchlist import ResponseEnvelope
from app.services.news_service import DEFAULT_LIMIT, MAX_LIMIT, NewsService

router = APIRouter(prefix="/api/news", tags=["news"])


def get_news_service(fmp: FmpClient = Depends(get_fmp_client)) -> NewsService:
    return NewsService(fmp)


@router.get("/articles", response_model=ResponseEnvelope[list[NewsArticle]])
def list_news_articles(
    limit: int = Query(DEFAULT_LIMIT, ge=1, le=MAX_LIMIT),
    service: NewsService = Depends(get_news_service),
) -> ResponseEnvelope[list[NewsArticle]]:
    items = service.list_articles(limit=limit)
    return ResponseEnvelope(data=items)
