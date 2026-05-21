"""F219-a: setup_snapshots macd_divergence column (MACD divergence detection)

Revision ID: 025_f219a_setup_macd_divergence
Revises: 024_f218_d6a_stock_fundamentals_quarterly
Create Date: 2026-05-21
"""
from alembic import op
import sqlalchemy as sa

revision = "025_f219a_setup_macd_divergence"
down_revision = "f218_d6a_fundamentals_quarterly"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "setup_snapshots",
        sa.Column("macd_divergence", sa.String(8), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("setup_snapshots", "macd_divergence")
