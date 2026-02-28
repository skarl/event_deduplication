"""Token usage tracking and cost estimation for AI matching.

Logs each API call (or cache hit) to the ai_usage_log table and provides
cost aggregation queries for per-batch and per-period reporting.
"""
from __future__ import annotations

from datetime import datetime

import structlog
import sqlalchemy as sa
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from event_dedup.matching.config import AIMatchingConfig
from event_dedup.models.ai_usage_log import AIUsageLog

logger = structlog.get_logger()


def estimate_cost(
    prompt_tokens: int,
    completion_tokens: int,
    config: AIMatchingConfig,
) -> float:
    """Estimate cost in USD for a single API call.

    Args:
        prompt_tokens: Number of input tokens.
        completion_tokens: Number of output tokens.
        config: AI config with per-1M-token pricing.

    Returns:
        Estimated cost in USD.
    """
    input_cost = (prompt_tokens / 1_000_000) * config.cost_per_1m_input_tokens
    output_cost = (completion_tokens / 1_000_000) * config.cost_per_1m_output_tokens
    return input_cost + output_cost


async def log_usage(
    session_factory: async_sessionmaker,
    batch_id: str,
    event_id_a: str,
    event_id_b: str,
    model: str,
    prompt_tokens: int,
    completion_tokens: int,
    estimated_cost_usd: float,
    cached: bool,
) -> None:
    """Log a single AI matching usage entry.

    Args:
        session_factory: Async session factory.
        batch_id: Identifier grouping requests from one pipeline run.
        event_id_a: First event ID.
        event_id_b: Second event ID.
        model: Model name used.
        prompt_tokens: Input token count (0 for cache hits).
        completion_tokens: Output token count (0 for cache hits).
        estimated_cost_usd: Estimated cost in USD (0.0 for cache hits).
        cached: Whether this was a cache hit.
    """
    async with session_factory() as session, session.begin():
        entry = AIUsageLog(
            batch_id=batch_id,
            event_id_a=event_id_a,
            event_id_b=event_id_b,
            model=model,
            prompt_tokens=prompt_tokens,
            completion_tokens=completion_tokens,
            total_tokens=prompt_tokens + completion_tokens,
            estimated_cost_usd=estimated_cost_usd,
            cached=cached,
        )
        session.add(entry)


async def get_batch_summary(
    session_factory: async_sessionmaker,
    batch_id: str,
) -> dict:
    """Get usage summary for a specific batch.

    Args:
        session_factory: Async session factory.
        batch_id: The batch identifier.

    Returns:
        Dict with total_requests, cached_requests, api_requests,
        total_tokens, estimated_cost_usd.
    """
    async with session_factory() as session:
        stmt = select(
            func.count(AIUsageLog.id).label("total_requests"),
            func.sum(
                func.cast(AIUsageLog.cached, sa.Integer)
            ).label("cached_requests"),
            func.sum(AIUsageLog.total_tokens).label("total_tokens"),
            func.sum(AIUsageLog.prompt_tokens).label("prompt_tokens"),
            func.sum(AIUsageLog.completion_tokens).label("completion_tokens"),
            func.sum(AIUsageLog.estimated_cost_usd).label("estimated_cost_usd"),
        ).where(AIUsageLog.batch_id == batch_id)

        result = await session.execute(stmt)
        row = result.one()

    total = row.total_requests or 0
    cached = row.cached_requests or 0

    return {
        "batch_id": batch_id,
        "total_requests": total,
        "cached_requests": cached,
        "api_requests": total - cached,
        "total_tokens": row.total_tokens or 0,
        "prompt_tokens": row.prompt_tokens or 0,
        "completion_tokens": row.completion_tokens or 0,
        "estimated_cost_usd": round(row.estimated_cost_usd or 0.0, 6),
    }


async def get_period_summary(
    session_factory: async_sessionmaker,
    since: datetime,
) -> dict:
    """Get usage summary for a time period.

    Args:
        session_factory: Async session factory.
        since: Start of the reporting period.

    Returns:
        Dict with batch_count, total_requests, total_tokens, estimated_cost_usd.
    """
    async with session_factory() as session:
        stmt = select(
            func.count(func.distinct(AIUsageLog.batch_id)).label("batch_count"),
            func.count(AIUsageLog.id).label("total_requests"),
            func.sum(
                func.cast(AIUsageLog.cached, sa.Integer)
            ).label("cached_requests"),
            func.sum(AIUsageLog.total_tokens).label("total_tokens"),
            func.sum(AIUsageLog.estimated_cost_usd).label("estimated_cost_usd"),
        ).where(AIUsageLog.created_at >= since)

        result = await session.execute(stmt)
        row = result.one()

    total = row.total_requests or 0
    cached = row.cached_requests or 0

    return {
        "since": since.isoformat(),
        "batch_count": row.batch_count or 0,
        "total_requests": total,
        "cached_requests": cached,
        "api_requests": total - cached,
        "total_tokens": row.total_tokens or 0,
        "estimated_cost_usd": round(row.estimated_cost_usd or 0.0, 6),
    }
