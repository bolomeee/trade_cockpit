"""F215-b: setup_snapshots volume accumulation columns (volume_zscore, obv_trend, up_down_volume_ratio)

Revision ID: 018_f215b_setup_volume_accumulation
Revises: 017_f211d1_journal_entries_ai_review
Create Date: 2026-05-13
"""
from alembic import op
import sqlalchemy as sa

revision = "018_f215b_setup_volume_accumulation"
down_revision = "017_f211d1_journal_entries_ai_review"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "setup_snapshots",
        sa.Column("volume_zscore", sa.Float(), nullable=True),
    )
    op.add_column(
        "setup_snapshots",
        sa.Column("obv_trend", sa.String(4), nullable=True),
    )
    op.add_column(
        "setup_snapshots",
        sa.Column("up_down_volume_ratio", sa.Float(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("setup_snapshots", "up_down_volume_ratio")
    op.drop_column("setup_snapshots", "obv_trend")
    op.drop_column("setup_snapshots", "volume_zscore")
