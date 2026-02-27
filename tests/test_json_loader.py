"""Tests for the JSON loader module."""

import json
import re
from pathlib import Path

import pytest

from event_dedup.ingestion.json_loader import (
    EventFileData,
    compute_file_hash,
    extract_source_code,
    load_event_file,
)


def test_load_valid_file(sample_event_file: Path) -> None:
    """Load the real bwb sample file and verify it returns EventFileData with 28 events."""
    result = load_event_file(sample_event_file)
    assert isinstance(result, EventFileData)
    assert len(result.events) == 28


def test_load_event_ids(sample_event_file: Path) -> None:
    """Verify all event IDs follow the pdf-{hash}-{batch}-{index} pattern."""
    result = load_event_file(sample_event_file)
    pattern = re.compile(r"^pdf-[a-f0-9]+-\d+-\d+$")
    for event in result.events:
        assert pattern.match(event.id), f"Event ID '{event.id}' does not match expected pattern"


def test_load_event_fields(sample_event_file: Path) -> None:
    """Verify the first event has the expected fields."""
    result = load_event_file(sample_event_file)
    # Find the event by ID (order may not be guaranteed in JSON)
    first_event = next(e for e in result.events if e.id == "pdf-9d58bea1-1-6")
    assert first_event.title == "Nordwiler Narrenfahrplan - Kita-Gizig-Umzug"
    assert first_event.source_type == "artikel"
    # City from _sanitizeResult
    assert first_event.location is not None
    assert first_event.location.sanitize_result is not None
    assert first_event.location.sanitize_result.city == "Kenzingen"


def test_load_multi_date_event(sample_event_file: Path) -> None:
    """Verify the Primel-Aktion event has 2 dates."""
    result = load_event_file(sample_event_file)
    primel = next(e for e in result.events if e.id == "pdf-9d58bea1-3-1")
    assert primel.title.startswith("Primel-Aktion")
    assert len(primel.event_dates) == 2
    dates = sorted([d.date for d in primel.event_dates])
    assert dates == ["2026-02-13", "2026-02-14"]


def test_load_online_event(sample_event_file: Path) -> None:
    """Verify the online event has no city."""
    result = load_event_file(sample_event_file)
    online = next(e for e in result.events if e.id == "pdf-9d58bea1-4-0")
    assert online.location is not None
    assert online.location.city is None


def test_compute_file_hash(sample_event_file: Path) -> None:
    """Verify file hash is 64-char hex and deterministic."""
    hash1 = compute_file_hash(sample_event_file)
    assert len(hash1) == 64
    assert all(c in "0123456789abcdef" for c in hash1)
    # Deterministic
    hash2 = compute_file_hash(sample_event_file)
    assert hash1 == hash2


def test_extract_source_code() -> None:
    """Test source code extraction from various filenames."""
    assert extract_source_code("bwb_11.02.2026_2026-02-11T20-46-41-776Z.json") == "bwb"
    assert extract_source_code("emt_18.02.2026_2026-02-18T19-28-36-646Z.json") == "emt"
    assert extract_source_code("rkb_18.02.2026_2026-02-18T19-31-48-997Z.json") == "rkb"


def test_invalid_json(tmp_path: Path) -> None:
    """Verify ValueError is raised for invalid JSON."""
    bad_file = tmp_path / "bad.json"
    bad_file.write_text("not valid json {{{", encoding="utf-8")
    with pytest.raises(ValueError, match="Invalid JSON"):
        load_event_file(bad_file)
