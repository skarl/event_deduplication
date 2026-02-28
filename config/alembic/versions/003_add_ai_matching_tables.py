"""Add AI matching cache and usage log tables.

Revision ID: 003_ai_matching
Revises: 002_pg_trgm_dates
Create Date: 2026-02-28
"""
from alembic import op
import sqlalchemy as sa

revision = "003_ai_matching"
down_revision = "002_pg_trgm_dates"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "ai_match_cache",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("pair_hash", sa.String(64), nullable=False),
        sa.Column("event_id_a", sa.String(), nullable=False),
        sa.Column("event_id_b", sa.String(), nullable=False),
        sa.Column("decision", sa.String(), nullable=False),
        sa.Column("confidence", sa.Float(), nullable=False),
        sa.Column("reasoning", sa.Text(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint("decision IN ('same', 'different')", name="ck_ai_match_cache_valid_ai_decision"),
    )
    op.create_index("ix_ai_match_cache_pair_hash", "ai_match_cache", ["pair_hash"], unique=True)

    op.create_table(
        "ai_usage_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("batch_id", sa.String(), nullable=False),
        sa.Column("event_id_a", sa.String(), nullable=False),
        sa.Column("event_id_b", sa.String(), nullable=False),
        sa.Column("model", sa.String(), nullable=False),
        sa.Column("prompt_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("completion_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("total_tokens", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("estimated_cost_usd", sa.Float(), nullable=False, server_default="0.0"),
        sa.Column("cached", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_ai_usage_log_batch_id", "ai_usage_log", ["batch_id"])


def downgrade() -> None:
    op.drop_index("ix_ai_usage_log_batch_id")
    op.drop_table("ai_usage_log")
    op.drop_index("ix_ai_match_cache_pair_hash")
    op.drop_table("ai_match_cache")
