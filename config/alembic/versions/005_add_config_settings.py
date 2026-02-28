"""Add config_settings table for dynamic runtime configuration.

Revision ID: 005_config_settings
Revises: 004_audit_log
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

revision = "005_config_settings"
down_revision = "004_audit_log"
branch_labels = None
depends_on = None


def upgrade() -> None:
    op.create_table(
        "config_settings",
        sa.Column("id", sa.Integer(), primary_key=True),
        sa.Column("config_json", sa.JSON(), server_default="{}", nullable=False),
        sa.Column("encrypted_api_key", sa.Text(), nullable=True),
        sa.Column(
            "updated_at",
            sa.DateTime(),
            server_default=sa.text("CURRENT_TIMESTAMP"),
            nullable=False,
        ),
        sa.Column(
            "updated_by",
            sa.String(100),
            server_default="system",
            nullable=False,
        ),
    )


def downgrade() -> None:
    op.drop_table("config_settings")
