"""News cache repository (F113-a).

Responsibilities:
- compute_article_key: URL-first, SHA-256 fallback
- get_cached: read from news_articles_cache filtered by as_of_date / since / limit
- upsert_many: batch upsert by (as_of_date, article_key) unique key
"""
from __future__ import annotations

import hashlib
import json
from datetime import date, datetime, timezone

from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.models.news_article_cache import NewsArticleCache
from app.schemas.news import NewsArticle


def compute_article_key(article: NewsArticle) -> str:
    """URL-first dedup key; SHA-256(title|publishedAt[:19]) as fallback.

    Strips to 512 chars to match column width. publishedAt is truncated to
    second-precision to avoid same-article getting different hashes due to
    sub-second variance in FMP payloads.
    """
    if article.url:
        return article.url[:512]
    raw = f"{article.title}|{article.published_at[:19]}"
    return hashlib.sha256(raw.encode()).hexdigest()


def _parse_dt(iso: str) -> datetime:
    """Parse 'YYYY-MM-DDTHH:MM:SSZ' → naive UTC datetime. Falls back to now()."""
    try:
        return datetime.strptime(iso[:19], "%Y-%m-%dT%H:%M:%S")
    except ValueError:
        return datetime.now(timezone.utc).replace(tzinfo=None)


def get_cached(
    db: Session,
    as_of_dates: list[date],
    since: datetime | None,
    limit: int,
) -> list[NewsArticle]:
    """Return articles from cache for given as_of_dates, optionally filtered by since."""
    q = db.query(NewsArticleCache).filter(
        NewsArticleCache.as_of_date.in_(as_of_dates)
    )
    if since is not None:
        q = q.filter(NewsArticleCache.published_at > since)
    rows = q.order_by(NewsArticleCache.published_at.desc()).limit(limit).all()
    return [_row_to_article(r) for r in rows]


def upsert_many(db: Session, articles: list[NewsArticle], as_of: date) -> int:
    """Upsert articles into cache; returns count of newly inserted rows."""
    if not articles:
        return 0
    count = 0
    for article in articles:
        key = compute_article_key(article)
        existing = (
            db.query(NewsArticleCache)
            .filter_by(as_of_date=as_of, article_key=key)
            .first()
        )
        if existing is not None:
            continue
        row = NewsArticleCache(
            article_key=key,
            published_at=_parse_dt(article.published_at),
            as_of_date=as_of,
            payload_json=_serialize(article),
            cached_at=datetime.now(timezone.utc).replace(tzinfo=None),
        )
        db.add(row)
        count += 1
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
    return count


def _serialize(article: NewsArticle) -> str:
    return json.dumps({
        "title": article.title,
        "published_at": article.published_at,
        "content_html": article.content_html,
        "symbols": article.symbols,
        "image_url": article.image_url,
        "url": article.url,
        "author": article.author,
        "site": article.site,
    })


def _row_to_article(row: NewsArticleCache) -> NewsArticle:
    data = json.loads(row.payload_json)
    return NewsArticle(
        title=data.get("title", ""),
        published_at=data.get("published_at", ""),
        content_html=data.get("content_html", ""),
        symbols=data.get("symbols", []),
        image_url=data.get("image_url"),
        url=data.get("url"),
        author=data.get("author"),
        site=data.get("site"),
    )
