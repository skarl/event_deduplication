from __future__ import annotations

from datetime import datetime
from typing import TYPE_CHECKING

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column, relationship

from event_dedup.models.base import Base

if TYPE_CHECKING:
    from event_dedup.models.source_event import SourceEvent


class FileIngestion(Base):
    __tablename__ = "file_ingestions"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    filename: Mapped[str] = mapped_column(sa.String)
    file_hash: Mapped[str] = mapped_column(sa.String, unique=True)
    source_code: Mapped[str] = mapped_column(sa.String)
    event_count: Mapped[int] = mapped_column(sa.Integer)
    status: Mapped[str] = mapped_column(sa.String, default="completed")
    error_message: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    ingested_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))
    file_metadata: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    # Relationship
    events: Mapped[list[SourceEvent]] = relationship("SourceEvent", back_populates="file_ingestion")
