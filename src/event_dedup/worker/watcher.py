"""Async file watcher using watchfiles awatch with .json filter.

Monitors a directory for newly added JSON files and delegates processing
to the pipeline orchestrator.
"""

from __future__ import annotations

import asyncio
from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker
from watchfiles import Change, awatch

from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.matching.config import MatchingConfig
from event_dedup.worker.orchestrator import process_file_batch, process_new_file


def json_added_filter(change: Change, path: str) -> bool:
    """Only react to newly added .json files."""
    return change == Change.added and path.endswith(".json")


async def watch_and_process(
    data_dir: Path,
    file_processor: FileProcessor,
    session_factory: async_sessionmaker,
    matching_config: MatchingConfig,
    stop_event: asyncio.Event | None = None,
) -> None:
    """Watch data_dir for new JSON files and process them.

    Single files are processed via ``process_new_file``; batches
    (multiple files detected in one watch cycle) are handled via
    ``process_file_batch`` for efficiency.

    Args:
        data_dir: Directory to watch.
        file_processor: Configured FileProcessor instance.
        session_factory: Async session factory for DB access.
        matching_config: Matching pipeline configuration.
        stop_event: Optional event to signal graceful shutdown.
    """
    log = structlog.get_logger().bind(watch_dir=str(data_dir))
    log.info("watcher_started")

    async for changes in awatch(
        data_dir, watch_filter=json_added_filter, stop_event=stop_event
    ):
        file_paths = [Path(path) for _, path in changes]
        log.info("files_detected", count=len(file_paths))

        if len(file_paths) == 1:
            await process_new_file(
                file_paths[0], file_processor, session_factory, matching_config
            )
        else:
            await process_file_batch(
                file_paths, file_processor, session_factory, matching_config
            )

    log.info("watcher_stopped")
