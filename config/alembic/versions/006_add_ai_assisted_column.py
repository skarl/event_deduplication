"""Add ai_assisted column to canonical_events.

Revision ID: 006_ai_assisted
Revises: 005_config_settings
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

revision = "006_ai_assisted"
down_revision = "005_config_settings"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.add_column(
        "canonical_events",
        sa.Column("ai_assisted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )


def downgrade() -> None:
    op.drop_column("canonical_events", "ai_assisted")
