"""AI matching resolver: orchestrates ambiguous pair resolution.

Filters ambiguous decisions from deterministic scoring, checks the
content-hash cache, calls Gemini Flash for uncached pairs, applies
confidence threshold, and returns an updated MatchResult.
"""
from __future__ import annotations

import asyncio
import uuid

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from event_dedup.ai_matching.cache import compute_pair_hash, lookup_cache, store_cache
from event_dedup.ai_matching.client import call_gemini, create_client
from event_dedup.ai_matching.cost_tracker import estimate_cost, get_batch_summary, log_usage
from event_dedup.ai_matching.schemas import AIMatchResult
from event_dedup.matching.config import AIMatchingConfig
from event_dedup.matching.pipeline import MatchDecisionRecord, MatchResult

logger = structlog.get_logger()


async def resolve_ambiguous_pairs(
    match_result: MatchResult,
    events: list[dict],
    ai_config: AIMatchingConfig,
    session_factory: async_sessionmaker,
) -> MatchResult:
    """Resolve ambiguous match decisions via Gemini Flash AI.

    Filters for decisions where decision=="ambiguous", resolves each
    via cache lookup or API call, and returns an updated MatchResult
    with resolved decisions.

    This function is called from the worker orchestrator AFTER
    deterministic scoring and BEFORE clustering.

    Args:
        match_result: The deterministic scoring result.
        events: All event dicts (needed for prompt formatting).
        ai_config: AI matching configuration.
        session_factory: Async session factory for cache/usage DB access.

    Returns:
        Updated MatchResult with ambiguous pairs resolved (or still
        ambiguous if AI confidence is below threshold or API failed).
    """
    events_by_id = {e["id"]: e for e in events}
    ambiguous = [
        d for d in match_result.decisions
        if d.decision == "ambiguous"
        and ai_config.min_combined_score <= d.combined_score_value <= ai_config.max_combined_score
    ]

    if not ambiguous:
        logger.info("ai_resolver_skip", reason="no_ambiguous_pairs")
        return match_result

    batch_id = str(uuid.uuid4())[:8]
    log = logger.bind(batch_id=batch_id, ambiguous_count=len(ambiguous))
    log.info("ai_resolver_start")

    client = create_client(ai_config.api_key)
    semaphore = asyncio.Semaphore(ai_config.max_concurrent_requests)

    async def resolve_one(decision: MatchDecisionRecord) -> MatchDecisionRecord:
        """Resolve a single ambiguous decision."""
        async with semaphore:
            event_a = events_by_id[decision.event_id_a]
            event_b = events_by_id[decision.event_id_b]

            # Compute cache key
            pair_hash = compute_pair_hash(event_a, event_b)

            # Check cache
            if ai_config.cache_enabled:
                cached = await lookup_cache(
                    session_factory, pair_hash, ai_config.model
                )
                if cached is not None:
                    # Log cache hit
                    await log_usage(
                        session_factory, batch_id,
                        decision.event_id_a, decision.event_id_b,
                        ai_config.model,
                        prompt_tokens=0, completion_tokens=0,
                        estimated_cost_usd=0.0, cached=True,
                    )
                    return _apply_ai_result(
                        decision, cached, ai_config.confidence_threshold
                    )

            # Call Gemini API
            try:
                result, prompt_tokens, completion_tokens = await call_gemini(
                    client, event_a, event_b, decision.signals, ai_config,
                )
            except Exception as e:
                logger.warning(
                    "gemini_call_failed",
                    pair=f"{decision.event_id_a}:{decision.event_id_b}",
                    error=str(e),
                )
                # Log failed attempt (0 tokens, 0 cost)
                await log_usage(
                    session_factory, batch_id,
                    decision.event_id_a, decision.event_id_b,
                    ai_config.model,
                    prompt_tokens=0, completion_tokens=0,
                    estimated_cost_usd=0.0, cached=False,
                )
                return decision  # Keep as ambiguous on failure

            # Calculate cost
            cost = estimate_cost(prompt_tokens, completion_tokens, ai_config)

            # Log API call
            await log_usage(
                session_factory, batch_id,
                decision.event_id_a, decision.event_id_b,
                ai_config.model,
                prompt_tokens=prompt_tokens,
                completion_tokens=completion_tokens,
                estimated_cost_usd=cost,
                cached=False,
            )

            # Store in cache
            if ai_config.cache_enabled:
                id_a, id_b = decision.event_id_a, decision.event_id_b
                await store_cache(
                    session_factory, pair_hash, id_a, id_b,
                    result, ai_config.model,
                )

            return _apply_ai_result(
                decision, result, ai_config.confidence_threshold
            )

    # Resolve all ambiguous pairs concurrently (with semaphore limiting)
    resolved = await asyncio.gather(
        *[resolve_one(d) for d in ambiguous],
        return_exceptions=True,
    )

    # Build updated decisions list
    ambiguous_ids = {
        (d.event_id_a, d.event_id_b) for d in ambiguous
    }
    updated_decisions = [
        d for d in match_result.decisions
        if (d.event_id_a, d.event_id_b) not in ambiguous_ids
    ]

    for original, result in zip(ambiguous, resolved):
        if isinstance(result, Exception):
            logger.error(
                "resolve_one_exception",
                pair=f"{original.event_id_a}:{original.event_id_b}",
                error=str(result),
            )
            updated_decisions.append(original)  # Keep as ambiguous
        else:
            updated_decisions.append(result)

    # Recount
    new_match = sum(1 for d in updated_decisions if d.decision == "match")
    new_ambiguous = sum(1 for d in updated_decisions if d.decision == "ambiguous")
    new_no_match = sum(1 for d in updated_decisions if d.decision == "no_match")

    # Log batch summary
    try:
        summary = await get_batch_summary(session_factory, batch_id)
        log.info(
            "ai_resolver_complete",
            resolved=len(ambiguous) - new_ambiguous,
            remaining_ambiguous=new_ambiguous,
            api_calls=summary["api_requests"],
            cache_hits=summary["cached_requests"],
            total_tokens=summary["total_tokens"],
            estimated_cost_usd=summary["estimated_cost_usd"],
        )
    except Exception:
        log.info("ai_resolver_complete", resolved=len(ambiguous) - new_ambiguous)

    return MatchResult(
        decisions=updated_decisions,
        pair_stats=match_result.pair_stats,
        match_count=new_match,
        ambiguous_count=new_ambiguous,
        no_match_count=new_no_match,
    )


