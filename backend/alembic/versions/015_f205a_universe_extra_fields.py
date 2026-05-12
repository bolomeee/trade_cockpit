"""F205-a universe extra fields: sector, industry, last_price, last_volume

Revision ID: 015_f205a_universe_extra_fields
Revises: 014_f206b1_pending_orders
Create Date: 2026-04-27
"""
from alembic import op
import sqlalchemy as sa

revision = "015_f205a_universe_extra_fields"
down_revision = "014_f206b1_pending_orders"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("market_scan_universe", sa.Column("sector", sa.String(64), nullable=True))
    op.add_column("market_scan_universe", sa.Column("industry", sa.String(128), nullable=True))
    op.add_column("market_scan_universe", sa.Column("last_price", sa.Float(), nullable=True))
    op.add_column("market_scan_universe", sa.Column("last_volume", sa.BigInteger(), nullable=True))


def downgrade() -> None:
    op.drop_column("market_scan_universe", "last_volume")
    op.drop_column("market_scan_universe", "last_price")
    op.drop_column("market_scan_universe", "industry")
    op.drop_column("market_scan_universe", "sector")
