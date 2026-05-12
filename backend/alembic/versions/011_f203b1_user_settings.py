"""F203-b1 user_settings table (single-row settings with default data migration)

Revision ID: 011_f203b1_user_settings
Revises: 010_f202a_setup_snapshots
Create Date: 2026-04-25

F203-b1 数据层：
- `user_settings` 单行表（CHECK id=1），存储账户风控参数
- 建表后立即 INSERT 默认行（data migration，raw SQL 避免 model import 时序问题）
- D066：持久化走 DB，不走 localStorage
- D070：4 字段不进 cockpit_params.py，进 DB
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "011_f203b1_user_settings"
down_revision: Union[str, None] = "010_f202a_setup_snapshots"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "user_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("account_size", sa.Float(), nullable=False, server_default=sa.text("100000.0")),
        sa.Column("max_exposure_pct", sa.Float(), nullable=False, server_default=sa.text("80.0")),
        sa.Column("single_trade_risk_pct", sa.Float(), nullable=False, server_default=sa.text("1.0")),
        sa.Column("default_risk_per_trade_pct", sa.Float(), nullable=False, server_default=sa.text("0.75")),
        sa.Column("base_currency", sa.String(8), nullable=False, server_default=sa.text("'USD'")),
        sa.Column("updated_at", sa.DateTime(), nullable=False),
        sa.CheckConstraint("id = 1", name="ck_user_settings_single_row"),
    )
    op.execute(
        "INSERT INTO user_settings "
        "(id, account_size, max_exposure_pct, single_trade_risk_pct, "
        "default_risk_per_trade_pct, base_currency, updated_at) "
        "VALUES (1, 100000.0, 80.0, 1.0, 0.75, 'USD', CURRENT_TIMESTAMP)"
    )


def downgrade() -> None:
    op.drop_table("user_settings")
