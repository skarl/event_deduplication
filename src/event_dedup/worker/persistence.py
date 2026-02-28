"""Canonical event and match decision persistence.

Provides two core functions:
- ``load_all_events_as_dicts``: Load all source events as pipeline-compatible dicts.
- ``replace_canonical_events``: Clear-and-replace canonical events, source links,
  and match decisions in a single transaction.
"""

from __future__ import annotations

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from event_dedup.matching.pipeline import PipelineResult
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.canonical_event_source import CanonicalEventSource
from event_dedup.models.match_decision import MatchDecision
from event_dedup.models.source_event import SourceEvent


async def load_all_events_as_dicts(session: AsyncSession) -> list[dict]:
    """Load all source events with eager-loaded dates as pipeline dicts.

    Returns a list of dicts matching the format expected by
    ``run_full_pipeline``.
    """
    result = await session.execute(
        select(SourceEvent).options(selectinload(SourceEvent.dates))
    )
    source_events = result.scalars().all()

    return [
        {
            "id": evt.id,
            "title": evt.title,
            "title_normalized": evt.title_normalized,
            "short_description": evt.short_description,
            "short_description_normalized": evt.short_description_normalized,
            "description": evt.description,
            "highlights": evt.highlights,
            "location_name": evt.location_name,
            "location_city": evt.location_city,
            "location_district": evt.location_district,
            "location_street": evt.location_street,
            "location_zipcode": evt.location_zipcode,
            "geo_latitude": evt.geo_latitude,
            "geo_longitude": evt.geo_longitude,
            "geo_confidence": evt.geo_confidence,
            "source_code": evt.source_code,
            "source_type": evt.source_type,
            "blocking_keys": evt.blocking_keys,
            "categories": evt.categories,
            "is_family_event": evt.is_family_event,
            "is_child_focused": evt.is_child_focused,
            "admission_free": evt.admission_free,
            "dates": [
                {
                    "date": str(d.date),
                    "start_time": str(d.start_time) if d.start_time else None,
                    "end_time": str(d.end_time) if d.end_time else None,
                    "end_date": str(d.end_date) if d.end_date else None,
                }
                for d in evt.dates
            ],
        }
        for evt in source_events
    ]


async def replace_canonical_events(
    session: AsyncSession, pipeline_result: PipelineResult
) -> int:
    """Clear all canonical events/match decisions and replace with new data.

    Must be called within an active ``session.begin()`` context.

    Args:
        session: Active async session (within a transaction).
        pipeline_result: The complete pipeline result.

    Returns:
        Number of canonical events written.
    """
    # Step 1: Delete all existing match decisions
    await session.execute(delete(MatchDecision))

    # Step 2: Delete source links first, then canonical events.
    # Explicit delete of CanonicalEventSource avoids reliance on
    # ON DELETE CASCADE (not enforced in SQLite without PRAGMA foreign_keys).
    await session.execute(delete(CanonicalEventSource))
    await session.execute(delete(CanonicalEvent))

    # Step 3: Build parallel cluster list
    all_clusters = list(pipeline_result.cluster_result.clusters) + list(
        pipeline_result.cluster_result.flagged_clusters
    )

    # Step 4: Create canonical events with source links
    for canonical_dict, cluster in zip(
        pipeline_result.canonical_events, all_clusters
    ):
        canonical = CanonicalEvent(
            title=canonical_dict["title"],
            short_description=canonical_dict.get("short_description"),
            description=canonical_dict.get("description"),
            highlights=canonical_dict.get("highlights"),
            location_name=canonical_dict.get("location_name"),
            location_city=canonical_dict.get("location_city"),
            location_district=canonical_dict.get("location_district"),
            location_street=canonical_dict.get("location_street"),
            location_zipcode=canonical_dict.get("location_zipcode"),
            geo_latitude=canonical_dict.get("geo_latitude"),
            geo_longitude=canonical_dict.get("geo_longitude"),
            geo_confidence=canonical_dict.get("geo_confidence"),
            dates=canonical_dict.get("dates"),
            categories=canonical_dict.get("categories"),
            is_family_event=canonical_dict.get("is_family_event"),
            is_child_focused=canonical_dict.get("is_child_focused"),
            admission_free=canonical_dict.get("admission_free"),
            field_provenance=canonical_dict.get("field_provenance"),
            source_count=canonical_dict.get("source_count", 1),
            match_confidence=canonical_dict.get("match_confidence"),
            needs_review=canonical_dict.get("needs_review", False),
        )
        session.add(canonical)
        await session.flush()  # Get auto-generated ID

        # Create source links from cluster membership (not field_provenance)
        for source_event_id in cluster:
            link = CanonicalEventSource(
                canonical_event_id=canonical.id,
                source_event_id=source_event_id,
            )
            session.add(link)

    # Step 5: Persist match decisions
    for decision in pipeline_result.match_result.decisions:
        match_decision = MatchDecision(
            source_event_id_a=decision.event_id_a,
            source_event_id_b=decision.event_id_b,
            combined_score=decision.combined_score_value,
            date_score=decision.signals.date,
            geo_score=decision.signals.geo,
            title_score=decision.signals.title,
            description_score=decision.signals.description,
            decision=decision.decision,
            tier=decision.tier,
        )
        session.add(match_decision)

    return len(pipeline_result.canonical_events)
