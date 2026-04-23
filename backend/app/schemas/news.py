"""News schemas (F112-a / F113-a).

Outward-facing shape of the `/api/news/articles` response.
"""
from __future__ import annotations

from app.schemas.watchlist import CamelModel


class NewsArticle(CamelModel):
    title: str
    published_at: str
    content_html: str
    symbols: list[str]
    image_url: str | None = None
    url: str | None = None
    author: str | None = None
    site: str | None = None


class NewsListResponseMeta(CamelModel):
    cache_hit: bool
    fmp_calls: int
    truncated: bool
    fmp_error: bool = False


class NewsListResponse(CamelModel):
    data: list[NewsArticle]
    meta: NewsListResponseMeta
    message: str = "success"
