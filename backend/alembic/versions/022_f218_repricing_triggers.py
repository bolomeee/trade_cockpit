"""F218-d1: create repricing_triggers table + UQ + 3 indexes

Revision ID: 022_f218_repricing_triggers
Revises: 021_f217b1_setup_snapshots_legacy
Create Date: 2026-05-18
"""
from alembic import op
import sqlalchemy as sa

revision = "022_f218_repricing_triggers"
down_revision = "021_f217b1_setup_snapshots_legacy"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "repricing_triggers",
        sa.Column("id", sa.Integer(), autoincrement=True, nullable=False),
        sa.Column("ticker", sa.String(length=10), nullable=False),
        sa.Column("trigger_type", sa.String(length=24), nullable=False),
        sa.Column("detected_date", sa.Date(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("evidence_json", sa.Text(), nullable=False),
        sa.Column("active", sa.Boolean(), nullable=False),
        sa.Column("computed_at", sa.DateTime(), nullable=False),
        sa.UniqueConstraint(
            "ticker", "trigger_type", "detected_date",
            name="uq_repricing_trigger_ticker_type_date",
        ),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index("ix_repricing_triggers_ticker", "repricing_triggers", ["ticker"])
    op.create_index("ix_repricing_triggers_detected_date", "repricing_triggers", ["detected_date"])
    op.create_index("ix_repricing_triggers_active", "repricing_triggers", ["active"])


def downgrade() -> None:
    op.drop_index("ix_repricing_triggers_active", table_name="repricing_triggers")
    op.drop_index("ix_repricing_triggers_detected_date", table_name="repricing_triggers")
    op.drop_index("ix_repricing_triggers_ticker", table_name="repricing_triggers")
    op.drop_table("repricing_triggers")
