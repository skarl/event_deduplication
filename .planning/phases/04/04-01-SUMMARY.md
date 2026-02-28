# Plan 04-01 Summary: FastAPI REST API

**Status:** COMPLETE
**Duration:** ~8m
**Date:** 2026-02-28

## What Was Built

### API Endpoints
- `GET /health` — health check (moved to router)
- `GET /api/canonical-events` — paginated list with search/filter (q, city, date_from, date_to, category, page, size)
- `GET /api/canonical-events/{id}` — detail with source events, dates, and match decisions

### Files Created
- `src/event_dedup/api/schemas.py` — Pydantic response schemas (EventDateSchema, SourceEventDetail, MatchDecisionSchema, CanonicalEventSummary, CanonicalEventDetail, PaginatedResponse)
- `src/event_dedup/api/deps.py` — FastAPI dependency injection (get_db)
- `src/event_dedup/api/routes/__init__.py` — routes package
- `src/event_dedup/api/routes/health.py` — health endpoint router
- `src/event_dedup/api/routes/canonical_events.py` — canonical events API endpoints
- `config/alembic/versions/002_add_pg_trgm_and_date_columns.py` — Alembic migration for pg_trgm + first_date/last_date
- `tests/test_api.py` — 11 API endpoint tests

### Files Modified
- `src/event_dedup/api/app.py` — CORS middleware, router includes (replaced inline /health)
- `src/event_dedup/models/canonical_event.py` — Added first_date, last_date columns (sa.Date, indexed)
- `src/event_dedup/canonical/synthesizer.py` — Populates first_date/last_date from dates array
- `src/event_dedup/worker/persistence.py` — Persists first_date/last_date with _parse_date helper
- `tests/conftest.py` — Added api_client and seeded_db fixtures

## Key Decisions
- Used BeforeValidator for date/time to string coercion in EventDateSchema (ORM stores date/time objects)
- Built CanonicalEventDetail from column dict + manual source/match_decision construction (avoids ORM relationship conflict with Pydantic from_attributes)
- Category filtering uses ILIKE on cast(JSON, String) for SQLite+PG compatibility
- down_revision chains to a621d57eaaf3 (phase 2 migration)

## Verification
- 11/11 API tests pass
- 283/283 total tests pass (zero regressions)
- All routes registered: /health, /api/canonical-events, /api/canonical-events/{event_id}
