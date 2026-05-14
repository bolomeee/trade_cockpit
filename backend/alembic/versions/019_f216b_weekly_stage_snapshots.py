"""F216-b: weekly_stage_snapshots table — Stan Weinstein Stage 1-4 per-ticker weekly snapshot

Revision ID: 019_f216b_weekly_stage_snapshots
Revises: 018_f215b_setup_volume_accumulation
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "019_f216b_weekly_stage_snapshots"
down_revision = "018_f215b_setup_volume_accumulation"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "weekly_stage_snapshots",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("scan_date", sa.Date(), nullable=False),
        sa.Column("stage", sa.Integer(), nullable=False),
        sa.Column("weekly_close", sa.Float(), nullable=True),
        sa.Column("weekly_ma_10", sa.Float(), nullable=True),
        sa.Column("weekly_ma_30", sa.Float(), nullable=True),
        sa.Column("weekly_ma_40", sa.Float(), nullable=True),
        sa.Column("slope_30w", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "scan_date", name="uq_weekly_stage_ticker_date"),
    )
    op.create_index("ix_weekly_stage_snapshots_ticker", "weekly_stage_snapshots", ["ticker"])
    op.create_index("ix_weekly_stage_snapshots_scan_date", "weekly_stage_snapshots", ["scan_date"])


def downgrade() -> None:
    op.drop_index("ix_weekly_stage_snapshots_scan_date", table_name="weekly_stage_snapshots")
    op.drop_index("ix_weekly_stage_snapshots_ticker", table_name="weekly_stage_snapshots")
    op.drop_table("weekly_stage_snapshots")
