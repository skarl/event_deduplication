"""SQLAlchemy model for runtime configuration storage."""

from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from event_dedup.models.base import Base


class ConfigSettings(Base):
    """Singleton row holding the full matching configuration as JSON.

    Only one row (``id=1``) is ever created.  The ``config_json`` column
    stores all matching parameters; ``encrypted_api_key`` stores the
    Fernet-encrypted Gemini API key separately so it is never part of
    the JSON blob returned to the frontend.
    """

    __tablename__ = "config_settings"

    id: Mapped[int] = mapped_column(primary_key=True, default=1)
    config_json: Mapped[dict] = mapped_column(
        sa.JSON, server_default="{}", default=dict
    )
    encrypted_api_key: Mapped[str | None] = mapped_column(
        sa.Text, nullable=True
    )
    updated_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )
    updated_by: Mapped[str] = mapped_column(
        sa.String(100), server_default="system"
    )
