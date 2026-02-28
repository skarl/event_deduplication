"""Tests for the export service module."""

import json
from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.export.service import (
    EXPORT_CHUNK_SIZE,
    canonical_to_input_format,
    chunk_events,
    query_and_export,
)
from event_dedup.models.canonical_event import CanonicalEvent


# ---------------------------------------------------------------------------
# canonical_to_input_format
# ---------------------------------------------------------------------------


class TestCanonicalToInputFormat:
    """Tests for transforming CanonicalEvent ORM objects to input JSON format."""

    def test_full_event(self):
        """All fields populated -- output has event_dates, nested location.geo."""
        ce = CanonicalEvent(
            id=1,
            title="Fasching in Freiburg",
            short_description="Fasching celebration",
            description="Annual Fasching celebration in the city center.",
            highlights=["live music", "food stands"],
            location_name="Rathausplatz",
            location_city="Freiburg",
            location_district="Altstadt",
            location_street="Rathausgasse 1",
            location_zipcode="79098",
            geo_latitude=48.0,
            geo_longitude=7.85,
            geo_confidence=0.95,
            dates=[
                {"date": "2026-02-15", "start_time": "14:00", "end_time": "22:00"},
            ],
            categories=["fasching", "karneval"],
            is_family_event=True,
            is_child_focused=False,
            admission_free=True,
        )

        result = canonical_to_input_format(ce)

        assert result["title"] == "Fasching in Freiburg"
        assert result["short_description"] == "Fasching celebration"
        assert result["description"] == "Annual Fasching celebration in the city center."
        assert result["highlights"] == ["live music", "food stands"]

        # Dates renamed to event_dates
        assert "dates" not in result
        assert result["event_dates"] == [
            {"date": "2026-02-15", "start_time": "14:00", "end_time": "22:00"},
        ]

        # Nested location
        loc = result["location"]
        assert loc["name"] == "Rathausplatz"
        assert loc["city"] == "Freiburg"
        assert loc["district"] == "Altstadt"
        assert loc["street"] == "Rathausgasse 1"
        assert loc["zipcode"] == "79098"

        # Nested geo within location
        geo = loc["geo"]
        assert geo["latitude"] == 48.0
        assert geo["longitude"] == 7.85
        assert geo["confidence"] == 0.95

        # Flags
        assert result["categories"] == ["fasching", "karneval"]
        assert result["is_family_event"] is True
        assert result["is_child_focused"] is False
        assert result["admission_free"] is True

        # Source-level fields must be absent
        assert "id" not in result
        assert "source_type" not in result
        assert "registration_required" not in result
        assert "confidence_score" not in result
        assert "_batch_index" not in result
        assert "_extracted_at" not in result

    def test_minimal_event(self):
        """Only title + dates -- no empty location/geo keys in output."""
        ce = CanonicalEvent(
            id=2,
            title="Minimal Event",
            dates=[{"date": "2026-03-01"}],
        )

        result = canonical_to_input_format(ce)

        assert result["title"] == "Minimal Event"
        assert result["event_dates"] == [{"date": "2026-03-01"}]
        # No location key when all location fields are None
        assert "location" not in result
        assert "short_description" not in result
        assert "description" not in result
        assert "highlights" not in result
        assert "categories" not in result

    def test_none_geo_fields(self):
        """Location fields present but geo fields None -- no geo key in location."""
        ce = CanonicalEvent(
            id=3,
            title="No Geo Event",
            location_city="Offenburg",
            location_name="Marktplatz",
            geo_latitude=None,
            geo_longitude=None,
            dates=[{"date": "2026-04-01"}],
        )

        result = canonical_to_input_format(ce)

        assert "location" in result
        assert result["location"]["city"] == "Offenburg"
        assert result["location"]["name"] == "Marktplatz"
        assert "geo" not in result["location"]


# ---------------------------------------------------------------------------
# chunk_events
# ---------------------------------------------------------------------------


