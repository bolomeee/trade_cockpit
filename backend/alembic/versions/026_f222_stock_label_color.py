"""F222-a: stocks label_color column (Watchlist color tagging)

Revision ID: 026_f222_stock_label_color
Revises: 025_f219a_setup_macd_divergence
Create Date: 2026-07-02
"""
from alembic import op
import sqlalchemy as sa

revision = "026_f222_stock_label_color"
down_revision = "025_f219a_setup_macd_divergence"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "stocks",
        sa.Column("label_color", sa.String(10), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("stocks", "label_color")
