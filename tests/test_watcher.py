"""Tests for the file watcher module."""

import asyncio
from pathlib import Path

import pytest
from watchfiles import Change

from event_dedup.worker.watcher import json_added_filter, watch_and_process


# ---- Tests for json_added_filter ----


def test_json_added_filter_accepts_json_added():
    """Filter returns True for newly added .json files."""
    assert json_added_filter(Change.added, "/path/to/file.json") is True


def test_json_added_filter_rejects_non_json():
    """Filter returns False for non-json files."""
    assert json_added_filter(Change.added, "/path/to/file.txt") is False
    assert json_added_filter(Change.added, "/path/to/file.csv") is False
    assert json_added_filter(Change.added, "/path/to/file.jsonl") is False


def test_json_added_filter_rejects_modified():
    """Filter returns False for modified (not added) files."""
    assert json_added_filter(Change.modified, "/path/to/file.json") is False


def test_json_added_filter_rejects_deleted():
    """Filter returns False for deleted files."""
    assert json_added_filter(Change.deleted, "/path/to/file.json") is False


# ---- Tests for watch_and_process ----


async def test_watch_and_process_stops_on_stop_event(tmp_path: Path) -> None:
    """watch_and_process exits cleanly when stop_event is set."""
    stop_event = asyncio.Event()

    # Set stop_event after a very short delay
    async def set_stop():
        await asyncio.sleep(0.1)
        stop_event.set()

    asyncio.create_task(set_stop())

    # watch_and_process should exit without error
    # We use a mock-like approach: pass None for dependencies that
    # won't be called since stop_event fires before any files arrive
    await watch_and_process(
        data_dir=tmp_path,
        file_processor=None,  # type: ignore[arg-type]
        session_factory=None,  # type: ignore[arg-type]
        matching_config=None,  # type: ignore[arg-type]
        stop_event=stop_event,
    )
    # If we reach here without hanging, the test passes
