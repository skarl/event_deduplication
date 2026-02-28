"""Tests for the review operations and dashboard API endpoints."""

import datetime as dt

import pytest
from sqlalchemy import select

from event_dedup.models.audit_log import AuditLog
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.canonical_event_source import CanonicalEventSource
from event_dedup.models.event_date import EventDate
from event_dedup.models.file_ingestion import FileIngestion
from event_dedup.models.match_decision import MatchDecision
from event_dedup.models.source_event import SourceEvent


@pytest.fixture
async def review_seeded_db(test_session_factory):
    """Seed the test DB with data for review operations testing.

    Creates:
    - FileIngestion (completed, with 3 source events)
    - Source event pdf-aaa-0-0 (Fasching in Freiburg)
    - Source event pdf-bbb-0-0 (Karneval in Freiburg)
    - Source event pdf-ccc-0-0 (Weihnachtsmarkt Freiburg)
    - Canonical 1: Fasching in Freiburg (2 sources: aaa, bbb), confidence=0.85
    - Canonical 2: Stadtfest Offenburg (singleton, no source event -- just a canonical)
    - Canonical 3: Weihnachtsmarkt (1 source: ccc), needs_review=True, confidence=0.45
    - Match decision for aaa <-> bbb
    """
    async with test_session_factory() as session:
        async with session.begin():
            # File ingestion
            fi = FileIngestion(
                filename="test.json",
                file_hash="review_test_hash",
                source_code="bwb",
                event_count=4,
                status="completed",
            )
            session.add(fi)
            await session.flush()

            # Source events
            se1 = SourceEvent(
                id="pdf-aaa-0-0",
                file_ingestion_id=fi.id,
                title="Fasching in Freiburg",
                source_type="artikel",
                source_code="bwb",
                location_city="Freiburg",
                categories=["fasching"],
                geo_latitude=48.0,
                geo_longitude=7.8,
                geo_confidence=0.9,
            )
            se2 = SourceEvent(
                id="pdf-bbb-0-0",
                file_ingestion_id=fi.id,
                title="Karneval in Freiburg",
                source_type="terminliste",
                source_code="rek",
                location_city="Freiburg",
                categories=["karneval"],
                geo_latitude=48.0,
                geo_longitude=7.8,
                geo_confidence=0.8,
            )
            se3 = SourceEvent(
                id="pdf-ccc-0-0",
                file_ingestion_id=fi.id,
                title="Weihnachtsmarkt Freiburg",
                source_type="artikel",
                source_code="bwb",
                location_city="Freiburg",
                categories=["weihnachten"],
                geo_latitude=48.0,
                geo_longitude=7.85,
                geo_confidence=0.95,
            )
            se4 = SourceEvent(
                id="pdf-ddd-0-0",
                file_ingestion_id=fi.id,
                title="Stadtfest Offenburg",
                source_type="terminliste",
                source_code="rek",
                location_city="Offenburg",
                categories=["stadtfest"],
            )
            session.add_all([se1, se2, se3, se4])

            # Event dates
            ed1 = EventDate(
                event_id="pdf-aaa-0-0",
                date=dt.date(2026, 2, 15),
                start_time=dt.time(14, 0),
            )
            ed2 = EventDate(
                event_id="pdf-bbb-0-0",
                date=dt.date(2026, 2, 15),
                start_time=dt.time(14, 30),
            )
            ed3 = EventDate(
                event_id="pdf-ccc-0-0",
                date=dt.date(2026, 12, 1),
                start_time=dt.time(16, 0),
            )
            ed4 = EventDate(
                event_id="pdf-ddd-0-0",
                date=dt.date(2026, 6, 20),
                start_time=dt.time(10, 0),
            )
            session.add_all([ed1, ed2, ed3, ed4])

            # Canonical event 1: merged event with 2 sources
            ce1 = CanonicalEvent(
                title="Fasching in Freiburg",
                short_description="Fasching celebration",
                description="Annual Fasching celebration in the city center.",
                location_city="Freiburg",
                dates=[{"date": "2026-02-15", "start_time": "14:00"}],
                categories=["fasching", "karneval"],
                source_count=2,
                match_confidence=0.85,
                needs_review=False,
                first_date=dt.date(2026, 2, 15),
                last_date=dt.date(2026, 2, 15),
                field_provenance={"title": "pdf-aaa-0-0"},
            )
            session.add(ce1)
            await session.flush()

            # Links for canonical 1
            link1 = CanonicalEventSource(
                canonical_event_id=ce1.id, source_event_id="pdf-aaa-0-0"
            )
            link2 = CanonicalEventSource(
                canonical_event_id=ce1.id, source_event_id="pdf-bbb-0-0"
            )
            session.add_all([link1, link2])

            # Canonical event 2: singleton with source event
            ce2 = CanonicalEvent(
                title="Stadtfest Offenburg",
                location_city="Offenburg",
                dates=[{"date": "2026-06-20"}],
                categories=["stadtfest"],
                source_count=1,
                needs_review=False,
                first_date=dt.date(2026, 6, 20),
                last_date=dt.date(2026, 6, 20),
            )
            session.add(ce2)
            await session.flush()

            link_stadtfest = CanonicalEventSource(
                canonical_event_id=ce2.id, source_event_id="pdf-ddd-0-0"
            )
            session.add(link_stadtfest)

            # Canonical event 3: needs review, low confidence
            ce3 = CanonicalEvent(
                title="Weihnachtsmarkt Freiburg",
                location_city="Freiburg",
                dates=[{"date": "2026-12-01", "start_time": "16:00"}],
                categories=["weihnachten"],
                source_count=1,
                match_confidence=0.45,
                needs_review=True,
                first_date=dt.date(2026, 12, 1),
                last_date=dt.date(2026, 12, 1),
            )
            session.add(ce3)
            await session.flush()

            # Link for canonical 3
            link3 = CanonicalEventSource(
                canonical_event_id=ce3.id, source_event_id="pdf-ccc-0-0"
            )
            session.add(link3)

            # Match decision (canonical ordering: aaa < bbb)
            md = MatchDecision(
                source_event_id_a="pdf-aaa-0-0",
                source_event_id_b="pdf-bbb-0-0",
                combined_score=0.85,
                date_score=0.95,
                geo_score=1.0,
                title_score=0.72,
                description_score=0.60,
                decision="match",
                tier="deterministic",
            )
            session.add(md)


