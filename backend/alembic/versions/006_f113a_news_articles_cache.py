"""F113-a news_articles_cache table

Revision ID: 006_f113a_news_articles_cache
Revises: 005_f111a_daily_payload_cache
Create Date: 2026-04-23

F113-a 后端 news 缓存：
- `news_articles_cache` 按 as_of_date + article_key 去重 upsert
- article_key = FMP link URL（首选）或 SHA-256(title+publishedAt)
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "006_f113a_news_articles_cache"
down_revision: Union[str, Sequence[str], None] = "005_f111a_daily_payload_cache"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "news_articles_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("article_key", sa.String(512), nullable=False),
        sa.Column("published_at", sa.DateTime(), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("cached_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "as_of_date", "article_key",
            name="uq_news_articles_cache_date_key",
        ),
    )
    op.create_index(
        "ix_news_articles_cache_published_at",
        "news_articles_cache",
        ["published_at"],
    )
    op.create_index(
        "ix_news_articles_cache_as_of_date",
        "news_articles_cache",
        ["as_of_date"],
    )
    op.create_index(
        "ix_news_articles_cache_date_published",
        "news_articles_cache",
        ["as_of_date", "published_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_news_articles_cache_date_published", table_name="news_articles_cache")
    op.drop_index("ix_news_articles_cache_as_of_date", table_name="news_articles_cache")
    op.drop_index("ix_news_articles_cache_published_at", table_name="news_articles_cache")
    op.drop_table("news_articles_cache")
