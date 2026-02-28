"""Tests for canonical event and match decision persistence."""

import datetime as dt

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from event_dedup.clustering.graph_cluster import ClusterResult
from event_dedup.matching.combiner import SignalScores
from event_dedup.matching.pipeline import (
    MatchDecisionRecord,
    MatchResult,
    PipelineResult,
)
from event_dedup.matching.candidate_pairs import CandidatePairStats
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.canonical_event_source import CanonicalEventSource
from event_dedup.models.event_date import EventDate
from event_dedup.models.file_ingestion import FileIngestion
from event_dedup.models.match_decision import MatchDecision
from event_dedup.models.source_event import SourceEvent
from event_dedup.worker.persistence import (
    load_all_events_as_dicts,
    replace_canonical_events,
)


def _make_file_ingestion(id: int = 1) -> FileIngestion:
    """Helper: create a FileIngestion record."""
    return FileIngestion(
        id=id,
        filename="test.json",
        file_hash=f"hash{id}",
        source_code="test",
        event_count=2,
        status="completed",
    )


def _make_source_event(
    event_id: str,
    file_ingestion_id: int = 1,
    title: str = "Test Event",
    city: str = "TestCity",
    dates: list[dict] | None = None,
) -> SourceEvent:
    """Helper: create a SourceEvent with minimal fields."""
    return SourceEvent(
        id=event_id,
        file_ingestion_id=file_ingestion_id,
        title=title,
        title_normalized=title.lower(),
        short_description="A test event",
        short_description_normalized="a test event",
        source_type="artikel",
        source_code="test",
        location_name="Test Location",
        location_city=city,
        location_city_normalized=city.lower(),
        geo_latitude=48.1,
        geo_longitude=7.8,
        geo_confidence=0.9,
        blocking_keys=["dc|2026-02-12|testcity"],
        categories=["test"],
        is_family_event=True,
        is_child_focused=False,
        admission_free=True,
    )


def _make_event_date(
    event_id: str,
    date: dt.date = dt.date(2026, 2, 12),
    start_time: dt.time | None = dt.time(10, 0),
) -> EventDate:
    """Helper: create an EventDate record."""
    return EventDate(
        event_id=event_id,
        date=date,
        start_time=start_time,
    )


def _make_pipeline_result(
    clusters: list[set[str]],
    flagged_clusters: list[set[str]] | None = None,
    canonical_dicts: list[dict] | None = None,
    decisions: list[MatchDecisionRecord] | None = None,
) -> PipelineResult:
    """Helper: create a PipelineResult from clusters and optional decisions."""
    flagged = flagged_clusters or []

    if canonical_dicts is None:
        canonical_dicts = []
        for cluster in clusters + flagged:
            canonical_dicts.append(
                {
                    "title": f"Canonical from {len(cluster)} sources",
                    "short_description": "Test canonical event",
                    "description": "A longer description",
                    "highlights": ["highlight1"],
                    "location_name": "Test Location",
                    "location_city": "TestCity",
                    "location_district": "TestDistrict",
                    "location_street": "Test Street",
                    "location_zipcode": "12345",
                    "geo_latitude": 48.1,
                    "geo_longitude": 7.8,
                    "geo_confidence": 0.9,
                    "dates": [{"date": "2026-02-12", "start_time": "10:00", "end_time": None, "end_date": None}],
                    "categories": ["test"],
                    "is_family_event": True,
                    "is_child_focused": False,
                    "admission_free": True,
                    "field_provenance": {"title": sorted(cluster)[0]},
                    "source_count": len(cluster),
                    "match_confidence": 0.85 if len(cluster) > 1 else None,
                    "needs_review": cluster in flagged,
                }
            )

    if decisions is None:
        decisions = []

    match_result = MatchResult(
        decisions=decisions,
        pair_stats=CandidatePairStats(
            total_events=sum(len(c) for c in clusters + flagged),
            total_possible_pairs=100,
            blocked_pairs=len(decisions),
            reduction_pct=95.0,
        ),
        match_count=sum(1 for d in decisions if d.decision == "match"),
        ambiguous_count=sum(1 for d in decisions if d.decision == "ambiguous"),
        no_match_count=sum(1 for d in decisions if d.decision == "no_match"),
    )

    cluster_result = ClusterResult(
        clusters=clusters,
        flagged_clusters=flagged,
        singleton_count=sum(1 for c in clusters if len(c) == 1),
        total_cluster_count=len(clusters) + len(flagged),
    )

    return PipelineResult(
        match_result=match_result,
        cluster_result=cluster_result,
        canonical_events=canonical_dicts,
        canonical_count=len(canonical_dicts),
        flagged_count=len(flagged),
    )


