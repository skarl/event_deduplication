"""SQLAlchemy model for tracking AI API usage and costs."""
from __future__ import annotations

from datetime import datetime

import sqlalchemy as sa
from sqlalchemy.orm import Mapped, mapped_column

from event_dedup.models.base import Base


class AIUsageLog(Base):
    """Logs each AI API call with token counts and estimated cost.

    Entries with cached=True record cache hits (zero API cost, zero tokens).
    Entries with cached=False record actual API calls.
    batch_id groups all requests from a single pipeline run.
    """

    __tablename__ = "ai_usage_log"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    batch_id: Mapped[str] = mapped_column(sa.String, index=True)
    event_id_a: Mapped[str] = mapped_column(sa.String)
    event_id_b: Mapped[str] = mapped_column(sa.String)
    model: Mapped[str] = mapped_column(sa.String)
    prompt_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    completion_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    total_tokens: Mapped[int] = mapped_column(sa.Integer, default=0)
    estimated_cost_usd: Mapped[float] = mapped_column(sa.Float, default=0.0)
    cached: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )
