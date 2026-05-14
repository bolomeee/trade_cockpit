"""F216-d1: setup_snapshots weekly_stage column (Stan Weinstein gate prep)

Revision ID: 020_f216d1_setup_weekly_stage_column
Revises: 019_f216b_weekly_stage_snapshots
Create Date: 2026-05-14
"""
from alembic import op
import sqlalchemy as sa

revision = "020_f216d1_setup_weekly_stage_column"
down_revision = "019_f216b_weekly_stage_snapshots"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "setup_snapshots",
        sa.Column("weekly_stage", sa.Integer(), nullable=True),
    )


def downgrade() -> None:
    op.drop_column("setup_snapshots", "weekly_stage")
