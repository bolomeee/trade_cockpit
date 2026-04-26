"""F206-a positions table

Revision ID: 013_f206a_positions
Revises: 012_f208a_ai_memos
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = "013_f206a_positions"
down_revision = "012_f208a_ai_memos"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "positions",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("entry_date", sa.Date(), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("stop_price", sa.Float(), nullable=False),
        sa.Column("target_2r", sa.Float(), nullable=True),
        sa.Column("target_3r", sa.Float(), nullable=True),
        sa.Column("setup_type", sa.String(24), nullable=True),
        sa.Column("notes", sa.Text(), nullable=True),
        sa.Column("status", sa.String(8), nullable=False, server_default="OPEN"),
        sa.Column("closed_at", sa.DateTime(timezone=True), nullable=True),
        sa.Column("close_price", sa.Float(), nullable=True),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.PrimaryKeyConstraint("id"),
        sa.CheckConstraint("status IN ('OPEN', 'CLOSED')", name="ck_positions_status"),
        sa.CheckConstraint("shares > 0", name="ck_positions_shares_positive"),
    )
    op.create_index("ix_positions_ticker", "positions", ["ticker"])
    op.create_index("ix_positions_status", "positions", ["status"])


def downgrade() -> None:
    op.drop_index("ix_positions_status", table_name="positions")
    op.drop_index("ix_positions_ticker", table_name="positions")
    op.drop_table("positions")
