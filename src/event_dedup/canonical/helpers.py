"""Reusable helpers for canonical event operations."""

from __future__ import annotations

import datetime as dt

from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.source_event import SourceEvent


def source_event_to_dict(evt: SourceEvent) -> dict:
    """Convert a SourceEvent ORM object to a dict for synthesize_canonical().

    Matches the format expected by run_full_pipeline and synthesize_canonical.
    Does NOT include normalized fields or blocking_keys (not needed for synthesis).
    """
    return {
        "id": evt.id,
        "title": evt.title,
        "short_description": evt.short_description,
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


def update_canonical_from_dict(canonical: CanonicalEvent, data: dict) -> None:
    """Apply synthesized canonical dict fields to an ORM CanonicalEvent object.

    Updates all content fields, provenance, and source_count.
    Does NOT modify id, created_at, version, needs_review, or match_confidence.
    """
    canonical.title = data["title"]
    canonical.short_description = data.get("short_description")
    canonical.description = data.get("description")
    canonical.highlights = data.get("highlights")
    canonical.location_name = data.get("location_name")
    canonical.location_city = data.get("location_city")
    canonical.location_district = data.get("location_district")
    canonical.location_street = data.get("location_street")
    canonical.location_zipcode = data.get("location_zipcode")
    canonical.geo_latitude = data.get("geo_latitude")
    canonical.geo_longitude = data.get("geo_longitude")
    canonical.geo_confidence = data.get("geo_confidence")
    canonical.dates = data.get("dates")
    canonical.categories = data.get("categories")
    canonical.is_family_event = data.get("is_family_event")
    canonical.is_child_focused = data.get("is_child_focused")
    canonical.admission_free = data.get("admission_free")
    canonical.field_provenance = data.get("field_provenance")
    canonical.source_count = data.get("source_count", 1)

    # Parse first_date/last_date from string to date objects
    first = data.get("first_date")
    last = data.get("last_date")
    canonical.first_date = dt.date.fromisoformat(first) if first else None
    canonical.last_date = dt.date.fromisoformat(last) if last else None

    canonical.updated_at = dt.datetime.now(dt.UTC)
