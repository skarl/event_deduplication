# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** Accurate event deduplication -- the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.
**Current focus:** Between milestones — v0.2 archived, v0.3 not yet started

## Current Position

Milestone: v0.2
Status: ARCHIVED — 20/20 requirements verified, 445 tests pass, milestone archived
Last activity: 2026-02-28 — Milestone archived, git tagged v0.2

Progress: [██████████] 100%

## Phase Overview

| Phase | Title | Requirements | Status |
|-------|-------|-------------|--------|
| 8 | Dynamic Configuration System | CFG-01..05 | Complete |
| 9 | AI Matching Verification & Indicators | AIM-01..04 | Complete |
| 10 | Time Gap Penalty & Venue Matching | TGP-01..02 | Complete |
| 11 | Frontend UX Improvements | UIX-01..04 | Complete |
| 12 | Export Function | EXP-01..05 | Complete |

## Performance Metrics

**Velocity (v0.1):**
- Total plans completed: 18
- Average duration: 4.1m
- Total execution time: ~1.25 hours

**v0.2:**

| Phase | Plan | Duration | Tasks | Files |
|-------|------|----------|-------|-------|
| 08 | 01 | 5m 24s | 2 | 16 |
| 08 | 02 | 2m 56s | 2 | 5 |
| 09 | 01 | ~4m | 2 | 6 |
| 09 | 02 | ~2m | 4 | 4 |
| 10 | 01 | ~3m | 2 | 6 |
| 10 | 02 | ~1m | 3 | 2 |
| 11 | 01 | ~2m | 2 | 2 |
| 11 | 02 | ~3m | 2 | 8 |
| 12 | 01 | ~3m 31s | 2 | 6 |
| 12 | 02 | ~2m 45s | 2 | 7 |

## Accumulated Context

### Ground Truth Dataset

Generated: 1181 labeled pairs (248 same, 933 different, 157 ambiguous skipped)
Database: ground_truth.db (SQLite, loadable by evaluation harness)
Regenerate: `uv run python scripts/generate_ground_truth.py`

### Pending Todos

None.

### Blockers/Concerns

None.

## Decisions

- Singleton row (id=1) for config_settings -- simple, no multi-tenant complexity
- Fernet encryption with plain-text fallback for dev convenience
- Per-run config loading from DB with YAML fallback for backward compat
- Deep merge for partial PATCH updates to preserve unset fields
- HTML details/summary for collapsible config sections (native, no extra deps)
- Per-section save with TanStack Query mutation for granular updates
- Write-only API key with clear button for secure key management
- ai_assisted computed in pipeline (not synthesizer or API route) to avoid N+1 queries
- tier.startswith("ai") to catch all AI tier variants
- TierBadge component with purple/orange/gray color coding
- 4-tier time proximity model: exact/close/far/gap penalty (was 3-tier)
- Venue name matching only within close proximity (<1km) to avoid penalizing distant events
- RapidFuzz token_sort_ratio >= 0.5 threshold for venue similarity
- Multi-value city filter with OR semantics, multi-value category filter with AND semantics
- ChipSelector as controlled component, no component library needed
- size=0 in UI maps to size=10000 for API (ALL sentinel)
- nullslast for desc sort, nullsfirst for asc sort on nullable columns
- Omit canonical event ID from export to match input format
- Export-specific metadata (exportedAt, eventCount, part, totalParts, filters) rather than mirroring input metadata
- POST for export endpoint (body parameters, matches roadmap)
- Assume UTC for naive datetime inputs in export filters
- Separate run_export from main() for CLI testability via monkeypatch
- Native datetime-local inputs for frontend export (no extra library)
- Blob download via URL.createObjectURL for frontend file save
- Title veto threshold (0.30) to prevent auto-merge when titles clearly differ (cinema/venue scenario)

## Session Continuity

Last session: 2026-02-28
Stopped at: Milestone v0.2 archived
Resume file: N/A
Next action: Start v0.3 with `/gsd:new-milestone`
