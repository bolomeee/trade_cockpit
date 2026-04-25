"""F208-a ai_memos table + composite indexes

Revision ID: 012_f208a_ai_memos
Revises: 011_f203b1_user_settings
Create Date: 2026-04-25
"""
from alembic import op
import sqlalchemy as sa

revision = "012_f208a_ai_memos"
down_revision = "011_f203b1_user_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_memos",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("task_type", sa.String(32), nullable=False),
        sa.Column("input_hash", sa.String(64), nullable=False),
        sa.Column("input_json", sa.Text(), nullable=False),
        sa.Column("output_json", sa.Text(), nullable=False),
        sa.Column("schema_version", sa.String(16), nullable=False),
        sa.Column("model_used", sa.String(64), nullable=False),
        sa.Column("tier", sa.String(16), nullable=False),
        sa.Column("tokens_in", sa.Integer(), nullable=False),
        sa.Column("tokens_out", sa.Integer(), nullable=False),
        sa.Column("cost_usd", sa.Numeric(10, 6), nullable=False),
        sa.Column("latency_ms", sa.Integer(), nullable=False),
        sa.Column("created_at", sa.DateTime(), nullable=False),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_ai_memos_task_type", "ai_memos", ["task_type"])
    op.create_index("ix_ai_memos_input_hash", "ai_memos", ["input_hash"])
    op.create_index("ix_ai_memos_created_at", "ai_memos", ["created_at"])
    # dedup query: (task_type, input_hash, created_at DESC)
    op.create_index(
        "ix_ai_memos_task_input_created",
        "ai_memos",
        ["task_type", "input_hash", sa.text("created_at DESC")],
    )
    # budget SUM monthly scan
    op.create_index(
        "ix_ai_memos_created_at_desc",
        "ai_memos",
        [sa.text("created_at DESC")],
    )


def downgrade() -> None:
    op.drop_index("ix_ai_memos_created_at_desc", table_name="ai_memos")
    op.drop_index("ix_ai_memos_task_input_created", table_name="ai_memos")
    op.drop_table("ai_memos")
