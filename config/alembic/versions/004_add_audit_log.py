"""Add audit_log table and dashboard query indexes.

Revision ID: 004_audit_log
Revises: 003_ai_matching
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

revision = "004_audit_log"
down_revision = "003_ai_matching"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column(
            "canonical_event_id",
            sa.Integer(),
            sa.ForeignKey("canonical_events.id", ondelete="SET NULL"),
            nullable=True,
        ),
        sa.Column("source_event_id", sa.String(), nullable=True),
        sa.Column("operator", sa.String(), nullable=False, server_default="anonymous"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
    )
    op.create_index("ix_audit_log_canonical_event_id", "audit_log", ["canonical_event_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # Indexes for dashboard query performance
    op.create_index("ix_file_ingestions_ingested_at", "file_ingestions", ["ingested_at"])
    op.create_index("ix_match_decisions_decided_at", "match_decisions", ["decided_at"])


def downgrade() -> None:
    op.drop_index("ix_match_decisions_decided_at")
    op.drop_index("ix_file_ingestions_ingested_at")
    op.drop_index("ix_audit_log_created_at")
    op.drop_index("ix_audit_log_canonical_event_id")
    op.drop_table("audit_log")