class TestChunkEvents:
    """Tests for splitting events into named JSON chunks."""

    def test_single_chunk(self):
        """150 events (< 200) -> 1 chunk."""
        events = [{"title": f"Event {i}"} for i in range(150)]
        chunks = chunk_events(events)

        assert len(chunks) == 1
        filename, content = chunks[0]
        assert filename.startswith("export_")
        assert filename.endswith("_part_1.json")

        parsed = json.loads(content)
        assert len(parsed["events"]) == 150
        assert parsed["metadata"]["eventCount"] == 150
        assert parsed["metadata"]["part"] == 1
        assert parsed["metadata"]["totalParts"] == 1

    def test_three_chunks(self):
        """450 events -> 3 chunks of 200, 200, 50."""
        events = [{"title": f"Event {i}"} for i in range(450)]
        chunks = chunk_events(events)

        assert len(chunks) == 3

        for i, (filename, content) in enumerate(chunks, start=1):
            assert f"_part_{i}.json" in filename
            parsed = json.loads(content)
            assert parsed["metadata"]["part"] == i
            assert parsed["metadata"]["totalParts"] == 3

        # Verify chunk sizes
        p1 = json.loads(chunks[0][1])
        p2 = json.loads(chunks[1][1])
        p3 = json.loads(chunks[2][1])
        assert p1["metadata"]["eventCount"] == 200
        assert p2["metadata"]["eventCount"] == 200
        assert p3["metadata"]["eventCount"] == 50

    def test_zero_events(self):
        """0 events -> 1 chunk with empty events array."""
        chunks = chunk_events([])

        assert len(chunks) == 1
        filename, content = chunks[0]
        assert filename.endswith("_part_1.json")

        parsed = json.loads(content)
        assert parsed["events"] == []
        assert parsed["metadata"]["eventCount"] == 0
        assert parsed["metadata"]["part"] == 1
        assert parsed["metadata"]["totalParts"] == 1

    def test_chunk_metadata_has_exported_at(self):
        """Each chunk has an exportedAt timestamp in metadata."""
        chunks = chunk_events([{"title": "Test"}])
        parsed = json.loads(chunks[0][1])
        assert "exportedAt" in parsed["metadata"]

    def test_filters_passed_to_metadata(self):
        """Filters are included in chunk metadata when provided."""
        chunks = chunk_events(
            [{"title": "Test"}],
            filters={"created_after": "2026-01-01T00:00:00", "modified_after": None},
        )
        parsed = json.loads(chunks[0][1])
        assert parsed["metadata"]["filters"]["created_after"] == "2026-01-01T00:00:00"
        assert parsed["metadata"]["filters"]["modified_after"] is None


# ---------------------------------------------------------------------------
# query_and_export (integration with DB)
# ---------------------------------------------------------------------------


class TestQueryAndExport:
    """Integration tests for querying and exporting canonical events."""

    async def test_no_filters(self, test_session_factory, seeded_db):
        """No filters -- returns all events as transformed dicts."""
        async with test_session_factory() as session:
            events = await query_and_export(session)

        assert len(events) == 2
        titles = {e["title"] for e in events}
        assert "Fasching in Freiburg" in titles
        assert "Stadtfest Offenburg" in titles

        # Verify transformation applied
        for event in events:
            assert "event_dates" in event
            assert "id" not in event  # source-level field excluded

    async def test_created_after_filter(self, test_session_factory, seeded_db):
        """created_after filter returns only events created at or after that timestamp."""
        # Seed an event with a known created_at in the future
        future_ts = datetime(2099, 1, 1, tzinfo=timezone.utc)
        async with test_session_factory() as session:
            async with session.begin():
                ce = CanonicalEvent(
                    title="Future Event",
                    dates=[{"date": "2099-01-01"}],
                    source_count=1,
                    needs_review=False,
                    created_at=future_ts,
                    updated_at=future_ts,
                )
                session.add(ce)

        async with test_session_factory() as session:
            events = await query_and_export(
                session,
                created_after=datetime(2098, 1, 1, tzinfo=timezone.utc),
            )

        assert len(events) == 1
        assert events[0]["title"] == "Future Event"

    async def test_modified_after_filter(self, test_session_factory, seeded_db):
        """modified_after filter returns only events modified at or after that timestamp."""
        future_ts = datetime(2099, 6, 1, tzinfo=timezone.utc)
        async with test_session_factory() as session:
            async with session.begin():
                ce = CanonicalEvent(
                    title="Recently Modified",
                    dates=[{"date": "2099-06-01"}],
                    source_count=1,
                    needs_review=False,
                    created_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                    updated_at=future_ts,
                )
                session.add(ce)

        async with test_session_factory() as session:
            events = await query_and_export(
                session,
                modified_after=datetime(2099, 1, 1, tzinfo=timezone.utc),
            )

        assert len(events) == 1
        assert events[0]["title"] == "Recently Modified"

    async def test_combined_filters(self, test_session_factory, seeded_db):
        """Both filters combined use AND semantics."""
        ts = datetime(2099, 1, 1, tzinfo=timezone.utc)
        async with test_session_factory() as session:
            async with session.begin():
                # Created recently but modified long ago -- should NOT match
                ce1 = CanonicalEvent(
                    title="Created Only",
                    dates=[],
                    source_count=1,
                    needs_review=False,
                    created_at=ts,
                    updated_at=datetime(2020, 1, 1, tzinfo=timezone.utc),
                )
                # Both created and modified recently -- should match
                ce2 = CanonicalEvent(
                    title="Both Recent",
                    dates=[],
                    source_count=1,
                    needs_review=False,
                    created_at=ts,
                    updated_at=ts,
                )
                session.add_all([ce1, ce2])

        async with test_session_factory() as session:
            events = await query_and_export(
                session,
                created_after=datetime(2098, 1, 1, tzinfo=timezone.utc),
                modified_after=datetime(2098, 1, 1, tzinfo=timezone.utc),
            )

        titles = {e["title"] for e in events}
        assert "Both Recent" in titles
        assert "Created Only" not in titles


# ---------------------------------------------------------------------------
# API integration tests
# ---------------------------------------------------------------------------


class TestExportAPI:
    """Integration tests for POST /api/export endpoint."""

    async def test_export_no_filters(self, api_client, seeded_db):
        """POST /api/export with empty body returns 200 JSON with events."""
        resp = await api_client.post("/api/export", json={})

        assert resp.status_code == 200
        assert resp.headers["content-type"].startswith("application/json")
        assert "content-disposition" in resp.headers
        assert ".json" in resp.headers["content-disposition"]

        body = resp.json()
        assert "events" in body
        assert len(body["events"]) == 2
        assert "metadata" in body

    async def test_export_with_created_after(self, api_client, seeded_db):
        """POST /api/export with created_after filter returns filtered results."""
        # Use a very future date so no seeded events match
        resp = await api_client.post(
            "/api/export",
            json={"created_after": "2099-01-01T00:00:00"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["events"] == []
        assert body["metadata"]["eventCount"] == 0

    async def test_export_empty_result(self, api_client, seeded_db):
        """Empty result returns JSON with empty events array, not 404."""
        resp = await api_client.post(
            "/api/export",
            json={"created_after": "2099-12-31T23:59:59"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["events"] == []
        assert body["metadata"]["eventCount"] == 0
        assert body["metadata"]["part"] == 1

    async def test_export_invalid_datetime(self, api_client, seeded_db):
        """Invalid datetime string returns 400."""
        resp = await api_client.post(
            "/api/export",
            json={"created_after": "not-a-datetime"},
        )

        assert resp.status_code == 400
        assert "Invalid datetime" in resp.json()["detail"]

    async def test_export_invalid_modified_after(self, api_client, seeded_db):
        """Invalid modified_after datetime string returns 400."""
        resp = await api_client.post(
            "/api/export",
            json={"modified_after": "garbage"},
        )

        assert resp.status_code == 400
        assert "Invalid datetime" in resp.json()["detail"]

    async def test_export_filters_in_metadata(self, api_client, seeded_db):
        """Filter values are included in the response metadata."""
        resp = await api_client.post(
            "/api/export",
            json={"created_after": "2020-01-01T00:00:00"},
        )

        assert resp.status_code == 200
        body = resp.json()
        assert body["metadata"]["filters"]["created_after"] == "2020-01-01T00:00:00"
        assert body["metadata"]["filters"]["modified_after"] is None

    async def test_export_events_have_correct_format(self, api_client, seeded_db):
        """Exported events have event_dates key, not dates; no source-level fields."""
        resp = await api_client.post("/api/export", json={})
        body = resp.json()

        for event in body["events"]:
            assert "event_dates" in event
            assert "dates" not in event
            assert "id" not in event
            assert "source_type" not in event
