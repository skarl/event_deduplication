"""SQLAlchemy model for caching AI match decisions."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from event_dedup.models.base import Base


class AIMatchCache(Base):
    """Cached AI match result keyed by content hash of the event pair.

    The pair_hash is a SHA-256 of the matching-relevant fields of both events
    in canonical order (id_a < id_b). This ensures identical event pairs always
    produce the same cache key regardless of processing order.
    """

    __tablename__ = "ai_match_cache"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    pair_hash: Mapped[str] = mapped_column(sa.String(64), unique=True, index=True)
    event_id_a: Mapped[str] = mapped_column(sa.String)
    event_id_b: Mapped[str] = mapped_column(sa.String)
    decision: Mapped[str] = mapped_column(sa.String)  # "same" or "different"
    confidence: Mapped[float] = mapped_column(sa.Float)
    reasoning: Mapped[str] = mapped_column(sa.Text)
    model: Mapped[str] = mapped_column(sa.String)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        sa.CheckConstraint(
            "decision IN ('same', 'different')", name="valid_ai_decision"
        ),
    )
