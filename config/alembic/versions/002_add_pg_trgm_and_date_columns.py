"""Add pg_trgm extension, GIN index on canonical_events.title, and first_date/last_date columns.

Revision ID: 002_pg_trgm_dates
Revises: a621d57eaaf3
Create Date: 2026-02-28
"""

from alembic import op
import sqlalchemy as sa

revision = "002_pg_trgm_dates"
down_revision = "a621d57eaaf3"
branch_labels = None
depends_on = None


def upgrade() -> None:
    # pg_trgm for fast title search (PostgreSQL only)
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_canonical_events_title_trgm",
        "canonical_events",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )
    # Denormalized date columns for range filtering
    op.add_column("canonical_events", sa.Column("first_date", sa.Date(), nullable=True))
    op.add_column("canonical_events", sa.Column("last_date", sa.Date(), nullable=True))
    op.create_index("ix_canonical_events_first_date", "canonical_events", ["first_date"])
    op.create_index("ix_canonical_events_last_date", "canonical_events", ["last_date"])


def downgrade() -> None:
    op.drop_index("ix_canonical_events_last_date")
    op.drop_index("ix_canonical_events_first_date")
    op.drop_column("canonical_events", "last_date")
    op.drop_column("canonical_events", "first_date")
    op.drop_index("ix_canonical_events_title_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
