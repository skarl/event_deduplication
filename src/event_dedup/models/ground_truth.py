"""Ground truth pair model for labeled event pairs."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from event_dedup.models.base import Base


class GroundTruthPair(Base):
    """A labeled pair of events used for evaluation.

    Each record represents a human-labeled judgment about whether two
    source events refer to the same real-world event ("same") or not
    ("different").

    Canonical ordering is enforced: event_id_a < event_id_b to prevent
    duplicate labels for the same pair.
    """

    __tablename__ = "ground_truth_pairs"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    event_id_a: Mapped[str] = mapped_column(sa.String, sa.ForeignKey("source_events.id"))
    event_id_b: Mapped[str] = mapped_column(sa.String, sa.ForeignKey("source_events.id"))
    label: Mapped[str] = mapped_column(sa.String)
    notes: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    title_similarity: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    labeled_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))

    __table_args__ = (
        sa.UniqueConstraint("event_id_a", "event_id_b", name="uq_ground_truth_pairs_event_pair"),
        sa.CheckConstraint("event_id_a < event_id_b", name="canonical_ordering"),
        sa.CheckConstraint("label IN ('same', 'different')", name="valid_label"),
    )
