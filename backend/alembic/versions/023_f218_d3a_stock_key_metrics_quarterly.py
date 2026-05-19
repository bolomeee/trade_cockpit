"""F218-d3a: create stock_key_metrics_quarterly table + UQ + index

Revision ID: f218_d3a_key_metrics_quarterly
Revises: 022_f218_repricing_triggers
Create Date: 2026-05-19
"""
from alembic import op
import sqlalchemy as sa

revision = "f218_d3a_key_metrics_quarterly"
down_revision = "022_f218_repricing_triggers"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "stock_key_metrics_quarterly",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("fiscal_quarter", sa.String(length=12), nullable=False),
        sa.Column("period_end_date", sa.Date(), nullable=False),
        sa.Column("gross_margin", sa.Float(), nullable=True),
        sa.Column("op_margin", sa.Float(), nullable=True),
        sa.Column("net_margin", sa.Float(), nullable=True),
        sa.Column("fcf_margin", sa.Float(), nullable=True),
        sa.Column("roic", sa.Float(), nullable=True),
        sa.Column("fetched_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "ticker", "fiscal_quarter",
            name="uq_key_metrics_ticker_quarter",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_stock_key_metrics_quarterly_ticker", "stock_key_metrics_quarterly", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_stock_key_metrics_quarterly_ticker", table_name="stock_key_metrics_quarterly")
    op.drop_table("stock_key_metrics_quarterly")
