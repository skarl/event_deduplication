"""Pipeline orchestrator bridging ingestion, matching, and persistence.

Provides the runtime logic that connects:
1. File ingestion (FileProcessor)
2. Loading all source events from DB
3. Running the matching pipeline (pure function)
4. Persisting canonical events and match decisions
"""

from __future__ import annotations

from pathlib import Path

import structlog
from sqlalchemy.ext.asyncio import async_sessionmaker

from event_dedup.ai_matching.resolver import resolve_ambiguous_pairs
from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.matching.config import MatchingConfig, load_config_for_run
from event_dedup.matching.pipeline import rebuild_pipeline_result, run_full_pipeline
from event_dedup.worker.persistence import (
    load_all_events_as_dicts,
    replace_canonical_events,
)

logger = structlog.get_logger()


async def _maybe_resolve_ai(
    pipeline_result,
    events: list[dict],
    matching_config: MatchingConfig,
    session_factory: async_sessionmaker,
):
    """Apply AI resolution to ambiguous pairs if enabled.

    Calls resolve_ambiguous_pairs on the match result. If any ambiguous
    pairs were resolved, rebuilds clustering and synthesis via
    rebuild_pipeline_result. Returns the original result unchanged if
    AI is disabled or no ambiguous pairs were resolved.
    """
    if not matching_config.ai.enabled or not matching_config.ai.api_key:
        return pipeline_result

    original_ambiguous = pipeline_result.match_result.ambiguous_count
    updated_match_result = await resolve_ambiguous_pairs(
        pipeline_result.match_result,
        events,
        matching_config.ai,
        session_factory,
    )

    if updated_match_result.ambiguous_count == original_ambiguous:
        return pipeline_result  # No changes, skip re-clustering

    # Re-cluster and re-synthesize with updated decisions
    return rebuild_pipeline_result(updated_match_result, events, matching_config)


async def process_new_file(
    file_path: Path,
    file_processor: FileProcessor,
    session_factory: async_sessionmaker,
    matching_config: MatchingConfig | None = None,
) -> dict:
    """Full pipeline: ingest file -> load all events -> match -> persist canonicals.

    Args:
        file_path: Path to the new JSON file.
        file_processor: Configured FileProcessor instance.
        session_factory: Async session factory for DB access.
        matching_config: Matching pipeline configuration.  If ``None``,
            the config is loaded from the database (or YAML fallback)
            for each run.

    Returns:
        Stats dict with status and per-file processing metrics.
    """
    if matching_config is None:
        matching_config = await load_config_for_run(session_factory)
    log = logger.bind(file=file_path.name)

    # Step 1: Ingest file
    result = await file_processor.process_file(file_path)
    if result.status != "completed":
        log.info("file_skipped", status=result.status, reason=result.reason)
        return {"status": result.status, "file": file_path.name, "reason": result.reason}

    log.info("file_ingested", event_count=result.event_count)

    try:
        # Step 2: Load ALL source events from DB
        async with session_factory() as session:
            events = await load_all_events_as_dicts(session)
        log.info("events_loaded", total_events=len(events))

        # Step 3: Run matching pipeline (pure function)
        pipeline_result = run_full_pipeline(events, matching_config)

        # Step 3.5: AI-assisted resolution of ambiguous pairs
        pipeline_result = await _maybe_resolve_ai(
            pipeline_result, events, matching_config, session_factory
        )

        log.info(
            "matching_complete",
            matches=pipeline_result.match_result.match_count,
            ambiguous=pipeline_result.match_result.ambiguous_count,
            canonical_count=pipeline_result.canonical_count,
            flagged_count=pipeline_result.flagged_count,
            reduction_pct=pipeline_result.match_result.pair_stats.reduction_pct,
        )

        # Step 4: Persist canonical events
        async with session_factory() as session, session.begin():
            count = await replace_canonical_events(session, pipeline_result)
        log.info("pipeline_complete", canonical_events_written=count)

        return {
            "status": "completed",
            "file": file_path.name,
            "events_ingested": result.event_count,
            "total_events": len(events),
            "matches_found": pipeline_result.match_result.match_count,
            "ambiguous": pipeline_result.match_result.ambiguous_count,
            "canonicals_created": pipeline_result.canonical_count,
            "flagged_for_review": pipeline_result.flagged_count,
        }
    except Exception as e:
        log.error("pipeline_failed", error=str(e), exc_info=True)
        return {"status": "error", "file": file_path.name, "error": str(e)}


