"""F206-b1 pending_orders table

Revision ID: 014_f206b1_pending_orders
Revises: 013_f206a_positions
Create Date: 2026-04-26
"""
from alembic import op
import sqlalchemy as sa

revision = "014_f206b1_pending_orders"
down_revision = "013_f206a_positions"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "pending_orders",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("setup_type", sa.String(24), nullable=False),
        sa.Column("entry_price", sa.Float(), nullable=False),
        sa.Column("stop_price", sa.Float(), nullable=False),
        sa.Column("shares", sa.Integer(), nullable=False),
        sa.Column("target_2r", sa.Float(), nullable=True),
        sa.Column("target_3r", sa.Float(), nullable=True),
        sa.Column("expiration_date", sa.Date(), nullable=True),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("notes", sa.Text(), nullable=True),
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
        sa.CheckConstraint(
            "status IN ('ACTIVE', 'TRIGGERED', 'CANCELLED', 'EXPIRED')",
            name="ck_pending_orders_status",
        ),
        sa.CheckConstraint("shares > 0", name="ck_pending_orders_shares_positive"),
    )
    op.create_index("ix_pending_orders_ticker", "pending_orders", ["ticker"])
    op.create_index("ix_pending_orders_status", "pending_orders", ["status"])


def downgrade() -> None:
    op.drop_index("ix_pending_orders_status", table_name="pending_orders")
    op.drop_index("ix_pending_orders_ticker", table_name="pending_orders")
    op.drop_table("pending_orders")
