"""News schemas (F112-a).

Outward-facing shape of the `/api/news/articles` response items. Raw FMP
`/stable/fmp-articles` payload is normalized by `NewsService` before reaching
this model.
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
