---
phase: 06-review-operations
plan: 01
subsystem: review-api
tags: [review, audit-log, dashboard, api, split, merge]
dependency_graph:
  requires: [models, canonical-synthesizer, api-framework]
  provides: [review-operations, audit-log-model, dashboard-api]
  affects: [frontend-review-ui]
tech_stack:
  added: []
  patterns: [transactional-operations, sql-delete-for-cascade, audit-logging]
key_files:
  created:
    - src/event_dedup/models/audit_log.py
    - config/alembic/versions/004_add_audit_log.py
    - src/event_dedup/canonical/helpers.py
    - src/event_dedup/review/__init__.py
    - src/event_dedup/review/operations.py
    - src/event_dedup/api/routes/review.py
    - src/event_dedup/api/routes/dashboard.py
    - tests/test_review_api.py
  modified:
    - src/event_dedup/models/__init__.py
    - src/event_dedup/api/schemas.py
    - src/event_dedup/api/app.py
decisions:
  - "Use SQL DELETE (not ORM session.delete) for canonical event deletion to avoid cascade conflicts with SQLAlchemy identity map"
  - "Separate audit_router at /api prefix for /api/audit-log endpoint (not nested under /api/review)"
  - "Added source event pdf-ddd-0-0 and CanonicalEventSource link for Stadtfest in test fixture for complete split-to-existing test coverage"
  - "Replaced datetime.utcnow() with datetime.now(dt.UTC) to fix deprecation warnings"
metrics:
  duration: 6m
  completed: 2026-02-28
  tasks: 2/2
  tests: 13 new + 11 existing = 24 total
  files_created: 8
  files_modified: 3
---

# Phase 6 Plan 01: Backend Review Operations Summary

AuditLog model with Alembic migration, transactional split/merge operations using synthesize_canonical for re-synthesis, review queue sorted by uncertainty, dismiss endpoint, audit log with filtering, and dashboard stats/processing-history APIs with 13 integration tests.

## Tasks Completed

### Task 1: AuditLog model, migration, helpers, and review operations service
**Commit:** a154e5f

- Created `AuditLog` model with action_type, canonical_event_id (FK with SET NULL), source_event_id, operator, details JSON, created_at
- Registered AuditLog in `models/__init__.py`
- Created Alembic migration 004: audit_log table with indexes on canonical_event_id and created_at, plus dashboard performance indexes on file_ingestions.ingested_at and match_decisions.decided_at
- Created `source_event_to_dict` helper extracting the 20+ field mapping from SourceEvent ORM to dict (matching synthesize_canonical input format)
- Created `update_canonical_from_dict` helper applying synthesized dict back to CanonicalEvent ORM (including first_date/last_date parsing)
- Implemented `split_source_from_canonical`: atomic transaction detaching source, re-synthesizing remaining sources, creating new canonical or assigning to existing, handling empty-canonical deletion and duplicate link detection
- Implemented `merge_canonical_events`: atomic transaction moving source links from donor to target, deleting donor, re-synthesizing target from all combined sources, handling duplicate source links

### Task 2: API routes, extended schemas, app registration, and tests
**Commit:** ff9fe09

- Extended schemas.py with 11 new Pydantic models: SplitRequest, MergeRequest, SplitResponse, MergeResponse, DismissRequest, AuditLogEntry, FileProcessingStats, MatchDistribution, CanonicalStats, DashboardStats, ProcessingHistoryEntry
- Created review routes: POST /api/review/split, POST /api/review/merge, GET /api/review/queue (paginated, sorted by needs_review desc then confidence asc), POST /api/review/queue/{id}/dismiss
- Created audit_router with GET /api/audit-log (paginated, filterable by canonical_event_id and action_type)
- Created dashboard routes: GET /api/dashboard/stats (file processing, match distribution, canonical summary), GET /api/dashboard/processing-history (daily time-series using SQLite-compatible sa.func.date)
- Registered review_router, audit_router, and dashboard_router in app.py
- Wrote 13 integration tests covering: split (new canonical, existing target, last source deletion, not found), merge (success, same-id rejection), review queue (returns low confidence, pagination), dismiss (clears flag, creates audit), audit log (records operations, filters by action_type), dashboard (stats structure, processing history)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed datetime.utcnow() deprecation**
- **Found during:** Task 2 (test warnings)
- **Issue:** `datetime.utcnow()` is deprecated in Python 3.12+
- **Fix:** Replaced with `datetime.now(dt.UTC)` in helpers.py and dashboard.py
- **Files modified:** src/event_dedup/canonical/helpers.py, src/event_dedup/api/routes/dashboard.py

**2. [Rule 1 - Bug] Used SQL DELETE instead of ORM session.delete for canonical deletion**
- **Found during:** Task 2 (test_split_last_source_deletes_canonical failing)
- **Issue:** SQLAlchemy ORM cascade on the `sources` relationship conflicts with explicit child deletion in split operation
- **Fix:** Replaced `session.delete(canonical)` with `sa.delete(CanonicalEvent).where(...)` for clean SQL-level deletion
- **Files modified:** src/event_dedup/review/operations.py

**3. [Rule 1 - Bug] SQLite ID reuse in split test**
- **Found during:** Task 2 (test assertions)
- **Issue:** SQLite reuses autoincrement IDs after deletion, so new canonical may get the same ID as deleted original
- **Fix:** Test verifies total count remains stable and new canonical has correct source_count instead of checking old ID returns 404
- **Files modified:** tests/test_review_api.py

**4. [Rule 2 - Missing functionality] Added source event and link for Stadtfest in test fixture**
- **Found during:** Task 2 (test_split_to_existing_canonical failing)
- **Issue:** Stadtfest canonical had source_count=1 but no actual CanonicalEventSource link, so split-to-existing couldn't verify source count increase
- **Fix:** Added pdf-ddd-0-0 source event with EventDate and CanonicalEventSource link for Stadtfest
- **Files modified:** tests/test_review_api.py

## Self-Check: PASSED

All 11 files verified present. Both commit hashes (a154e5f, ff9fe09) confirmed in git log. 24 tests pass (13 new + 11 existing).
