"""F211-d1: journal_entries.ai_review (Text/JSON, nullable) + ai_review_memo_id (Integer, nullable)

Revision ID: 017_f211d1_journal_entries_ai_review
Revises: 016_f205e_pool_cache
Create Date: 2026-04-29
"""
from alembic import op
import sqlalchemy as sa

revision = "017_f211d1_journal_entries_ai_review"
down_revision = "016_f205e_pool_cache"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column("journal_entries", sa.Column("ai_review", sa.Text(), nullable=True))
    op.add_column("journal_entries", sa.Column("ai_review_memo_id", sa.Integer(), nullable=True))
    # No FK constraint on ai_review_memo_id — D069 ai_memos 180-day rolling cleanup would block FK


def downgrade() -> None:
    op.drop_column("journal_entries", "ai_review_memo_id")
    op.drop_column("journal_entries", "ai_review")
