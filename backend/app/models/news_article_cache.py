from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import Column, Date, DateTime, Index, Integer, String, Text, UniqueConstraint

from app.models import Base


class NewsArticleCache(Base):
    __tablename__ = "news_articles_cache"
    __table_args__ = (
        UniqueConstraint(
            "as_of_date", "article_key",
            name="uq_news_articles_cache_date_key",
        ),
        Index(
            "ix_news_articles_cache_date_published",
            "as_of_date", "published_at",
        ),
    )

    id = Column(Integer, primary_key=True, autoincrement=True)
    article_key = Column(String(512), nullable=False)
    published_at = Column(DateTime, nullable=False, index=True)
    as_of_date = Column(Date, nullable=False, index=True)
    payload_json = Column(Text, nullable=False)
    cached_at = Column(
        DateTime,
        nullable=False,
        default=lambda: datetime.now(timezone.utc).replace(tzinfo=None),
    )
