"""Pydantic schemas for AI matching structured output."""
from __future__ import annotations

from pydantic import BaseModel, Field


class AIMatchResult(BaseModel):
    """Structured response from Gemini Flash for event pair comparison.

    Used as response_schema in the Gemini API call to constrain output.
    """
    decision: str = Field(
        description=(
            "Whether the two events are the same real-world event. "
            "Must be 'same' or 'different'."
        )
    )
    confidence: float = Field(
        description="Confidence in the decision, from 0.0 (no confidence) to 1.0 (certain).",
        ge=0.0,
        le=1.0,
    )
    reasoning: str = Field(
        description=(
            "Brief explanation of why the events are considered same or different, "
            "noting key matching or differentiating factors."
        )
    )
