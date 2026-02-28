"""Audit log model for tracking manual review operations."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from event_dedup.models.base import Base


class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(sa.String)  # "split", "merge", "review_dismiss"
    canonical_event_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("canonical_events.id", ondelete="SET NULL"), nullable=True
    )
    source_event_id: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    operator: Mapped[str] = mapped_column(sa.String, default="anonymous")
    details: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )
