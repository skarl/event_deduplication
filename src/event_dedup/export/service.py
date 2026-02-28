"""Core export logic: query, transform, chunk canonical events to input JSON format."""

from __future__ import annotations

import json
from datetime import datetime, timezone

import sqlalchemy as sa
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.models.canonical_event import CanonicalEvent

EXPORT_CHUNK_SIZE = 200


def canonical_to_input_format(canonical: CanonicalEvent) -> dict:
    """Transform a CanonicalEvent ORM object to input JSON format.

    Maps the flat DB columns to the nested structure expected by the ingestion
    pipeline (``event_dates``, nested ``location.geo``, etc.).  Only includes
    optional fields when they have non-None values.
    """
    event: dict = {
        "title": canonical.title,
    }

    # Optional text fields
    if canonical.short_description:
        event["short_description"] = canonical.short_description
    if canonical.description:
        event["description"] = canonical.description
    if canonical.highlights:
        event["highlights"] = canonical.highlights

    # Dates: rename "dates" -> "event_dates"
    event["event_dates"] = canonical.dates or []

    # Location: reconstruct nested structure from flat fields
    location: dict = {}
    if canonical.location_name:
        location["name"] = canonical.location_name
    if canonical.location_city:
        location["city"] = canonical.location_city
    if canonical.location_district:
        location["district"] = canonical.location_district
    if canonical.location_street:
        location["street"] = canonical.location_street
    if canonical.location_zipcode:
        location["zipcode"] = canonical.location_zipcode

    # Geo: nested within location, only when lat/lng are present
    if canonical.geo_latitude is not None and canonical.geo_longitude is not None:
        geo: dict = {
            "longitude": canonical.geo_longitude,
            "latitude": canonical.geo_latitude,
        }
        if canonical.geo_confidence is not None:
            geo["confidence"] = canonical.geo_confidence
        location["geo"] = geo

    if location:
        event["location"] = location

    # Categories and flags
    if canonical.categories:
        event["categories"] = canonical.categories
    if canonical.is_family_event is not None:
        event["is_family_event"] = canonical.is_family_event
    if canonical.is_child_focused is not None:
        event["is_child_focused"] = canonical.is_child_focused
    if canonical.admission_free is not None:
        event["admission_free"] = canonical.admission_free

    return event


def chunk_events(
    events: list[dict],
    chunk_size: int = EXPORT_CHUNK_SIZE,
    filters: dict | None = None,
) -> list[tuple[str, str]]:
    """Split events into named JSON chunks.

    Returns a list of ``(filename, json_content)`` tuples.  Each chunk is a
    complete JSON document with an ``events`` array and ``metadata`` block.

    When *events* is empty a single file with an empty ``events`` array is
    returned (never an empty list).
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
    exported_at = datetime.now(timezone.utc).isoformat()

    if not events:
        content = json.dumps(
            {
                "events": [],
                "metadata": {
                    "exportedAt": exported_at,
                    "eventCount": 0,
                    "part": 1,
                    "totalParts": 1,
                    "filters": filters,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        return [(f"export_{timestamp}_part_1.json", content)]

    total_parts = (len(events) + chunk_size - 1) // chunk_size
    chunks: list[tuple[str, str]] = []

    for i in range(0, len(events), chunk_size):
        part = i // chunk_size + 1
        chunk = events[i : i + chunk_size]
        filename = f"export_{timestamp}_part_{part}.json"
        content = json.dumps(
            {
                "events": chunk,
                "metadata": {
                    "exportedAt": exported_at,
                    "eventCount": len(chunk),
                    "part": part,
                    "totalParts": total_parts,
                    "filters": filters,
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        chunks.append((filename, content))

    return chunks


async def query_and_export(
    session: AsyncSession,
    created_after: datetime | None = None,
    modified_after: datetime | None = None,
) -> list[dict]:
    """Query canonical events with optional date filters, return as input-format dicts.

    Args:
        session: Async SQLAlchemy session.
        created_after: Only include events created at or after this timestamp.
        modified_after: Only include events modified (updated_at) at or after
            this timestamp.

    Returns:
        List of event dicts in the input JSON format.
    """
    stmt = sa.select(CanonicalEvent)

    if created_after is not None:
        stmt = stmt.where(CanonicalEvent.created_at >= created_after)
    if modified_after is not None:
        stmt = stmt.where(CanonicalEvent.updated_at >= modified_after)

    stmt = stmt.order_by(CanonicalEvent.id)
    result = await session.execute(stmt)
    rows = list(result.scalars().all())

    return [canonical_to_input_format(row) for row in rows]
