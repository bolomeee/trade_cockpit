"""F202-a setup_snapshots table

Revision ID: 010_f202a_setup_snapshots
Revises: 009_f201a_market_regime_snapshots
Create Date: 2026-04-25

F202-a 数据层：
- `setup_snapshots` 按 (ticker, scan_date) 唯一（cockpit watchlist 每日 setup 快照）
- 保留最近 60 天（F202-b cron job 负责清理，D062）
- 不设外键（与 market_breakout_scans 一致）
- 仅 cockpit 服务消费
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "010_f202a_setup_snapshots"
down_revision: Union[str, None] = "009_f201a_market_regime_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "setup_snapshots",
        sa.Column("id", sa.Integer(), nullable=False),
        sa.Column("ticker", sa.String(10), nullable=False),
        sa.Column("scan_date", sa.Date(), nullable=False),
        sa.Column("setup_type", sa.String(24), nullable=False),
        sa.Column("setup_quality", sa.String(1), nullable=True),
        sa.Column("entry_price", sa.Float(), nullable=True),
        sa.Column("stop_price", sa.Float(), nullable=True),
        sa.Column("target_2r", sa.Float(), nullable=True),
        sa.Column("target_3r", sa.Float(), nullable=True),
        sa.Column("distance_to_entry_pct", sa.Float(), nullable=True),
        sa.Column("reward_risk", sa.Float(), nullable=True),
        sa.Column("rs_percentile", sa.Float(), nullable=True),
        sa.Column("volume_status", sa.String(8), nullable=True),
        sa.Column("trend_score", sa.Integer(), nullable=True),
        sa.Column("earnings_risk", sa.String(8), nullable=False),
        sa.Column("ready_signal", sa.Boolean(), nullable=False),
        sa.Column("suggested_action", sa.String(16), nullable=True),
        sa.Column("scanned_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("ticker", "scan_date", name="uq_setup_snapshot_ticker_date"),
    )
    op.create_index("ix_setup_snapshots_scan_date", "setup_snapshots", ["scan_date"])
    op.create_index("ix_setup_snapshots_ticker", "setup_snapshots", ["ticker"])


def downgrade() -> None:
    op.drop_index("ix_setup_snapshots_ticker", table_name="setup_snapshots")
    op.drop_index("ix_setup_snapshots_scan_date", table_name="setup_snapshots")
    op.drop_table("setup_snapshots")
