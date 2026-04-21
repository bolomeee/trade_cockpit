"""F106 signal_type + volume columns

Revision ID: 003_f106_signal_type_and_volume
Revises: 002_f105_market_scan_tables
Create Date: 2026-04-21

F106 Multi-Signal Scanner (D045):
- Adds `signal_type` (NOT NULL, default 'legacy_crossover' for any existing rows).
- Adds `volume` (nullable) and `volume_ratio_20` (nullable).
- Replaces unique constraint (scan_date, ticker) with (scan_date, ticker, signal_type).
- Adds index on signal_type for filter queries.
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "003_f106_signal_type_and_volume"
down_revision: Union[str, Sequence[str], None] = "002_f105_market_scan_tables"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("market_breakout_scans", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column(
                "signal_type",
                sa.String(length=32),
                nullable=False,
                server_default="legacy_crossover",
            )
        )
        batch_op.add_column(
            sa.Column("volume", sa.BigInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column("volume_ratio_20", sa.Float(), nullable=True)
        )
        batch_op.drop_constraint(
            "uq_breakout_scan_date_ticker", type_="unique"
        )
        batch_op.create_unique_constraint(
            "uq_breakout_scan_date_ticker_signal",
            ["scan_date", "ticker", "signal_type"],
        )
        batch_op.create_index(
            batch_op.f("ix_market_breakout_scans_signal_type"),
            ["signal_type"],
            unique=False,
        )


def downgrade() -> None:
    with op.batch_alter_table("market_breakout_scans", schema=None) as batch_op:
        batch_op.drop_index(batch_op.f("ix_market_breakout_scans_signal_type"))
        batch_op.drop_constraint(
            "uq_breakout_scan_date_ticker_signal", type_="unique"
        )
        batch_op.create_unique_constraint(
            "uq_breakout_scan_date_ticker", ["scan_date", "ticker"]
        )
        batch_op.drop_column("volume_ratio_20")
        batch_op.drop_column("volume")
        batch_op.drop_column("signal_type")
