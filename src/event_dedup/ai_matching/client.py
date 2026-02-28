"""Gemini API client wrapper for AI matching.

Provides async API call with structured output, using the google-genai
SDK. The SDK handles retries (up to 4 with exponential backoff) and
rate limit (429) responses automatically.
"""
from __future__ import annotations

import structlog
from google import genai
from google.genai import types

from event_dedup.ai_matching.prompt import SYSTEM_PROMPT, format_event_pair
from event_dedup.ai_matching.schemas import AIMatchResult
from event_dedup.matching.combiner import SignalScores
from event_dedup.matching.config import AIMatchingConfig

logger = structlog.get_logger()


def create_client(api_key: str) -> genai.Client:
    """Create a Gemini API client.

    Args:
        api_key: Google AI Studio API key.

    Returns:
        Configured genai.Client instance.
    """
    return genai.Client(api_key=api_key)


async def call_gemini(
    client: genai.Client,
    event_a: dict,
    event_b: dict,
    signals: SignalScores,
    ai_config: AIMatchingConfig,
) -> tuple[AIMatchResult, int, int]:
    """Call Gemini Flash for a single event pair comparison.

    Args:
        client: Gemini API client.
        event_a: First event dict.
        event_b: Second event dict.
        signals: Pre-computed signal scores.
        ai_config: AI matching configuration.

    Returns:
        Tuple of (AIMatchResult, prompt_tokens, completion_tokens).

    Raises:
        Exception: On API error (caller should handle gracefully).
    """
    prompt = format_event_pair(event_a, event_b, signals)

    response = await client.aio.models.generate_content(
        model=ai_config.model,
        contents=prompt,
        config=types.GenerateContentConfig(
            system_instruction=SYSTEM_PROMPT,
            response_mime_type="application/json",
            response_schema=AIMatchResult,
            temperature=ai_config.temperature,
            max_output_tokens=ai_config.max_output_tokens,
        ),
    )

    result = AIMatchResult.model_validate_json(response.text)

    # Extract token usage from response metadata
    usage = response.usage_metadata
    prompt_tokens = getattr(usage, "prompt_token_count", 0) or 0
    completion_tokens = getattr(usage, "candidates_token_count", 0) or 0

    logger.debug(
        "gemini_call_complete",
        decision=result.decision,
        confidence=result.confidence,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
    )

    return result, prompt_tokens, completion_tokens