async def process_existing_files(
    data_dir: Path,
    file_processor: FileProcessor,
    session_factory: async_sessionmaker,
    matching_config: MatchingConfig | None = None,
) -> int:
    """Scan directory for existing .json files and process each.

    The idempotency check in FileProcessor handles already-processed
    files by returning status="skipped".

    Args:
        data_dir: Directory to scan for JSON files.
        file_processor: Configured FileProcessor instance.
        session_factory: Async session factory for DB access.
        matching_config: Matching pipeline configuration.  If ``None``,
            each file will load config from DB per run.

    Returns:
        Number of files that completed processing (not skipped/failed).
    """
    log = logger.bind(data_dir=str(data_dir))
    json_files = sorted(data_dir.glob("*.json"))
    processed = 0

    for file_path in json_files:
        stats = await process_new_file(
            file_path, file_processor, session_factory, matching_config
        )
        if stats.get("status") == "completed":
            processed += 1

    log.info(
        "startup_scan_complete",
        files_found=len(json_files),
        files_processed=processed,
    )
    return processed


async def process_file_batch(
    file_paths: list[Path],
    file_processor: FileProcessor,
    session_factory: async_sessionmaker,
    matching_config: MatchingConfig | None = None,
) -> list[dict]:
    """Process a batch of files that arrived simultaneously.

    Ingests ALL files first (each creates source events), then runs
    matching ONCE across all events.  More efficient than per-file matching.

    Args:
        file_paths: List of JSON file paths to process.
        file_processor: Configured FileProcessor instance.
        session_factory: Async session factory for DB access.
        matching_config: Matching pipeline configuration.  If ``None``,
            the config is loaded from the database (or YAML fallback).

    Returns:
        List of stats dicts, one per file.
    """
    if matching_config is None:
        matching_config = await load_config_for_run(session_factory)
    log = logger.bind(batch_size=len(file_paths))
    results = []
    any_completed = False

    # Step 1: Ingest all files sequentially
    for file_path in file_paths:
        ingest_result = await file_processor.process_file(file_path)
        results.append(
            {
                "file": file_path.name,
                "status": ingest_result.status,
                "events_ingested": ingest_result.event_count,
                "reason": ingest_result.reason,
            }
        )
        if ingest_result.status == "completed":
            any_completed = True
            log.info("file_ingested", file=file_path.name, event_count=ingest_result.event_count)

    if not any_completed:
        log.info("batch_no_new_files", files=len(file_paths))
        return results

    try:
        # Step 2: Load all events and run pipeline once
        async with session_factory() as session:
            events = await load_all_events_as_dicts(session)
        log.info("events_loaded", total_events=len(events))

        pipeline_result = run_full_pipeline(events, matching_config)

        # AI-assisted resolution of ambiguous pairs
        pipeline_result = await _maybe_resolve_ai(
            pipeline_result, events, matching_config, session_factory
        )

        log.info(
            "matching_complete",
            matches=pipeline_result.match_result.match_count,
            canonical_count=pipeline_result.canonical_count,
            flagged_count=pipeline_result.flagged_count,
        )

        # Step 3: Persist
        async with session_factory() as session, session.begin():
            count = await replace_canonical_events(session, pipeline_result)
        log.info("batch_pipeline_complete", canonical_events_written=count)

        # Enrich completed results with pipeline stats
        for r in results:
            if r["status"] == "completed":
                r["total_events"] = len(events)
                r["matches_found"] = pipeline_result.match_result.match_count
                r["canonicals_created"] = pipeline_result.canonical_count
                r["flagged_for_review"] = pipeline_result.flagged_count

    except Exception as e:
        log.error("batch_pipeline_failed", error=str(e), exc_info=True)
        for r in results:
            if r["status"] == "completed":
                r["status"] = "error"
                r["error"] = str(e)

    return results
