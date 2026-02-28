"""Tests for the CLI export command."""

import json
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path
from unittest.mock import patch

import pytest

from event_dedup.cli.__main__ import run_export
from event_dedup.models.canonical_event import CanonicalEvent


@pytest.fixture
async def _seed_events(test_session_factory):
    """Seed the test DB with canonical events at known timestamps."""
    now = datetime.now(timezone.utc)

    async with test_session_factory() as session:
        async with session.begin():
            ce1 = CanonicalEvent(
                title="Early Event",
                location_city="Freiburg",
                dates=[{"date": "2026-02-10"}],
                categories=["test"],
                source_count=1,
                needs_review=False,
            )
            session.add(ce1)
            await session.flush()

            ce2 = CanonicalEvent(
                title="Later Event",
                location_city="Offenburg",
                dates=[{"date": "2026-06-20"}],
                categories=["test2"],
                source_count=1,
                needs_review=False,
            )
            session.add(ce2)


@pytest.mark.asyncio
async def test_run_export_with_seeded_db(test_session_factory, seeded_db, tmp_path):
    """run_export writes JSON files to the output directory when events exist."""
    output_dir = tmp_path / "out"

    with patch("event_dedup.cli.__main__.get_session_factory", return_value=test_session_factory):
        await run_export(
            created_after=None,
            modified_after=None,
            output_dir=output_dir,
        )

    # Should have created at least one export file
    files = list(output_dir.glob("export_*_part_*.json"))
    assert len(files) >= 1

    # Parse and verify structure
    data = json.loads(files[0].read_text())
    assert "events" in data
    assert "metadata" in data
    assert data["metadata"]["eventCount"] == len(data["events"])
    assert data["metadata"]["eventCount"] > 0
    # Verify events have the expected structure (input format)
    first_event = data["events"][0]
    assert "title" in first_event
    assert "event_dates" in first_event


@pytest.mark.asyncio
async def test_run_export_with_date_filter(test_session_factory, _seed_events, tmp_path):
    """run_export with created_after filters events by creation timestamp."""
    output_dir = tmp_path / "filtered"

    # Use a future timestamp that should match no events
    far_future = datetime(2099, 1, 1, tzinfo=timezone.utc)

    with patch("event_dedup.cli.__main__.get_session_factory", return_value=test_session_factory):
        await run_export(
            created_after=far_future,
            modified_after=None,
            output_dir=output_dir,
        )

    files = list(output_dir.glob("export_*_part_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["events"] == []
    assert data["metadata"]["eventCount"] == 0


@pytest.mark.asyncio
async def test_run_export_empty_result(test_session_factory, tmp_path):
    """run_export with no events in DB produces a file with empty events array."""
    output_dir = tmp_path / "empty"

    with patch("event_dedup.cli.__main__.get_session_factory", return_value=test_session_factory):
        await run_export(
            created_after=None,
            modified_after=None,
            output_dir=output_dir,
        )

    files = list(output_dir.glob("export_*_part_*.json"))
    assert len(files) == 1
    data = json.loads(files[0].read_text())
    assert data["events"] == []
    assert data["metadata"]["eventCount"] == 0
    assert data["metadata"]["part"] == 1
    assert data["metadata"]["totalParts"] == 1


def test_cli_help_does_not_error():
    """CLI --help exits cleanly without error."""
    result = subprocess.run(
        [sys.executable, "-m", "event_dedup.cli", "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0
    assert "Event Deduplication CLI" in result.stdout


def test_cli_export_help_does_not_error():
    """CLI export --help exits cleanly and shows flags."""
    result = subprocess.run(
        [sys.executable, "-m", "event_dedup.cli", "export", "--help"],
        capture_output=True,
        text=True,
        cwd=str(Path(__file__).resolve().parents[1]),
    )
    assert result.returncode == 0
    assert "--created-after" in result.stdout
    assert "--modified-after" in result.stdout
    assert "--output-dir" in result.stdout