# --- Split tests ---


@pytest.mark.asyncio
async def test_split_creates_new_canonical(api_client, review_seeded_db):
    """POST split with target_canonical_id=None creates a new canonical."""
    # Get canonical 1 ID (Fasching)
    list_resp = await api_client.get("/api/canonical-events?q=Fasching")
    ce_id = list_resp.json()["items"][0]["id"]

    resp = await api_client.post(
        "/api/review/split",
        json={
            "canonical_event_id": ce_id,
            "source_event_id": "pdf-bbb-0-0",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_canonical_id"] == ce_id
    assert data["new_canonical_id"] is not None
    assert data["original_deleted"] is False

    # Original canonical still exists with 1 source
    detail_resp = await api_client.get(f"/api/canonical-events/{ce_id}")
    assert detail_resp.status_code == 200
    detail = detail_resp.json()
    assert detail["source_count"] == 1

    # New canonical exists
    new_resp = await api_client.get(f"/api/canonical-events/{data['new_canonical_id']}")
    assert new_resp.status_code == 200
    assert new_resp.json()["source_count"] == 1


@pytest.mark.asyncio
async def test_split_to_existing_canonical(api_client, review_seeded_db):
    """POST split with target_canonical_id assigns source to existing canonical."""
    # Get canonical 1 (Fasching) and canonical 2 (Stadtfest)
    list_resp = await api_client.get("/api/canonical-events")
    items = list_resp.json()["items"]
    fasching_id = next(i["id"] for i in items if "Fasching" in i["title"])
    stadtfest_id = next(i["id"] for i in items if "Stadtfest" in i["title"])

    resp = await api_client.post(
        "/api/review/split",
        json={
            "canonical_event_id": fasching_id,
            "source_event_id": "pdf-bbb-0-0",
            "target_canonical_id": stadtfest_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["target_canonical_id"] == stadtfest_id
    assert data["new_canonical_id"] is None

    # Target canonical now has 2 sources (was 1 singleton + the moved one)
    target_detail = await api_client.get(f"/api/canonical-events/{stadtfest_id}")
    assert target_detail.status_code == 200
    assert target_detail.json()["source_count"] == 2


@pytest.mark.asyncio
async def test_split_last_source_deletes_canonical(api_client, review_seeded_db):
    """Splitting the only source from a singleton canonical deletes it."""
    # Get canonical 3 (Weihnachtsmarkt -- singleton with 1 source ccc)
    list_resp = await api_client.get("/api/canonical-events?q=Weihnachtsmarkt")
    ce_id = list_resp.json()["items"][0]["id"]

    # Count canonicals before
    all_before = await api_client.get("/api/canonical-events")
    total_before = all_before.json()["total"]

    resp = await api_client.post(
        "/api/review/split",
        json={
            "canonical_event_id": ce_id,
            "source_event_id": "pdf-ccc-0-0",
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["original_deleted"] is True
    assert data["new_canonical_id"] is not None

    # Total count should stay the same (one deleted, one created)
    all_after = await api_client.get("/api/canonical-events")
    total_after = all_after.json()["total"]
    assert total_after == total_before

    # The new canonical exists and has the source event's data
    new_resp = await api_client.get(f"/api/canonical-events/{data['new_canonical_id']}")
    assert new_resp.status_code == 200
    assert new_resp.json()["source_count"] == 1


@pytest.mark.asyncio
async def test_split_not_found(api_client, review_seeded_db):
    """POST split with invalid canonical/source returns 404."""
    resp = await api_client.post(
        "/api/review/split",
        json={
            "canonical_event_id": 9999,
            "source_event_id": "pdf-nonexistent",
        },
    )
    assert resp.status_code == 404


# --- Merge tests ---


@pytest.mark.asyncio
async def test_merge_canonical_events(api_client, review_seeded_db):
    """POST merge combines two canonicals, deleting the donor."""
    list_resp = await api_client.get("/api/canonical-events")
    items = list_resp.json()["items"]
    fasching_id = next(i["id"] for i in items if "Fasching" in i["title"])
    weihnachtsmarkt_id = next(i["id"] for i in items if "Weihnachtsmarkt" in i["title"])

    resp = await api_client.post(
        "/api/review/merge",
        json={
            "source_canonical_id": weihnachtsmarkt_id,
            "target_canonical_id": fasching_id,
        },
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["surviving_canonical_id"] == fasching_id
    assert data["deleted_canonical_id"] == weihnachtsmarkt_id
    assert data["new_source_count"] == 3  # 2 + 1

    # Donor should be deleted
    donor_resp = await api_client.get(f"/api/canonical-events/{weihnachtsmarkt_id}")
    assert donor_resp.status_code == 404

    # Target should have all sources
    target_resp = await api_client.get(f"/api/canonical-events/{fasching_id}")
    assert target_resp.status_code == 200
    assert target_resp.json()["source_count"] == 3


@pytest.mark.asyncio
async def test_merge_same_id_returns_400(api_client, review_seeded_db):
    """POST merge with same source and target returns 400."""
    list_resp = await api_client.get("/api/canonical-events?q=Fasching")
    ce_id = list_resp.json()["items"][0]["id"]

    resp = await api_client.post(
        "/api/review/merge",
        json={
            "source_canonical_id": ce_id,
            "target_canonical_id": ce_id,
        },
    )
    assert resp.status_code == 400


# --- Review queue tests ---


@pytest.mark.asyncio
async def test_review_queue_returns_low_confidence(api_client, review_seeded_db):
    """GET /api/review/queue returns needs_review and low-confidence events."""
    resp = await api_client.get("/api/review/queue")
    assert resp.status_code == 200
    data = resp.json()
    # Should have at least the needs_review event
    assert data["total"] >= 1
    # First item should be the needs_review event (sorted by needs_review desc, then confidence asc)
    items = data["items"]
    assert len(items) >= 1
    assert items[0]["needs_review"] is True


@pytest.mark.asyncio
async def test_review_queue_pagination(api_client, review_seeded_db):
    """GET /api/review/queue supports pagination."""
    resp = await api_client.get("/api/review/queue?page=1&size=1")
    assert resp.status_code == 200
    data = resp.json()
    assert data["size"] == 1
    assert data["page"] == 1
    assert len(data["items"]) <= 1


# --- Dismiss test ---


@pytest.mark.asyncio
async def test_dismiss_from_queue(api_client, review_seeded_db, test_session_factory):
    """POST dismiss clears needs_review and logs audit entry."""
    # Find the needs_review event
    list_resp = await api_client.get("/api/canonical-events?q=Weihnachtsmarkt")
    ce_id = list_resp.json()["items"][0]["id"]

    resp = await api_client.post(
        f"/api/review/queue/{ce_id}/dismiss",
        json={"operator": "tester", "reason": "Looks correct"},
    )
    assert resp.status_code == 200
    assert resp.json() == {"status": "dismissed"}

    # Verify needs_review is now False
    detail_resp = await api_client.get(f"/api/canonical-events/{ce_id}")
    assert detail_resp.json()["needs_review"] is False

    # Verify audit log entry was created
    audit_resp = await api_client.get(f"/api/audit-log?action_type=review_dismiss")
    audit_data = audit_resp.json()
    assert audit_data["total"] >= 1
    entry = audit_data["items"][0]
    assert entry["action_type"] == "review_dismiss"
    assert entry["canonical_event_id"] == ce_id
    assert entry["operator"] == "tester"


# --- Audit log tests ---


@pytest.mark.asyncio
async def test_audit_log_records_operations(api_client, review_seeded_db):
    """After a split, GET /api/audit-log returns the entry."""
    # Perform a split first
    list_resp = await api_client.get("/api/canonical-events?q=Fasching")
    ce_id = list_resp.json()["items"][0]["id"]

    await api_client.post(
        "/api/review/split",
        json={
            "canonical_event_id": ce_id,
            "source_event_id": "pdf-bbb-0-0",
        },
    )

    # Check audit log
    audit_resp = await api_client.get("/api/audit-log")
    assert audit_resp.status_code == 200
    data = audit_resp.json()
    assert data["total"] >= 1
    assert any(e["action_type"] == "split" for e in data["items"])


@pytest.mark.asyncio
async def test_audit_log_filter_by_action_type(api_client, review_seeded_db):
    """GET /api/audit-log?action_type=split returns only split entries."""
    # Perform a split and a dismiss
    list_resp = await api_client.get("/api/canonical-events?q=Fasching")
    fasching_id = list_resp.json()["items"][0]["id"]

    await api_client.post(
        "/api/review/split",
        json={
            "canonical_event_id": fasching_id,
            "source_event_id": "pdf-bbb-0-0",
        },
    )

    weihnacht_resp = await api_client.get("/api/canonical-events?q=Weihnachtsmarkt")
    weihnacht_id = weihnacht_resp.json()["items"][0]["id"]
    await api_client.post(
        f"/api/review/queue/{weihnacht_id}/dismiss",
        json={"operator": "tester"},
    )

    # Filter by split only
    audit_resp = await api_client.get("/api/audit-log?action_type=split")
    data = audit_resp.json()
    assert data["total"] >= 1
    assert all(e["action_type"] == "split" for e in data["items"])


# --- Dashboard tests ---


@pytest.mark.asyncio
async def test_dashboard_stats(api_client, review_seeded_db):
    """GET /api/dashboard/stats returns valid structure."""
    resp = await api_client.get("/api/dashboard/stats")
    assert resp.status_code == 200
    data = resp.json()

    # File stats
    assert "files" in data
    assert data["files"]["total_files"] >= 1
    assert data["files"]["total_events"] >= 3

    # Match distribution
    assert "matches" in data
    assert "match" in data["matches"]
    assert "no_match" in data["matches"]
    assert "ambiguous" in data["matches"]

    # Canonical stats
    assert "canonicals" in data
    assert data["canonicals"]["total"] >= 3
    assert data["canonicals"]["needs_review"] >= 1


@pytest.mark.asyncio
async def test_dashboard_processing_history(api_client, review_seeded_db):
    """GET /api/dashboard/processing-history returns daily time-series."""
    resp = await api_client.get("/api/dashboard/processing-history")
    assert resp.status_code == 200
    data = resp.json()

    # Should have at least one entry (from the seeded file ingestion)
    assert len(data) >= 1
    entry = data[0]
    assert "date" in entry
    assert "files_processed" in entry
    assert "events_ingested" in entry
    assert "errors" in entry
    assert entry["files_processed"] >= 1
