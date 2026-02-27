"""Tests for the file processor module."""

import json
import shutil
from pathlib import Path
from unittest.mock import patch

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.models.event_date import EventDate
from event_dedup.models.file_ingestion import FileIngestion
from event_dedup.models.source_event import SourceEvent


@pytest.fixture
def processor(test_session_factory: async_sessionmaker[AsyncSession], tmp_dead_letter_dir: Path) -> FileProcessor:
    """Create a FileProcessor with test fixtures."""
    return FileProcessor(session_factory=test_session_factory, dead_letter_dir=tmp_dead_letter_dir)


async def test_process_file_creates_records(
    processor: FileProcessor,
    sample_event_file: Path,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Process the bwb sample file and verify records are created."""
    result = await processor.process_file(sample_event_file)
    assert result.status == "completed"
    assert result.event_count == 28

    # Verify FileIngestion record
    async with test_session_factory() as session:
        fi_result = await session.execute(select(FileIngestion))
        ingestions = fi_result.scalars().all()
        assert len(ingestions) == 1
        assert ingestions[0].status == "completed"
        assert ingestions[0].event_count == 28

        # Verify SourceEvent records
        se_result = await session.execute(select(SourceEvent))
        events = se_result.scalars().all()
        assert len(events) == 28


async def test_process_file_idempotency(
    processor: FileProcessor,
    sample_event_file: Path,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Process the same file twice and verify second call is skipped."""
    result1 = await processor.process_file(sample_event_file)
    assert result1.status == "completed"

    result2 = await processor.process_file(sample_event_file)
    assert result2.status == "skipped"
    assert result2.reason == "already processed"

    # Verify still only 28 events
    async with test_session_factory() as session:
        se_result = await session.execute(select(SourceEvent))
        events = se_result.scalars().all()
        assert len(events) == 28


async def test_process_file_creates_event_dates(
    processor: FileProcessor,
    sample_event_file: Path,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify EventDate records are created, including multi-date events."""
    await processor.process_file(sample_event_file)

    async with test_session_factory() as session:
        # Check Primel-Aktion has 2 date rows
        primel_dates = await session.execute(
            select(EventDate).where(EventDate.event_id == "pdf-9d58bea1-3-1")
        )
        dates = primel_dates.scalars().all()
        assert len(dates) == 2

        # Check total EventDate records exist
        all_dates = await session.execute(select(EventDate))
        all_date_rows = all_dates.scalars().all()
        assert len(all_date_rows) > 0


async def test_process_file_city_from_sanitize_result(
    processor: FileProcessor,
    sample_event_file: Path,
    test_session_factory: async_sessionmaker[AsyncSession],
) -> None:
    """Verify events use _sanitizeResult.city as authoritative city."""
    await processor.process_file(sample_event_file)

    async with test_session_factory() as session:
        # First event (pdf-9d58bea1-1-6) should have city from _sanitizeResult
        result = await session.execute(
            select(SourceEvent).where(SourceEvent.id == "pdf-9d58bea1-1-6")
        )
        event = result.scalar_one()
        assert event.location_city == "Kenzingen"


async def test_process_file_transaction_rollback(
    test_session_factory: async_sessionmaker[AsyncSession],
    tmp_dead_letter_dir: Path,
    sample_event_file: Path,
) -> None:
    """Mock a failure during event creation and verify no records exist."""
    processor = FileProcessor(session_factory=test_session_factory, dead_letter_dir=tmp_dead_letter_dir)

    # Make a copy of the file so the dead letter move doesn't affect the original
    work_file = tmp_dead_letter_dir.parent / "work_copy.json"
    shutil.copy2(sample_event_file, work_file)

    with patch(
        "event_dedup.ingestion.file_processor._build_source_event",
        side_effect=RuntimeError("simulated failure"),
    ):
        result = await processor.process_file(work_file)

    assert result.status == "failed"

    # Verify no SourceEvent records exist (transaction rolled back)
    async with test_session_factory() as session:
        se_result = await session.execute(select(SourceEvent))
        events = se_result.scalars().all()
        assert len(events) == 0


async def test_dead_letter_on_failure(
    test_session_factory: async_sessionmaker[AsyncSession],
    tmp_dead_letter_dir: Path,
    tmp_path: Path,
) -> None:
    """Process an invalid file and verify it gets moved to dead_letter_dir."""
    # Create a file with valid JSON but invalid event structure
    bad_file = tmp_path / "bad_events.json"
    bad_file.write_text(json.dumps({"events": [{"invalid": "data"}]}), encoding="utf-8")

    processor = FileProcessor(session_factory=test_session_factory, dead_letter_dir=tmp_dead_letter_dir)
    result = await processor.process_file(bad_file)

    assert result.status == "failed"
    # File should be moved to dead letter dir
    assert (tmp_dead_letter_dir / "bad_events.json").exists()
    assert not bad_file.exists()
