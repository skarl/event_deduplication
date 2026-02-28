# Phase 10 UAT: Time Gap Penalty & Venue Name Matching

**Date:** 2026-02-28
**Result:** PASS (6/6)

## Test Results

| # | Test | Requirement | Result |
|---|------|-------------|--------|
| 1 | Time gap penalty — 4h gap → score 0.15 (was 0.3) | TGP-01 | PASS |
| 2 | Time gap boundary — 119min → 0.3 (far), 121min → 0.15 (gap) | TGP-01 | PASS |
| 3 | Venue name mismatch — same coords, different names → geo score 0.5 | NEW | PASS |
| 4 | Missing venue names — benefit of the doubt (score 1.0) | NEW | PASS |
| 5 | Config API — 4 new fields in serialized config | TGP-02 | PASS |
| 6 | Frontend — TS types compile, ConfigPage has 4 new NumberField inputs | TGP-02 | PASS |

## Test Details

### Test 1: Time Gap Penalty
Events on same date, 4 hours apart. Date scorer returns 0.15 (`time_gap_penalty_factor`) instead of the old 0.3 (`far_factor`). Verified via `date_score()` call.

### Test 2: Time Gap Boundary
119 minutes apart → far_factor (0.3). 121 minutes apart → time_gap_penalty_factor (0.15). The 4-tier model transitions correctly at the 2-hour boundary.

### Test 3: Venue Name Mismatch
Same coordinates (48.0, 7.8), "Stadttheater" vs "Konzerthaus" → geo score 0.5 (base 1.0 × venue_mismatch_factor 0.5). Same venue name → geo score 1.0 (no penalty).

### Test 4: Missing Venue Names
One name missing → 1.0. Both missing → 1.0. Far apart events (>1km) with different names → venue check skipped, distance-only score used.

### Test 5: Config API
`MatchingConfig().model_dump()` includes `time_gap_penalty_hours` (2.0), `time_gap_penalty_factor` (0.15), `venue_match_distance_km` (1.0), `venue_mismatch_factor` (0.5).

### Test 6: Frontend
`npx tsc --noEmit` passes. Types in `index.ts` and NumberField inputs in `ConfigPage.tsx` confirmed for all 4 new fields.

## Automated Tests

73/73 scorer and config tests pass (`uv run pytest tests/test_scorers.py tests/test_matching_config.py -v`).
