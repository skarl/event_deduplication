# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** Accurate event deduplication -- the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.
**Current focus:** Milestone v0.2 — Configuration, AI Verification, UX & Export

## Current Position

Milestone: v0.2
Status: In progress — Phase 8 complete (2/2 plans), awaiting verification checkpoint
Last activity: 2026-02-28 — Phase 8 Plan 2 (frontend config UI) completed

Progress: [██░░░░░░░░] 20%
Current Phase: 8
Current Plan: 2 (checkpoint pending)

## Phase Overview

| Phase | Title | Requirements | Status |
|-------|-------|-------------|--------|
| 8 | Dynamic Configuration System | CFG-01..05 | In Progress (2/2 plans, checkpoint pending) |
| 9 | AI Matching Verification & Indicators | AIM-01..04 | Pending |
| 10 | Time Gap Penalty | TGP-01..02 | Pending |
| 11 | Frontend UX Improvements | UIX-01..04 | Pending |
| 12 | Export Function | EXP-01..04 | Pending |

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

## Session Continuity

Last session: 2026-02-28
Stopped at: Completed 08-02-PLAN.md (awaiting human-verify checkpoint)
Resume file: N/A
Next action: Verify config page at http://localhost:5173/config, then proceed to Phase 9
