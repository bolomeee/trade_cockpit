"""F105 market scan tables

Revision ID: 002_f105_market_scan_tables
Revises: 001_initial
Create Date: 2026-04-20

New tables for F105 Market Breakout Scanner (D038 / D040):
- market_scan_universe: 市值≥500亿美元的候选池，月级刷新
- market_breakout_scans: 每日 breakout 快照，覆盖写入
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "002_f105_market_scan_tables"
down_revision: Union[str, Sequence[str], None] = "001_initial"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_scan_universe",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("exchange", sa.String(length=20), nullable=False),
        sa.Column("market_cap", sa.BigInteger(), nullable=False),
        sa.Column("last_seen_at", sa.DateTime(), nullable=False),
        sa.Column("added_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    with op.batch_alter_table("market_scan_universe", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_market_scan_universe_ticker"), ["ticker"], unique=True
        )

    op.create_table(
        "market_breakout_scans",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("scan_date", sa.Date(), nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("company_name", sa.String(length=200), nullable=False),
        sa.Column("close_price", sa.Float(), nullable=False),
        sa.Column("ma150_value", sa.Float(), nullable=False),
        sa.Column("pct_above_ma150", sa.Float(), nullable=False),
        sa.Column("slope_value", sa.Float(), nullable=False),
        sa.Column("market_cap", sa.BigInteger(), nullable=False),
        sa.Column("scanned_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint(
            "scan_date", "ticker", name="uq_breakout_scan_date_ticker"
        ),
    )
    with op.batch_alter_table("market_breakout_scans", schema=None) as batch_op:
        batch_op.create_index(
            batch_op.f("ix_market_breakout_scans_scan_date"),
            ["scan_date"],
            unique=False,
        )
        batch_op.create_index(
            batch_op.f("ix_market_breakout_scans_scanned_at"),
            ["scanned_at"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("market_breakout_scans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_market_breakout_scans_scanned_at"))
        batch_op.drop_index(batch_op.f("ix_market_breakout_scans_scan_date"))
    op.drop_table("market_breakout_scans")

    with op.batch_alter_table("market_scan_universe", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_market_scan_universe_ticker"))
    op.drop_table("market_scan_universe")
