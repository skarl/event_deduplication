from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from event_dedup.models.base import Base

if TYPE_CHECKING:
    from event_dedup.models.event_date import EventDate
    from event_dedup.models.file_ingestion import FileIngestion


class SourceEvent(Base):
    __tablename__ = "source_events"

    # Primary key: natural key from JSON (pdf-{hash}-{batch}-{index})
    id: Mapped[str] = mapped_column(sa.String, primary_key=True)

    # Foreign key to file_ingestions
    file_ingestion_id: Mapped[int] = mapped_column(sa.ForeignKey("file_ingestions.id"))

    # Original fields (for display)
    title: Mapped[str] = mapped_column(sa.String)
    short_description: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    highlights: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)
    location_name: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_city: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_district: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_street: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_street_no: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_zipcode: Mapped[str | None] = mapped_column(sa.String, nullable=True)

    # Normalized fields (for matching -- populated in Plan 01-02)
    title_normalized: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    short_description_normalized: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_name_normalized: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_city_normalized: Mapped[str | None] = mapped_column(sa.String, nullable=True)

    # Blocking keys (populated in Plan 01-02) -- JSON for SQLite compatibility
    blocking_keys: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)

    # Geo fields
    geo_latitude: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    geo_longitude: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    geo_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    geo_country: Mapped[str | None] = mapped_column(sa.String, nullable=True)

    # Event metadata
    source_type: Mapped[str] = mapped_column(sa.String)
    source_code: Mapped[str] = mapped_column(sa.String)
    categories: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)
    is_family_event: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    is_child_focused: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    admission_free: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    registration_required: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    registration_contact: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    confidence_score: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    # Extraction metadata
    batch_index: Mapped[int | None] = mapped_column(sa.Integer, nullable=True)
    extracted_at: Mapped[str | None] = mapped_column(sa.String, nullable=True)

    # Timestamps
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))

    # Relationships
    dates: Mapped[list[EventDate]] = relationship("EventDate", back_populates="event", cascade="all, delete-orphan")
    file_ingestion: Mapped[FileIngestion] = relationship("FileIngestion", back_populates="events")
