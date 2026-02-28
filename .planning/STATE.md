# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-28)

**Core value:** Accurate event deduplication -- the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.
**Current focus:** Milestone v0.2 — Configuration, AI Verification, UX & Export

## Current Position

Milestone: v0.2
Status: In progress — Phase 9 complete
Last activity: 2026-02-28 — Phase 9 executed (2 plans, 2 commits)

Progress: [████░░░░░░] 40%

## Phase Overview

| Phase | Title | Requirements | Status |
|-------|-------|-------------|--------|
| 8 | Dynamic Configuration System | CFG-01..05 | Complete |
| 9 | AI Matching Verification & Indicators | AIM-01..04 | Complete |
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
| 09 | 01 | ~4m | 2 | 6 |
| 09 | 02 | ~2m | 4 | 4 |

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

## Session Continuity

Last session: 2026-02-28
Stopped at: Phase 9 complete
Resume file: N/A
Next action: `/gsd:plan-phase 10` to plan Time Gap Penalty
