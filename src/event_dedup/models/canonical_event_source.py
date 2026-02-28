"""Join table linking canonical events to their source events."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from event_dedup.models.base import Base

if TYPE_CHECKING:
    from event_dedup.models.canonical_event import CanonicalEvent
    from event_dedup.models.source_event import SourceEvent


class CanonicalEventSource(Base):
    """Links a canonical event to one of its contributing source events.

    The unique constraint prevents the same source event from being linked
    to the same canonical event more than once.
    """

    __tablename__ = "canonical_event_sources"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    canonical_event_id: Mapped[int] = mapped_column(
        sa.Integer, sa.ForeignKey("canonical_events.id", ondelete="CASCADE")
    )
    source_event_id: Mapped[str] = mapped_column(sa.String, sa.ForeignKey("source_events.id"))
    added_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))

    # Relationships
    canonical_event: Mapped[CanonicalEvent] = relationship("CanonicalEvent", back_populates="sources")
    source_event: Mapped[SourceEvent] = relationship("SourceEvent")

    __table_args__ = (
        sa.UniqueConstraint("canonical_event_id", "source_event_id", name="uq_canonical_event_sources_pair"),
    )
