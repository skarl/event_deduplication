"""Match decision model for recording pairwise comparison results."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from event_dedup.models.base import Base


class MatchDecision(Base):
    """Records the outcome of comparing two source events.

    Stores individual signal scores (date, geo, title, description), the
    combined score, and the final decision.  Canonical ordering is enforced
    (source_event_id_a < source_event_id_b) to prevent duplicate comparisons.
    """

    __tablename__ = "match_decisions"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_event_id_a: Mapped[str] = mapped_column(sa.String, sa.ForeignKey("source_events.id"))
    source_event_id_b: Mapped[str] = mapped_column(sa.String, sa.ForeignKey("source_events.id"))

    # Scores
    combined_score: Mapped[float] = mapped_column(sa.Float)
    date_score: Mapped[float] = mapped_column(sa.Float)
    geo_score: Mapped[float] = mapped_column(sa.Float)
    title_score: Mapped[float] = mapped_column(sa.Float)
    description_score: Mapped[float] = mapped_column(sa.Float)

    # Decision
    decision: Mapped[str] = mapped_column(sa.String)
    tier: Mapped[str] = mapped_column(sa.String, default="deterministic")

    # Timestamp
    decided_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        sa.UniqueConstraint("source_event_id_a", "source_event_id_b", name="uq_match_decisions_event_pair"),
        sa.CheckConstraint("source_event_id_a < source_event_id_b", name="canonical_ordering"),
        sa.CheckConstraint("decision IN ('match', 'no_match', 'ambiguous')", name="valid_decision"),
    )
