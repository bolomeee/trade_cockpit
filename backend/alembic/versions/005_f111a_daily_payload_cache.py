"""F111-a daily_payload_cache table

Revision ID: 005_f111a_daily_payload_cache
Revises: 004_f107b1_shares_float
Create Date: 2026-04-22

F111-a on-demand ticker 数据当日缓存（D055）：
- `daily_payload_cache` 表存储非 watchlist ticker 的 chart/fundamentals 响应 JSON
- 联合唯一键 (ticker, endpoint, as_of_date) 保证每日每端点只写一条
- 有效期 = 当日（service 层判断 as_of_date == date.today()）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "005_f111a_daily_payload_cache"
down_revision: Union[str, Sequence[str], None] = "004_f107b1_shares_float"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "daily_payload_cache",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("endpoint", sa.String(20), nullable=False),
        sa.Column("as_of_date", sa.Date(), nullable=False),
        sa.Column("payload_json", sa.Text(), nullable=False),
        sa.Column("cached_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "endpoint", "as_of_date",
            name="uq_daily_payload_cache_ticker_endpoint_date",
        ),
    )
    op.create_index(
        "ix_daily_payload_cache_ticker",
        "daily_payload_cache",
        ["ticker"],
    )


def downgrade() -> None:
    op.drop_index("ix_daily_payload_cache_ticker", table_name="daily_payload_cache")
    op.drop_table("daily_payload_cache")
