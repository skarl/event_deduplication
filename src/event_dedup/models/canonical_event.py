"""Canonical event model -- the deduplicated, merged representation."""

from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from event_dedup.models.base import Base

if TYPE_CHECKING:
    from event_dedup.models.canonical_event_source import CanonicalEventSource


class CanonicalEvent(Base):
    """A deduplicated event merging one or more source events.

    Represents the "best" version of an event after matching and field-level
    merging.  The field_provenance JSON tracks which source contributed each
    field value.
    """

    __tablename__ = "canonical_events"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)

    # Core content fields
    title: Mapped[str] = mapped_column(sa.String)
    short_description: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    highlights: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)

    # Location
    location_name: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_city: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_district: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_street: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_zipcode: Mapped[str | None] = mapped_column(sa.String, nullable=True)

    # Geo
    geo_latitude: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    geo_longitude: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    geo_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    # Dates & categories (JSON for SQLite compatibility)
    dates: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)
    categories: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)

    # Event metadata
    is_family_event: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    is_child_focused: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    admission_free: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)

    # Provenance & quality
    field_provenance: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    source_count: Mapped[int] = mapped_column(sa.Integer, default=1)
    match_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    version: Mapped[int] = mapped_column(sa.Integer, default=1)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))

    # Relationships
    sources: Mapped[list[CanonicalEventSource]] = relationship(
        "CanonicalEventSource", back_populates="canonical_event", cascade="all, delete-orphan"
    )