def _apply_ai_result(
    decision: MatchDecisionRecord,
    ai_result: AIMatchResult,
    confidence_threshold: float,
) -> MatchDecisionRecord:
    """Apply an AI result to a match decision.

    Maps AI decision "same" -> "match", "different" -> "no_match".
    Only overrides if AI confidence >= threshold; otherwise keeps
    as "ambiguous" for human review.

    Args:
        decision: Original ambiguous decision.
        ai_result: AI judgment (same/different + confidence).
        confidence_threshold: Minimum confidence to override.

    Returns:
        Updated MatchDecisionRecord (new instance).
    """
    if ai_result.confidence < confidence_threshold:
        # Low confidence -- keep as ambiguous for review queue
        return MatchDecisionRecord(
            event_id_a=decision.event_id_a,
            event_id_b=decision.event_id_b,
            signals=decision.signals,
            combined_score_value=decision.combined_score_value,
            decision="ambiguous",
            tier="ai_low_confidence",
        )

    # Map AI decision to pipeline decision
    if ai_result.decision == "same":
        new_decision = "match"
    elif ai_result.decision == "different":
        new_decision = "no_match"
    else:
        # Unexpected value -- keep as ambiguous
        return MatchDecisionRecord(
            event_id_a=decision.event_id_a,
            event_id_b=decision.event_id_b,
            signals=decision.signals,
            combined_score_value=decision.combined_score_value,
            decision="ambiguous",
            tier="ai_unexpected",
        )

    return MatchDecisionRecord(
        event_id_a=decision.event_id_a,
        event_id_b=decision.event_id_b,
        signals=decision.signals,
        combined_score_value=decision.combined_score_value,
        decision=new_decision,
        tier="ai",
    )
