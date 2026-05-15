"""F217-b1: setup_snapshots.legacy column + soft-delete PULLBACK rows

Revision ID: 021_f217b1_setup_snapshots_legacy
Revises: 020_f216d1_setup_weekly_stage_column
Create Date: 2026-05-15
"""
from alembic import op
import sqlalchemy as sa

revision = "021_f217b1_setup_snapshots_legacy"
down_revision = "020_f216d1_setup_weekly_stage_column"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # Step 1: add column with server_default so all existing rows get legacy=0
    op.add_column(
        "setup_snapshots",
        sa.Column("legacy", sa.Boolean(), nullable=False, server_default=sa.false()),
    )
    # Step 2: soft-delete all historical PULLBACK rows (SQLite stores Boolean as 0/1)
    op.execute("UPDATE setup_snapshots SET legacy = 1 WHERE setup_type = 'PULLBACK'")
    # Step 3: remove server_default via batch mode (required for SQLite ALTER COLUMN support)
    # ORM default=False takes over for new inserts; avoids dual-default-source divergence
    with op.batch_alter_table("setup_snapshots") as batch_op:
        batch_op.alter_column(
            "legacy",
            existing_type=sa.Boolean(),
            existing_nullable=False,
            existing_server_default=sa.false(),
            server_default=None,
        )


def downgrade() -> None:
    # Drop the column; original PULLBACK rows become visible again (downgrade semantics)
    op.drop_column("setup_snapshots", "legacy")
