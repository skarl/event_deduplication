# Roadmap: Event Deduplication Service

## Completed Milestones

- [x] **v0.1** (2026-02-27 to 2026-02-28) -- Full event deduplication service: 7 phases, 18 plans, 39 requirements, 371 tests. [Details](milestones/v0.1-ROADMAP.md) | [Requirements](milestones/v0.1-REQUIREMENTS.md)

## Current Milestone: v0.2 — Configuration, AI Verification, UX & Export

**Requirements:** [REQUIREMENTS.md](REQUIREMENTS.md) (19 requirements)

### Phase 8: Dynamic Configuration System
**Goal:** All matching parameters editable via frontend with immediate effect on next pipeline run
**Requirements:** CFG-01, CFG-02, CFG-03, CFG-04, CFG-05
**Rationale:** Foundation phase — the config system is needed by AI matching (API key, on/off toggle) and time gap penalty (configurable parameters). Must come first.
**Plans:** 2 plans

Plans:
- [x] 08-01-PLAN.md — Backend: DB model, migration, encryption, API endpoints, worker config loading, tests
- [x] 08-02-PLAN.md — Frontend: config page with grouped sections, API key management, AI toggle

**Scope:**
- Database-backed config model (replaces YAML-only config)
- REST API endpoints: GET config, PATCH config (partial updates)
- Gemini API key: stored encrypted/hashed, write-only in API (never returned in GET)
- Frontend config page: grouped sections (Scoring, Thresholds, Date/Time, Geo, AI, Cluster)
- Worker loads config from DB at pipeline start (falls back to YAML defaults if no DB config)

### Phase 9: AI Matching Verification & Indicators
**Goal:** AI matching is verified end-to-end and its involvement is visible throughout the system
**Requirements:** AIM-01, AIM-02, AIM-03, AIM-04
**Depends on:** Phase 8 (API key + on/off toggle in config)
**Plans:** 2 plans

Plans:
- [x] 09-01-PLAN.md — Backend: DB migration, model, pipeline computation, persistence, API schema, integration test
- [x] 09-02-PLAN.md — Frontend: TypeScript types, AI badge in event list/detail, ConfidenceIndicator tier styling

**Scope:**
- Integration test: process test events through full pipeline with AI enabled (mock or real Gemini)
- New `ai_assisted` boolean field on CanonicalEvent model + migration
- Pipeline sets `ai_assisted=True` when any cluster pair has `tier="ai"`
- Frontend: AI badge in event list, AI detail in ConfidenceIndicator, tier-based styling

### Phase 10: Time Gap Penalty & Venue Name Matching
**Goal:** Sequential events at the same location 2h+ apart are no longer falsely matched; events at different venues in the same city are correctly distinguished
**Requirements:** TGP-01, TGP-02
**Depends on:** Phase 8 (penalty factor in config)
**Plans:** 2 plans

Plans:
- [x] 10-01-PLAN.md — Backend: DateConfig + time gap penalty, GeoConfig + venue name matching, tests
- [x] 10-02-PLAN.md — Frontend: TypeScript types, DateTimeSection + GeoSection config fields

**Scope:**
- Add 4th time proximity tier: 2h+ gaps get `time_gap_penalty_factor` (0.15) instead of `far_factor` (0.3)
- Add configurable `time_gap_penalty_hours` (default 2.0) and `time_gap_penalty_factor` (default 0.15) to DateConfig
- Add venue name fuzzy matching in geo scorer when events are in close proximity (<1km)
- Add configurable `venue_match_distance_km` (default 1.0) and `venue_mismatch_factor` (default 0.5) to GeoConfig
- All parameters exposed in dynamic config (Phase 8)
- Update existing tests, add new test cases for time gap and venue matching scenarios

### Phase 11: Frontend UX Improvements
**Goal:** Event browsing is faster and more flexible with filter chips, sorting, and page sizing
**Requirements:** UIX-01, UIX-02, UIX-03, UIX-04
**Depends on:** Phase 9 (AI indicator column in list)

**Scope:**
- API endpoints: GET distinct categories, GET distinct cities (for autocomplete)
- Category chip selector: autocomplete dropdown, selected chips with "x" remove, multi-select
- City chip selector: same UX pattern as categories
- Column sorting: clickable headers with sort direction indicator, backend `sort_by` + `sort_dir` params
- Page size selector: 25 / 50 / 100 / 200 / ALL options, persisted in URL params

### Phase 12: Export Function
**Goal:** Operators can export canonical events as JSON files matching the input format
**Requirements:** EXP-01, EXP-02, EXP-03, EXP-04, EXP-05

**Scope:**
- Core export logic as shared module (used by both API and CLI)
- API endpoint: POST /api/export with optional `created_after`, `modified_after` datetime filters
- CLI command: `uv run python -m event_dedup.cli export --created-after ... --modified-after ... --output-dir ./export/`
- Transforms canonical events to input-format JSON (title, description, dates, location with geo, categories, flags)
- Splits output into chunks of max 200 events: `export_{timestamp}_part_{N}.json`
- API returns ZIP archive if multiple files, single JSON if ≤200 events
- CLI writes files directly to output directory
- Frontend: Export page/dialog with datetime pickers and download button

---

### Phase Summary

| Phase | Title | Requirements | Depends On |
|-------|-------|-------------|------------|
| 8 | Dynamic Configuration System | CFG-01..05 (5) | — |
| 9 | AI Matching Verification & Indicators | AIM-01..04 (4) | Phase 8 |
| 10 | Time Gap Penalty | TGP-01..02 (2) | Phase 8 |
| 11 | Frontend UX Improvements | UIX-01..04 (4) | Phase 9 |
| 12 | Export Function | EXP-01..05 (5) | — |

**Total: 5 phases, 20 requirements**

### Requirement Coverage

All 19 requirements mapped to exactly one phase:

| Requirement | Phase |
|-------------|-------|
| CFG-01..05 | 8 |
| AIM-01..04 | 9 |
| TGP-01..02 | 10 |
| UIX-01..04 | 11 |
| EXP-01..05 | 12 |
