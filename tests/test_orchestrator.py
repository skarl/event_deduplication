"""Integration tests for the pipeline orchestrator."""

import json
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.matching.config import MatchingConfig
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.canonical_event_source import CanonicalEventSource
from event_dedup.worker.orchestrator import (
    process_existing_files,
    process_file_batch,
    process_new_file,
)


def _make_event(
    event_id: str,
    title: str,
    source_type: str = "artikel",
    city: str = "Freiburg",
    date: str = "2026-03-15",
    start_time: str = "10:00",
    lat: float = 47.999,
    lon: float = 7.842,
) -> dict:
    """Create a single event dict for a test JSON file."""
    return {
        "id": event_id,
        "title": title,
        "short_description": f"Description for {title}",
        "event_dates": [{"date": date, "start_time": start_time}],
        "location": {
            "name": "Testort",
            "city": city,
            "_sanitizeResult": {"city": city, "confidence": 1},
            "geo": {
                "latitude": lat,
                "longitude": lon,
                "confidence": 0.95,
                "country": "DEU",
            },
        },
        "source_type": source_type,
        "categories": ["kultur"],
        "is_family_event": False,
        "is_child_focused": False,
        "admission_free": True,
        "registration_required": False,
        "confidence_score": 0.9,
        "_batch_index": 0,
        "_extracted_at": "2026-02-28T10:00:00Z",
    }


def _write_json_file(dir_path: Path, filename: str, events: list[dict]) -> Path:
    """Write a JSON event file in the expected format."""
    file_path = dir_path / filename
    data = {
        "events": events,
        "rejected": [],
        "metadata": {"processedAt": "2026-02-28T10:00:00Z", "sourceKey": "test.pdf"},
    }
    file_path.write_text(json.dumps(data), encoding="utf-8")
    return file_path


@pytest.fixture
def matching_config() -> MatchingConfig:
    """Return default matching config for tests."""
    return MatchingConfig()


@pytest.fixture
def processor(
    test_session_factory: async_sessionmaker[AsyncSession],
    tmp_dead_letter_dir: Path,
) -> FileProcessor:
    """Create a FileProcessor with test fixtures."""
    return FileProcessor(
        session_factory=test_session_factory,
        dead_letter_dir=tmp_dead_letter_dir,
    )


# ---- Tests for process_new_file ----


async def test_process_new_file_completes_full_pipeline(
    processor: FileProcessor,
    test_session_factory: async_sessionmaker[AsyncSession],
    matching_config: MatchingConfig,
    tmp_path: Path,
) -> None:
    """process_new_file ingests, matches, and persists canonical events."""
    # Create a JSON file with 2 events from one source
    events = [
        _make_event("pdf-abc-0-0", "Sommerfest im Park"),
        _make_event("pdf-abc-0-1", "Wintermarkt am Rathaus"),
    ]
    file_path = _write_json_file(tmp_path, "srcA_test.json", events)

    stats = await process_new_file(
        file_path, processor, test_session_factory, matching_config
    )

    assert stats["status"] == "completed"
    assert stats["events_ingested"] == 2
    assert "total_events" in stats
    assert "canonicals_created" in stats

    # Verify canonical events in DB
    async with test_session_factory() as session:
        result = await session.execute(select(CanonicalEvent))
        canonicals = result.scalars().all()
        assert len(canonicals) > 0


async def test_process_new_file_skips_already_processed(
    processor: FileProcessor,
    test_session_factory: async_sessionmaker[AsyncSession],
    matching_config: MatchingConfig,
    tmp_path: Path,
) -> None:
    """Second call to process_new_file with same file returns status='skipped'."""
    events = [_make_event("pdf-def-0-0", "Marktfest")]
    file_path = _write_json_file(tmp_path, "srcB_test.json", events)

    result1 = await process_new_file(
        file_path, processor, test_session_factory, matching_config
    )
    assert result1["status"] == "completed"

    result2 = await process_new_file(
        file_path, processor, test_session_factory, matching_config
    )
    assert result2["status"] == "skipped"


async def test_process_new_file_handles_invalid_json(
    processor: FileProcessor,
    test_session_factory: async_sessionmaker[AsyncSession],
    matching_config: MatchingConfig,
    tmp_path: Path,
) -> None:
    """Invalid JSON file returns status='failed' and goes to dead letter."""
    bad_file = tmp_path / "srcC_bad.json"
    bad_file.write_text('{"events": [{"invalid": "data"}]}', encoding="utf-8")

    stats = await process_new_file(
        bad_file, processor, test_session_factory, matching_config
    )

    assert stats["status"] == "failed"


# ---- Tests for process_existing_files ----


async def test_process_existing_files_scans_directory(
    processor: FileProcessor,
    test_session_factory: async_sessionmaker[AsyncSession],
    matching_config: MatchingConfig,
    tmp_path: Path,
) -> None:
    """process_existing_files finds and processes all JSON files in directory."""
    data_dir = tmp_path / "eventdata"
    data_dir.mkdir()

    # Create 3 JSON files
    for i in range(3):
        events = [
            _make_event(
                f"pdf-scan{i}-0-0",
                f"Scan Event {i}",
                city=f"City{i}",
                date=f"2026-04-{10 + i:02d}",
            )
        ]
        _write_json_file(data_dir, f"src{i}_scan.json", events)

    count = await process_existing_files(
        data_dir, processor, test_session_factory, matching_config
    )

    assert count == 3


# ---- Tests for process_file_batch ----


async def test_process_file_batch_runs_matching_once(
    processor: FileProcessor,
    test_session_factory: async_sessionmaker[AsyncSession],
    matching_config: MatchingConfig,
    tmp_path: Path,
) -> None:
    """process_file_batch ingests multiple files then runs matching once."""
    # Create 2 JSON files with events from different sources that could match
    # (same date, same city, similar title)
    events_a = [
        _make_event(
            "pdf-batchA-0-0",
            "Weihnachtsmarkt Freiburg",
            source_type="artikel",
            city="Freiburg",
            date="2026-12-01",
        ),
    ]
    events_b = [
        _make_event(
            "pdf-batchB-0-0",
            "Weihnachtsmarkt Freiburg Innenstadt",
            source_type="artikel",
            city="Freiburg",
            date="2026-12-01",
        ),
    ]

    file_a = _write_json_file(tmp_path, "srcA_batch.json", events_a)
    file_b = _write_json_file(tmp_path, "srcB_batch.json", events_b)

    results = await process_file_batch(
        [file_a, file_b], processor, test_session_factory, matching_config
    )

    assert len(results) == 2
    assert all(r["status"] == "completed" for r in results)

    # Verify canonical events exist in DB
    async with test_session_factory() as session:
        result = await session.execute(select(CanonicalEvent))
        canonicals = result.scalars().all()
        assert len(canonicals) > 0

        # Verify source links exist
        result = await session.execute(select(CanonicalEventSource))
        sources = result.scalars().all()
        assert len(sources) >= 2  # At least 2 source events linked
