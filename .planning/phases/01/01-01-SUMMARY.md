---
phase: 01-foundation
plan: 01
subsystem: ingestion
tags: [scaffolding, database, ingestion, idempotency]
dependency_graph:
  requires: []
  provides: [SourceEvent, EventDate, FileIngestion, FileProcessor, json_loader]
  affects: [01-02, 01-03]
tech_stack:
  added: [sqlalchemy, asyncpg, alembic, pydantic, pydantic-settings, rapidfuzz, aiosqlite, greenlet]
  patterns: [src-layout, async-sessionmaker, declarative-base, pydantic-validation]
key_files:
  created:
    - pyproject.toml
    - src/event_dedup/models/base.py
    - src/event_dedup/models/source_event.py
    - src/event_dedup/models/event_date.py
    - src/event_dedup/models/file_ingestion.py
    - src/event_dedup/db/engine.py
    - src/event_dedup/db/session.py
    - src/event_dedup/config/settings.py
    - src/event_dedup/ingestion/json_loader.py
    - src/event_dedup/ingestion/file_processor.py
    - config/alembic.ini
    - config/alembic/env.py
    - config/alembic/script.py.mako
    - config/alembic/versions/045202897e89_initial_schema.py
    - tests/conftest.py
    - tests/test_json_loader.py
    - tests/test_file_processor.py
  modified: []
decisions:
  - Use JSON type instead of JSONB/ARRAY for SQLite test compatibility
  - Use sa.text("CURRENT_TIMESTAMP") for server defaults (PG + SQLite compatible)
  - Use hatchling build backend with src layout
  - Added sqlalchemy[asyncio] extra to pull in greenlet dependency
  - Alembic env.py supports ALEMBIC_DATABASE_URL env override for migration generation without PG
metrics:
  duration: 5m
  completed: 2026-02-27
  tasks_completed: 2
  tasks_total: 2
  tests_total: 14
  tests_passing: 14
  files_created: 30
---

# Phase 1 Plan 1: Project Scaffolding, Database Models, and JSON Ingestion Summary

SQLAlchemy models for source_events/event_dates/file_ingestions with Pydantic-validated JSON ingestion, SHA-256 idempotency, and transactional safety using aiosqlite for tests.

## Tasks Completed

### Task 1: Project scaffolding, database models, and Alembic migration
- **Commit:** ed9f8cc
- Created pyproject.toml with uv project config and all Phase 1 dependencies
- Defined three SQLAlchemy models: SourceEvent (30+ columns), EventDate (composite index), FileIngestion (unique hash)
- Set up async engine, session factory, and Pydantic settings with env prefix
- Generated Alembic initial migration (all three tables)
- Created package structure for all future modules (models, db, config, ingestion, preprocessing, evaluation, ground_truth)

### Task 2: JSON loader and file processor with idempotency
- **Commit:** e7ba39d
- Created Pydantic models for JSON validation (GeoData, SanitizeResult, LocationData, EventData, etc.)
- Implemented load_event_file, compute_file_hash, extract_source_code utilities
- Built FileProcessor class with full idempotency (SHA-256 hash check), single-transaction writes, and dead letter handling
- City resolution uses _sanitizeResult.city as authoritative source per CONTEXT.md
- 14 tests passing (8 loader + 6 processor) using SQLite in-memory -- no PostgreSQL required

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed hatchling build backend reference**
- **Found during:** Task 1
- **Issue:** `build-backend = "hatchling.backends"` should be `"hatchling.build"`
- **Fix:** Corrected the build-backend string in pyproject.toml
- **Files modified:** pyproject.toml

**2. [Rule 3 - Blocking] Added greenlet dependency for async SQLAlchemy**
- **Found during:** Task 2
- **Issue:** SQLAlchemy async engine requires greenlet library, not installed by default
- **Fix:** Changed `sqlalchemy>=2.0` to `sqlalchemy[asyncio]>=2.0` in pyproject.toml
- **Files modified:** pyproject.toml, uv.lock

## Verification Results

1. All models import OK: `from event_dedup.models import Base, SourceEvent, EventDate, FileIngestion` -- PASS
2. All 14 tests pass: `uv run pytest tests/ -x -v` -- PASS
3. Alembic migration exists: `config/alembic/versions/045202897e89_initial_schema.py` -- PASS
4. All package directories exist under src/event_dedup/ -- PASS

## Self-Check: PASSED

All 17 key files verified present. Both task commits (ed9f8cc, e7ba39d) verified in git history.
