# Phase 3 Context: Pipeline Integration & Deployment

**Phase goal**: The complete pipeline runs as Docker containers that automatically process new JSON files dropped into a watched directory.

**Created**: 2026-02-28
**Requirements**: PIPE-01, PIPE-05, DEPL-01, DEPL-02, DEPL-03

---

## Success Criteria

1. Dropping a JSON file into the watched directory triggers automatic processing, and canonical events appear in the database without manual intervention
2. Each file is processed in a single database transaction -- if processing fails partway through, no partial data is written
3. Structured processing logs report events processed, matches found, new canonicals created, and errors for each file
4. Running `docker-compose up` starts the full stack (pipeline worker, API server, frontend, PostgreSQL) with all configuration provided via environment variables
5. The pipeline worker, API server, and frontend each run as separate Docker containers

## Phase 2 Interfaces (What We Build On)

### Existing Pipeline Components

**FileProcessor** (`src/event_dedup/ingestion/file_processor.py`):
- `FileProcessor(session_factory, dead_letter_dir, prefix_config_path, city_aliases_path)`
- `async process_file(file_path: Path) -> FileProcessResult`
- Already handles: idempotent hashing, single-transaction writes, dead letter on failure
- Returns: `FileProcessResult(status, event_count, file_hash, reason)`

**Matching Pipeline** (`src/event_dedup/matching/pipeline.py`):
- `run_full_pipeline(events: list[dict], config: MatchingConfig) -> PipelineResult`
- Pure function: events in, PipelineResult out (no DB access)
- Returns: `PipelineResult(match_result, cluster_result, canonical_events, canonical_count, flagged_count)`

**Database Layer**:
- `get_engine()` from `event_dedup.db.engine` -- cached async engine
- `get_session_factory()` from `event_dedup.db.session` -- cached session factory
- `get_session()` context manager for ad-hoc queries

**Settings** (`src/event_dedup/config/settings.py`):
- Pydantic Settings with `EVENT_DEDUP_` env prefix
- `database_url`, `database_url_sync`, `dead_letter_dir`, `event_data_dir`

**Matching Config** (`config/matching.yaml`):
- YAML-driven: scoring weights, thresholds, geo, date, title, cluster, canonical strategies
- Loaded via `load_matching_config()` from `event_dedup.matching.config`

### Database Schema (3 Alembic migrations)
- `file_ingestions`, `source_events`, `event_dates` (Phase 1)
- `ground_truth_pairs` (Phase 1)
- `canonical_events`, `canonical_event_sources`, `match_decisions` (Phase 2)

## What Phase 3 Must Build

### Pipeline Worker Service
1. **File watcher**: Monitor `event_data_dir` for new JSON files
2. **Pipeline orchestrator**: Connect ingestion → load events → matching → write canonicals to DB
3. **Structured logging**: JSON-formatted logs with per-file processing reports
4. **CLI entry point**: `python -m event_dedup.worker` or similar

### Docker Infrastructure
1. **Pipeline worker Dockerfile**: Python app with uv, watches directory
2. **API server Dockerfile**: FastAPI skeleton with health endpoint (routes filled in Phase 4)
3. **Frontend Dockerfile**: Nginx placeholder (React app built in Phase 4)
4. **docker-compose.yml**: Full stack with PostgreSQL, volumes, environment variables
5. **Alembic auto-migration**: Run migrations on container startup

### Gap Between Existing Code and Phase 3

The existing code has:
- File ingestion (single file at a time, called manually)
- Matching pipeline (pure function, takes event dicts)
- No connection between them (no code that ingests a file AND THEN runs matching)
- No file watching
- No canonical event DB write (synthesis returns dicts, doesn't persist)
- No structured logging
- No Docker anything

Phase 3 must bridge these gaps.

## Key Technical Decisions Needed

1. **File watcher library**: watchfiles (Rust-based, async) vs watchdog vs polling
2. **When to run matching**: After each file? After a batch? Configurable debounce?
3. **Canonical event persistence**: Write to DB after synthesis (new code needed)
4. **Structured logging format**: structlog vs python-json-logger vs stdlib
5. **Docker base image**: python:3.12-slim vs uv-based image
6. **Migration strategy**: Alembic upgrade on container startup

## Deferred to Later Phases

- API endpoints (Phase 4)
- React frontend (Phase 4)
- AI-assisted matching (Phase 5)
- Manual review workflows (Phase 6)

---
*Context captured: 2026-02-28*
*Ready for: research-phase or plan-phase*
