"""Shared test fixtures."""

from pathlib import Path

import pytest
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

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
