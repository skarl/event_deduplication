"""Shared test fixtures."""

from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from event_dedup.api.app import app
from event_dedup.api.deps import get_db
from event_dedup.models.base import Base

# Path to the real event data files
EVENTDATA_DIR = Path(__file__).resolve().parents[1] / "eventdata"
BWB_SAMPLE = EVENTDATA_DIR / "bwb_11.02.2026_2026-02-11T20-46-41-776Z.json"


@pytest.fixture
def sample_event_file() -> Path:
    """Return path to the bwb sample event file."""
    return BWB_SAMPLE


@pytest.fixture
def tmp_dead_letter_dir(tmp_path: Path) -> Path:
    """Return a temporary dead letter directory."""
    dead_letter = tmp_path / "dead_letters"
    dead_letter.mkdir()
    return dead_letter


@pytest.fixture
def sample_event_json() -> dict:
    """Return a minimal valid event JSON dict for unit tests."""
    return {
        "events": [
            {
                "id": "pdf-test-0-0",
                "title": "Test Event",
                "short_description": "A test event",
                "event_dates": [{"date": "2026-02-12", "start_time": "10:00"}],
                "location": {
                    "name": "Test Location",
                    "city": "TestCity",
                    "_sanitizeResult": {"city": "SanitizedCity", "confidence": 1},
                    "geo": {"longitude": 7.8, "latitude": 48.1, "confidence": 0.9, "country": "DEU"},
                },
                "source_type": "artikel",
                "categories": ["test"],
                "is_family_event": True,
                "is_child_focused": False,
                "admission_free": True,
                "registration_required": False,
                "confidence_score": 0.85,
                "_batch_index": 0,
                "_extracted_at": "2026-02-11T20:46:39.141Z",
            }
        ],
        "rejected": [],
        "metadata": {"processedAt": "2026-02-11T20:46:41.796Z", "sourceKey": "test.pdf"},
    }


@pytest.fixture
async def test_engine():
    """Create an async SQLite in-memory engine for tests."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def test_session_factory(test_engine) -> async_sessionmaker[AsyncSession]:
    """Create an async session factory bound to the test engine."""
    return async_sessionmaker(test_engine, expire_on_commit=False)


@pytest.fixture
async def api_client(test_engine, test_session_factory):
    """Async HTTP client hitting the FastAPI app with test DB."""

    async def override_get_db():
        async with test_session_factory() as session:
            yield session

    app.dependency_overrides[get_db] = override_get_db
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        yield client
    app.dependency_overrides.clear()


@pytest.fixture
async def seeded_db(test_session_factory):
    """Seed the test DB with sample canonical events, sources, and match decisions."""
    import datetime as dt

    from event_dedup.models.canonical_event import CanonicalEvent
    from event_dedup.models.canonical_event_source import CanonicalEventSource
    from event_dedup.models.event_date import EventDate
    from event_dedup.models.file_ingestion import FileIngestion
    from event_dedup.models.match_decision import MatchDecision
    from event_dedup.models.source_event import SourceEvent

    async with test_session_factory() as session:
        async with session.begin():
            # Create file ingestion
            fi = FileIngestion(
                filename="test.json",
                file_hash="testhash123",
                source_code="bwb",
                event_count=2,
                status="completed",
            )
            session.add(fi)
            await session.flush()

            # Create 2 source events
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
            session.add_all([se1, se2])

            # Add dates to source events
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
            session.add_all([ed1, ed2])

            # Create canonical event (merged)
            ce = CanonicalEvent(
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
            session.add(ce)
            await session.flush()

            # Link sources
            link1 = CanonicalEventSource(
                canonical_event_id=ce.id, source_event_id="pdf-aaa-0-0"
            )
            link2 = CanonicalEventSource(
                canonical_event_id=ce.id, source_event_id="pdf-bbb-0-0"
            )
            session.add_all([link1, link2])

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

            # Create a second canonical event (singleton)
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
