"""F107-b1 shares_float columns on stocks

Revision ID: 004_f107b1_shares_float
Revises: 003_f106_signal_type_and_volume
Create Date: 2026-04-22

F107-b1 Vol/Float 比率后端链路（D049/D050）：
- `shares_float` (BigInteger, nullable) — FMP /stable/shares-float 的 floatShares (D051 rev)
- `shares_float_refreshed_at` (DateTime, nullable) — 24h TTL 缓存戳
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "004_f107b1_shares_float"
down_revision: Union[str, Sequence[str], None] = "003_f106_signal_type_and_volume"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    with op.batch_alter_table("stocks", schema=None) as batch_op:
        batch_op.add_column(
            sa.Column("shares_float", sa.BigInteger(), nullable=True)
        )
        batch_op.add_column(
            sa.Column(
                "shares_float_refreshed_at", sa.DateTime(), nullable=True
            )
        )


def downgrade() -> None:
    with op.batch_alter_table("stocks", schema=None) as batch_op:
        batch_op.drop_column("shares_float_refreshed_at")
        batch_op.drop_column("shares_float")
