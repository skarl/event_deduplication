---
phase: 03-pipeline-integration
plan: 01
subsystem: pipeline-worker
tags: [worker, watcher, orchestrator, persistence, logging, structlog, watchfiles]
dependency_graph:
  requires: [02-04]
  provides: [watch_and_process, process_new_file, process_existing_files, process_file_batch, load_all_events_as_dicts, replace_canonical_events, configure_logging]
  affects: [matching-pipeline, canonical-events, file-processor]
tech_stack:
  added: [watchfiles, structlog]
  patterns: [clear-and-replace, ProcessorFormatter-unified-logging, async-file-watching, graceful-shutdown-via-stop-event]
key_files:
  created:
    - src/event_dedup/worker/__init__.py
    - src/event_dedup/worker/watcher.py
    - src/event_dedup/worker/orchestrator.py
    - src/event_dedup/worker/persistence.py
    - src/event_dedup/worker/__main__.py
    - src/event_dedup/logging_config.py
    - tests/test_persistence.py
    - tests/test_orchestrator.py
    - tests/test_watcher.py
  modified:
    - pyproject.toml
    - src/event_dedup/config/settings.py
decisions:
  - Explicit CanonicalEventSource delete before CanonicalEvent delete to avoid SQLite foreign key CASCADE limitation
  - Source links derived from cluster membership (not field_provenance) for completeness
  - Separate transactions for file ingestion and canonical persistence (clear-and-replace rebuilds all canonicals each run)
metrics:
  duration: 5m
  completed: 2026-02-28
  tasks_completed: 5
  tasks_total: 5
  test_count: 15
  total_test_suite: 272
  files_created: 9
  files_modified: 2
  lines_added: ~1200
---

# Phase 3 Plan 1: Pipeline Worker Service Summary

Pipeline worker service with watchfiles-based file watcher, orchestrator bridging ingestion/matching/persistence, clear-and-replace canonical event DB persistence, unified structlog+stdlib JSON logging, and 15 new tests covering all components.

## What Was Built

### Structured Logging (`logging_config.py`, 62 lines)
`configure_logging(json_output, log_level)` sets up structlog's ProcessorFormatter so both `structlog.get_logger()` and existing `logging.getLogger(__name__)` calls (used in file_processor.py, alembic env.py) produce uniform JSON output. Console renderer mode available for development.

### Canonical Event Persistence (`worker/persistence.py`, 151 lines)
Two core functions:
- `load_all_events_as_dicts(session)` -- queries all SourceEvents with eager-loaded dates, converts to pipeline-compatible dict format
- `replace_canonical_events(session, pipeline_result)` -- in a single transaction: deletes all MatchDecisions, CanonicalEventSources, and CanonicalEvents, then inserts fresh data from the pipeline result

Key design: source links use cluster membership from `pipeline_result.cluster_result.clusters` (not `field_provenance`), ensuring all cluster members are linked even if they didn't contribute a field value.

### Pipeline Orchestrator (`worker/orchestrator.py`, 178 lines)
Three functions connecting the pipeline stages:
- `process_new_file()` -- full pipeline: ingest file -> load all events -> run_full_pipeline -> persist canonicals. Structured logs at each stage.
- `process_existing_files()` -- startup scan: glob *.json, process each (idempotency check handles already-processed).
- `process_file_batch()` -- batch mode: ingest all files first, then run matching once for efficiency.

### File Watcher (`worker/watcher.py`, 64 lines)
- `json_added_filter()` -- watchfiles filter for `Change.added` + `.json` extension
- `watch_and_process()` -- async loop via `awatch` with stop_event for graceful shutdown. Single files use `process_new_file`; batches use `process_file_batch`.

### Worker Entry Point (`worker/__main__.py`, 57 lines)
`python -m event_dedup.worker` configures logging, loads settings, processes existing files on startup, then enters the file watch loop. SIGTERM/SIGINT set an asyncio.Event for graceful shutdown.

### Settings Extended (`config/settings.py`)
Added `matching_config_path`, `log_json`, `log_level` -- all configurable via `EVENT_DEDUP_` env prefix.

### Test Coverage (15 new tests)
- `test_persistence.py` (5 tests): dict format, creation, replacement, cluster membership
- `test_orchestrator.py` (5 tests): full pipeline, skip, failure, directory scan, batch
- `test_watcher.py` (5 tests): filter accept/reject, graceful shutdown

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Explicit CanonicalEventSource delete for SQLite compatibility**
- **Found during:** Task 3
- **Issue:** SQLite does not enforce ON DELETE CASCADE without `PRAGMA foreign_keys = ON`. The `delete(CanonicalEvent)` statement did not cascade-delete CanonicalEventSource rows, causing UNIQUE constraint violations on re-insert.
- **Fix:** Added explicit `delete(CanonicalEventSource)` before `delete(CanonicalEvent)` in `replace_canonical_events`.
- **Files modified:** `src/event_dedup/worker/persistence.py`
- **Commit:** 059db9b

## Verification Results

All verification checks from the plan pass:
- 15 new tests: PASS
- Full test suite (272 tests): PASS
- Import chain verification: PASS
- JSON logging verification: PASS (both structlog and stdlib produce JSON)

## Commits

| Task | Commit  | Description |
|------|---------|-------------|
| 1    | 4344cca | Add watchfiles and structlog dependencies, extend settings |
| 2    | b77ba57 | Unified structlog + stdlib JSON logging configuration |
| 3    | 059db9b | Canonical event persistence with clear-and-replace strategy |
| 4    | 9a6d3cf | Pipeline orchestrator connecting ingestion, matching, and persistence |
| 5    | ea443b7 | File watcher and worker entry point with graceful shutdown |

## Requirements Addressed

- **PIPE-01**: File watcher detects new .json files in configured directory and triggers processing
- **PIPE-05**: Structured JSON logs report events_ingested, total_events, matches_found, canonicals_created, flagged_for_review per file

## Self-Check: PASSED

All 10 created files verified present. All 5 task commits verified in git log.
