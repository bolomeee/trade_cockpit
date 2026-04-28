"""F205-e: cockpit_pool_cache — RS + fundamental weekly cache

Revision ID: 016_f205e_pool_cache
Revises: 015_f205a_universe_extra_fields
Create Date: 2026-04-28
"""
from alembic import op
import sqlalchemy as sa

revision = "016_f205e_pool_cache"
down_revision = "015_f205a_universe_extra_fields"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "cockpit_pool_cache",
        sa.Column("ticker", sa.Text(), nullable=False),
        sa.Column("rs_percentile", sa.Float(), nullable=False),
        sa.Column("ma50", sa.Float(), nullable=True),
        sa.Column("last_close", sa.Float(), nullable=True),
        sa.Column("revenue_growth_yoy", sa.Float(), nullable=True),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("ticker"),
    )
    op.create_index(
        "ix_cockpit_pool_cache_computed_at",
        "cockpit_pool_cache",
        ["computed_at"],
    )


def downgrade() -> None:
    op.drop_index("ix_cockpit_pool_cache_computed_at", table_name="cockpit_pool_cache")
    op.drop_table("cockpit_pool_cache")
