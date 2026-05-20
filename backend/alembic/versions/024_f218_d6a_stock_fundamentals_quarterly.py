"""F218-d6a: create stock_fundamentals_quarterly table + UQ + index

Revision ID: f218_d6a_fundamentals_quarterly
Revises: f218_d3a_key_metrics_quarterly
Create Date: 2026-05-20
"""
from alembic import op
import sqlalchemy as sa

revision = "f218_d6a_fundamentals_quarterly"
down_revision = "f218_d3a_key_metrics_quarterly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_fundamentals_quarterly",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("fiscal_quarter", sa.String(length=12), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("total_debt", sa.BigInteger(), nullable=True),
        sa.Column("cash", sa.BigInteger(), nullable=True),
        sa.Column("net_debt", sa.BigInteger(), nullable=True),
        sa.Column("fcf", sa.BigInteger(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "ticker", "fiscal_quarter",
            name="uq_fundamentals_ticker_quarter",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_fundamentals_quarterly_ticker", "stock_fundamentals_quarterly", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_stock_fundamentals_quarterly_ticker", table_name="stock_fundamentals_quarterly")
    op.drop_table("stock_fundamentals_quarterly")