async def _seed_source_events(
    session_factory: async_sessionmaker[AsyncSession],
    event_ids: list[str],
) -> None:
    """Insert file ingestion + source events + dates into the test DB."""
    async with session_factory() as session, session.begin():
        fi = _make_file_ingestion()
        session.add(fi)
        await session.flush()

        for eid in event_ids:
            evt = _make_source_event(eid, file_ingestion_id=fi.id, title=f"Event {eid}")
            session.add(evt)
            date_record = _make_event_date(eid)
            session.add(date_record)


# ---- Tests for load_all_events_as_dicts ----


async def test_load_all_events_returns_correct_format(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Inserted source events are loaded as dicts with all required keys."""
    await _seed_source_events(test_session_factory, ["evt-1", "evt-2"])

    async with test_session_factory() as session:
        events = await load_all_events_as_dicts(session)

    assert len(events) == 2

    required_keys = {
        "id", "title", "title_normalized", "short_description",
        "short_description_normalized", "description", "highlights",
        "location_name", "location_city", "location_district",
        "location_street", "location_zipcode",
        "geo_latitude", "geo_longitude", "geo_confidence",
        "source_code", "source_type", "blocking_keys",
        "categories", "is_family_event", "is_child_focused",
        "admission_free", "dates",
    }
    for evt in events:
        assert required_keys.issubset(set(evt.keys()))


async def test_load_all_events_dates_are_strings(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Dates are serialized as strings, not date/time objects."""
    await _seed_source_events(test_session_factory, ["evt-1"])

    async with test_session_factory() as session:
        events = await load_all_events_as_dicts(session)

    assert len(events) == 1
    assert len(events[0]["dates"]) == 1
    d = events[0]["dates"][0]
    assert isinstance(d["date"], str)
    assert d["start_time"] is None or isinstance(d["start_time"], str)


# ---- Tests for replace_canonical_events ----


async def test_replace_creates_canonical_and_sources_and_decisions(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """replace_canonical_events creates canonical events, source links, and match decisions."""
    event_ids = ["evt-a", "evt-b", "evt-c"]
    await _seed_source_events(test_session_factory, event_ids)

    decisions = [
        MatchDecisionRecord(
            event_id_a="evt-a",
            event_id_b="evt-b",
            signals=SignalScores(date=0.9, geo=0.8, title=0.7, description=0.6),
            combined_score_value=0.85,
            decision="match",
        ),
    ]

    pipeline_result = _make_pipeline_result(
        clusters=[{"evt-a", "evt-b"}, {"evt-c"}],
        decisions=decisions,
    )

    async with test_session_factory() as session, session.begin():
        count = await replace_canonical_events(session, pipeline_result)

    assert count == 2

    async with test_session_factory() as session:
        # Verify canonical events
        result = await session.execute(select(CanonicalEvent))
        canonicals = result.scalars().all()
        assert len(canonicals) == 2

        # Verify source links
        result = await session.execute(select(CanonicalEventSource))
        sources = result.scalars().all()
        assert len(sources) == 3  # 2 from cluster + 1 singleton

        # Verify match decisions
        result = await session.execute(select(MatchDecision))
        decisions_db = result.scalars().all()
        assert len(decisions_db) == 1
        assert decisions_db[0].decision == "match"
        assert decisions_db[0].combined_score == 0.85


async def test_replace_clears_previous_data(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """replace_canonical_events deletes old data before inserting new."""
    event_ids = ["evt-1", "evt-2", "evt-3"]
    await _seed_source_events(test_session_factory, event_ids)

    # First run: 2 canonicals
    first_result = _make_pipeline_result(
        clusters=[{"evt-1", "evt-2"}, {"evt-3"}],
        decisions=[
            MatchDecisionRecord(
                event_id_a="evt-1",
                event_id_b="evt-2",
                signals=SignalScores(date=0.9, geo=0.8, title=0.7, description=0.6),
                combined_score_value=0.85,
                decision="match",
            ),
        ],
    )
    async with test_session_factory() as session, session.begin():
        await replace_canonical_events(session, first_result)

    # Second run: 1 canonical (different clustering)
    second_result = _make_pipeline_result(
        clusters=[{"evt-1", "evt-2", "evt-3"}],
        decisions=[
            MatchDecisionRecord(
                event_id_a="evt-1",
                event_id_b="evt-2",
                signals=SignalScores(date=0.9, geo=0.8, title=0.7, description=0.6),
                combined_score_value=0.85,
                decision="match",
            ),
            MatchDecisionRecord(
                event_id_a="evt-2",
                event_id_b="evt-3",
                signals=SignalScores(date=0.8, geo=0.7, title=0.6, description=0.5),
                combined_score_value=0.75,
                decision="match",
            ),
        ],
    )
    async with test_session_factory() as session, session.begin():
        count = await replace_canonical_events(session, second_result)

    assert count == 1

    async with test_session_factory() as session:
        # Only 1 canonical should exist now
        result = await session.execute(select(CanonicalEvent))
        canonicals = result.scalars().all()
        assert len(canonicals) == 1

        # 3 source links (all events in one cluster)
        result = await session.execute(select(CanonicalEventSource))
        sources = result.scalars().all()
        assert len(sources) == 3

        # 2 match decisions (from second run)
        result = await session.execute(select(MatchDecision))
        decisions_db = result.scalars().all()
        assert len(decisions_db) == 2


async def test_source_links_match_cluster_membership(
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Source links use full cluster membership, not just field_provenance."""
    event_ids = ["evt-x", "evt-y", "evt-z"]
    await _seed_source_events(test_session_factory, event_ids)

    # 3-event cluster
    pipeline_result = _make_pipeline_result(
        clusters=[{"evt-x", "evt-y", "evt-z"}],
        decisions=[
            MatchDecisionRecord(
                event_id_a="evt-x",
                event_id_b="evt-y",
                signals=SignalScores(date=0.9, geo=0.8, title=0.7, description=0.6),
                combined_score_value=0.85,
                decision="match",
            ),
            MatchDecisionRecord(
                event_id_a="evt-y",
                event_id_b="evt-z",
                signals=SignalScores(date=0.8, geo=0.7, title=0.6, description=0.5),
                combined_score_value=0.75,
                decision="match",
            ),
        ],
    )

    async with test_session_factory() as session, session.begin():
        await replace_canonical_events(session, pipeline_result)

    async with test_session_factory() as session:
        result = await session.execute(select(CanonicalEvent))
        canonicals = result.scalars().all()
        assert len(canonicals) == 1
        canonical = canonicals[0]

        # Should have 3 source links (full cluster), not just field_provenance entries
        result = await session.execute(
            select(CanonicalEventSource).where(
                CanonicalEventSource.canonical_event_id == canonical.id
            )
        )
        sources = result.scalars().all()
        source_ids = {s.source_event_id for s in sources}
        assert source_ids == {"evt-x", "evt-y", "evt-z"}
