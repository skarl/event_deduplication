"""Content-hash cache for AI match results.

Computes deterministic hashes from event pair content and manages
cache lookup/storage in the ai_match_cache table.
"""
from __future__ import annotations

import hashlib
import json

import structlog
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from event_dedup.ai_matching.schemas import AIMatchResult
from event_dedup.models.ai_match_cache import AIMatchCache

logger = structlog.get_logger()


def compute_pair_hash(event_a: dict, event_b: dict) -> str:
    """Compute a deterministic SHA-256 hash of an event pair's content.

    Uses canonical ordering (id_a < id_b) and only matching-relevant
    fields so that the same real-world event pair always produces the
    same hash regardless of processing order.

    Args:
        event_a: First event dict.
        event_b: Second event dict.

    Returns:
        64-character hex SHA-256 hash string.
    """
    # Canonical ordering
    if event_a["id"] > event_b["id"]:
        event_a, event_b = event_b, event_a

    def extract_fields(e: dict) -> dict:
        return {
            "title": e.get("title", ""),
            "description": e.get("description", ""),
            "short_description": e.get("short_description", ""),
            "location_city": e.get("location_city", ""),
            "location_name": e.get("location_name", ""),
            "dates": sorted(
                str(d.get("date", "")) for d in (e.get("dates") or [])
            ),
            "categories": sorted(e.get("categories") or []),
        }

    content = json.dumps(
        [extract_fields(event_a), extract_fields(event_b)],
        sort_keys=True,
        ensure_ascii=False,
    )
    return hashlib.sha256(content.encode()).hexdigest()


async def lookup_cache(
    session_factory: async_sessionmaker,
    pair_hash: str,
    current_model: str,
) -> AIMatchResult | None:
    """Look up a cached AI match result by pair hash.

    Returns None on cache miss or if the cached result was generated
    by a different model (stale cache on model upgrade).

    Args:
        session_factory: Async session factory.
        pair_hash: SHA-256 hash of the event pair content.
        current_model: The model ID currently configured (for staleness check).

    Returns:
        AIMatchResult if cache hit with matching model, else None.
    """
    async with session_factory() as session:
        stmt = select(AIMatchCache).where(AIMatchCache.pair_hash == pair_hash)
        result = await session.execute(stmt)
        cached = result.scalar_one_or_none()

    if cached is None:
        return None

    # Check model staleness
    if cached.model != current_model:
        logger.debug(
            "cache_model_stale",
            pair_hash=pair_hash[:12],
            cached_model=cached.model,
            current_model=current_model,
        )
        return None

    return AIMatchResult(
        decision=cached.decision,
        confidence=cached.confidence,
        reasoning=cached.reasoning,
    )


async def store_cache(
    session_factory: async_sessionmaker,
    pair_hash: str,
    event_id_a: str,
    event_id_b: str,
    result: AIMatchResult,
    model: str,
) -> None:
    """Store an AI match result in the cache.

    Uses the pair_hash as the unique key. Silently ignores duplicate
    inserts (race condition between concurrent workers).

    Args:
        session_factory: Async session factory.
        pair_hash: SHA-256 hash of the event pair content.
        event_id_a: First event ID (canonical order).
        event_id_b: Second event ID (canonical order).
        result: The AI match result to cache.
        model: The model ID that produced this result.
    """
    async with session_factory() as session, session.begin():
        entry = AIMatchCache(
            pair_hash=pair_hash,
            event_id_a=event_id_a,
            event_id_b=event_id_b,
            decision=result.decision,
            confidence=result.confidence,
            reasoning=result.reasoning,
            model=model,
        )
        session.add(entry)
        try:
            await session.flush()
        except Exception:
            # Unique constraint violation = concurrent insert, ignore
            await session.rollback()
            logger.debug("cache_store_duplicate", pair_hash=pair_hash[:12])
