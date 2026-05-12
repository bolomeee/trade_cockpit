"""F204-a earnings_events table

Revision ID: 008_f204_earnings_events
Revises: 007_f113b_backfill_news_symbols
Create Date: 2026-04-24

F204-a 数据层：
- `earnings_events` 按 (ticker, earnings_date) 唯一
- 每日 APScheduler 增量 upsert FMP earnings-calendar（F204-b 接入）
- 仅 cockpit 服务消费（D065）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "008_f204_earnings_events"
down_revision: Union[str, Sequence[str], None] = "007_f113b_backfill_news_symbols"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "earnings_events",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("earnings_date", sa.Date(), nullable=False),
        sa.Column("eps_estimate", sa.Float(), nullable=True),
        sa.Column("eps_actual", sa.Float(), nullable=True),
        sa.Column("revenue_estimate", sa.BigInteger(), nullable=True),
        sa.Column("revenue_actual", sa.BigInteger(), nullable=True),
        sa.Column("time_of_day", sa.String(8), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "ticker", "earnings_date",
            name="uq_earnings_event_ticker_date",
        ),
    )
    op.create_index("ix_earnings_events_ticker", "earnings_events", ["ticker"])
    op.create_index("ix_earnings_events_earnings_date", "earnings_events", ["earnings_date"])


def downgrade() -> None:
    op.drop_index("ix_earnings_events_earnings_date", table_name="earnings_events")
    op.drop_index("ix_earnings_events_ticker", table_name="earnings_events")
    op.drop_table("earnings_events")
