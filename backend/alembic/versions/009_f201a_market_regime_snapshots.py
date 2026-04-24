"""F201-a market_regime_snapshots table

Revision ID: 009_f201a_market_regime_snapshots
Revises: 008_f204_earnings_events
Create Date: 2026-04-24

F201-a 数据层：
- `market_regime_snapshots` 按 date 唯一（每日一条 regime 打分快照）
- 保留最近 90 天（F201-b cron job 负责清理）
- 仅 cockpit 服务消费（D061）
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "009_f201a_market_regime_snapshots"
down_revision: Union[str, Sequence[str], None] = "008_f204_earnings_events"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "market_regime_snapshots",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("date", sa.Date(), nullable=False),
        sa.Column("regime", sa.String(16), nullable=False),
        sa.Column("market_score", sa.Integer(), nullable=False),
        sa.Column("spy_trend_score", sa.Integer(), nullable=False),
        sa.Column("qqq_trend_score", sa.Integer(), nullable=False),
        sa.Column("iwm_breadth_score", sa.Integer(), nullable=False),
        sa.Column("sector_participation_score", sa.Integer(), nullable=False),
        sa.Column("risk_appetite_score", sa.Integer(), nullable=False),
        sa.Column("volatility_stress_score", sa.Integer(), nullable=False),
        sa.Column("allowed_exposure_pct", sa.Float(), nullable=False),
        sa.Column("single_trade_risk_pct", sa.Float(), nullable=False),
        sa.Column("preferred_setups", sa.Text(), nullable=False),
        sa.Column("avoid_setups", sa.Text(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint("date", name="uq_market_regime_date"),
    )
    op.create_index(
        "ix_market_regime_snapshots_date",
        "market_regime_snapshots",
        ["date"],
    )


def downgrade() -> None:
    op.drop_index("ix_market_regime_snapshots_date", table_name="market_regime_snapshots")
    op.drop_table("market_regime_snapshots")
