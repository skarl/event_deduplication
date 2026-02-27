from __future__ import annotations

import datetime as dt
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from event_dedup.models.base import Base

if TYPE_CHECKING:
    from event_dedup.models.source_event import SourceEvent


class EventDate(Base):
    __tablename__ = "event_dates"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    event_id: Mapped[str] = mapped_column(sa.ForeignKey("source_events.id", ondelete="CASCADE"))
    date: Mapped[dt.date] = mapped_column(sa.Date)
    start_time: Mapped[dt.time | None] = mapped_column(sa.Time, nullable=True)
    end_time: Mapped[dt.time | None] = mapped_column(sa.Time, nullable=True)
    end_date: Mapped[dt.date | None] = mapped_column(sa.Date, nullable=True)

    # Composite index for efficient date-based lookups
    __table_args__ = (sa.Index("ix_event_dates_event_id_date", "event_id", "date"),)

    # Relationship
    event: Mapped[SourceEvent] = relationship("SourceEvent", back_populates="dates")
