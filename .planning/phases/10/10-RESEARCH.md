# Phase 10: Time Gap Penalty & Venue Name Matching - Research

**Researched:** 2026-02-28
**Domain:** Date/time scoring penalty, venue name comparison in geo scoring
**Confidence:** HIGH

## Summary

Phase 10 reduces false-positive matches for sequential events by adding two mechanisms:

1. **Time Gap Penalty (TGP-01, TGP-02):** Events on the same date but 2+ hours apart receive a steeper time penalty. Currently, any time difference >90 minutes gets `far_factor=0.3`. Phase 10 adds a 4th tier: when the gap exceeds a configurable threshold (default 2 hours), a lower `time_gap_penalty_factor` (default 0.15) is applied instead. Both parameters are exposed in the dynamic config system.

2. **Venue Name Matching (new):** The geo scorer currently only compares coordinates. Since OCR-extracted events often have city-center coordinates rather than exact venue positions, two events in the same city always get geo_score ~1.0 — even at completely different venues. Phase 10 enhances the geo scorer to compare `location_name` when events are within close proximity, reducing the geo score when venue names clearly differ.

Both mechanisms work together: a concert at "Stadttheater" at 14:00 and a reading at "Kurhaus" at 18:00 in the same city currently score as a likely match. After Phase 10, the time gap penalty (2h+ apart → factor 0.15) AND venue mismatch (different names → factor 0.5) both reduce the score, making the "no_match" decision much more likely.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| TGP-01 | Time gap penalty: events 2h+ apart get steeper penalty (0.15 instead of 0.3) | `_time_proximity_factor()` in date_scorer.py line 64-83, DateConfig in config.py line 52-58 |
| TGP-02 | Time gap parameters configurable via dynamic config | Phase 8 config system auto-exposes new DateConfig fields via GET/PATCH API |
| NEW | Venue name matching in geo scorer when events are in close proximity | geo_scorer.py line 27-59, `location_name` field available on all events |
</phase_requirements>

## Current State

### 1. Date Scorer (`src/event_dedup/matching/scorers/date_scorer.py`)

**`_time_proximity_factor()` function (line 64-83):**
- Returns 1.0 if either time missing (benefit of the doubt)
- Returns 1.0 if diff ≤ time_tolerance_minutes (30 min)
- Returns close_factor (0.7) if diff ≤ time_close_minutes (90 min)
- Returns far_factor (0.3) otherwise

**Three-tier model:**
| Band | Time diff | Factor |
|------|-----------|--------|
| Exact | 0-30 min | 1.0 |
| Close | 30-90 min | 0.7 |
| Far | 90+ min | 0.3 |

**After Phase 10 (four-tier model):**
| Band | Time diff | Factor |
|------|-----------|--------|
| Exact | 0-30 min | 1.0 |
| Close | 30-90 min | 0.7 |
| Far | 90-120 min | 0.3 |
| Gap | 120+ min | 0.15 |

### 2. DateConfig (`src/event_dedup/matching/config.py`, line 52-58)

```python
class DateConfig(BaseModel):
    time_tolerance_minutes: int = 30
    time_close_minutes: int = 90
    close_factor: float = 0.7
    far_factor: float = 0.3
```

**New fields needed:**
- `time_gap_penalty_hours: float = 2.0` — threshold in hours
- `time_gap_penalty_factor: float = 0.15` — factor when gap exceeds threshold

### 3. Geo Scorer (`src/event_dedup/matching/scorers/geo_scorer.py`)

Currently only uses coordinates + confidence:
- Returns neutral_score (0.5) when coordinates missing or low confidence
- Returns `max(0, 1 - distance_km / max_distance_km)` otherwise
- Does NOT look at `location_name` at all

**Problem:** OCR-extracted events often have city-center coordinates rather than exact venue positions. Two events at "Stadttheater Freiburg" and "Konzerthaus Freiburg" both get coordinates ~48.0, 7.85 → geo_score ≈ 1.0.

**Solution:** When distance is small (< 1km, meaning "same area"), compare venue names via fuzzy matching. If names clearly differ, reduce the geo score.

### 4. GeoConfig (`src/event_dedup/matching/config.py`, line 44-49)

```python
class GeoConfig(BaseModel):
    max_distance_km: float = 10.0
    min_confidence: float = 0.85
    neutral_score: float = 0.5
```

**New fields needed:**
- `venue_match_distance_km: float = 1.0` — only compare venue names when distance < this threshold
- `venue_mismatch_factor: float = 0.5` — multiply geo score by this when venue names clearly differ

### 5. Existing Tests

**Date scorer tests (`tests/test_scorers.py`, line 13-85):**
- `test_time_far_match`: Uses 240 min (4h) gap, expects 0.3. After Phase 10, this should return 0.15 (4h > 2h threshold).
- Need to update this test and add new tests for the 4th tier boundary.

**Geo scorer tests (`tests/test_scorers.py`, line 91-142):**
- Test coordinate-based scoring only. Need new tests for venue name matching.

**Config tests (`tests/test_matching_config.py`, line 78-83):**
- `test_default_date`: Asserts 4 fields. Need to add assertions for the 2 new fields.

### 6. Frontend

**TypeScript types (`frontend/src/types/index.ts`, line 198-203):**
```typescript
export interface DateConfig {
  time_tolerance_minutes: number;
  time_close_minutes: number;
  close_factor: number;
  far_factor: number;
}

export interface GeoConfig {
  max_distance_km: number;
  min_confidence: number;
  neutral_score: number;
}
```

Both need the new fields added.

**ConfigPage.tsx:** DateTimeSection (line 201-249) renders 4 fields for DateConfig. GeoSection (line 252-294) renders 3 fields for GeoConfig. Both need the new fields added.

### 7. Config API & YAML

The Phase 8 dynamic config system automatically exposes all Pydantic model fields. Adding new fields to DateConfig and GeoConfig:
- GET /api/config → includes new fields with defaults
- PATCH /api/config → supports partial updates of new fields
- Deep merge preserves existing values

`config/matching.yaml` should document the new fields.

## Key Integration Points

### Time Gap Penalty Data Flow

```
1. DateConfig gains time_gap_penalty_hours and time_gap_penalty_factor
2. _time_proximity_factor() checks: if diff > threshold_hours * 60 → return penalty_factor
3. Config auto-exposed via Phase 8 REST API
4. Frontend renders new fields in DateTimeSection
```

### Venue Name Matching Data Flow

```
1. GeoConfig gains venue_match_distance_km and venue_mismatch_factor
2. geo_score() after computing distance: if distance < venue_match_distance_km,
   compare location_name with RapidFuzz
3. If venue names clearly differ (ratio < 0.5), multiply score by venue_mismatch_factor
4. Config auto-exposed via Phase 8 REST API
5. Frontend renders new fields in GeoSection
```

## Architecture Patterns

### Pattern: Adding a 4th Time Tier

Extend `_time_proximity_factor()` with one additional check before the final return:

```python
def _time_proximity_factor(time_a, time_b, config: DateConfig) -> float:
    if not time_a or not time_b:
        return 1.0
    # ... parse times, compute diff_minutes ...
    if diff_minutes <= config.time_tolerance_minutes:
        return 1.0
    if diff_minutes <= config.time_close_minutes:
        return config.close_factor
    if diff_minutes <= config.time_gap_penalty_hours * 60:  # NEW
        return config.far_factor
    return config.time_gap_penalty_factor  # NEW
```

### Pattern: Venue Name Factor in Geo Scorer

```python
from rapidfuzz import fuzz

def _venue_name_factor(name_a: str | None, name_b: str | None, config: GeoConfig) -> float:
    """Compare venue names. Returns 1.0 for match/missing, lower for mismatch."""
    if not name_a or not name_b:
        return 1.0  # Benefit of the doubt
    ratio = fuzz.token_sort_ratio(name_a.lower(), name_b.lower()) / 100.0
    if ratio >= 0.5:
        return 1.0  # Same or similar venue
    return config.venue_mismatch_factor  # Different venue
```

Then in `geo_score()`:
```python
score = max(0.0, 1.0 - dist / config.max_distance_km)
if dist < config.venue_match_distance_km:
    venue_f = _venue_name_factor(
        event_a.get("location_name"), event_b.get("location_name"), config
    )
    score *= venue_f
return score
```

### Anti-Patterns to Avoid

- **Comparing venue names at all distances:** Only relevant when events are in the same area. At 5km+ apart, different venues are expected and coordinates alone are sufficient.
- **Using venue match as a standalone score signal:** This would add a 5th signal and change the scoring architecture. Better to integrate it into the existing geo scorer.
- **Penalizing missing venue names:** Many events lack location_name. Must return 1.0 (benefit of doubt) when either name is missing.

## Common Pitfalls

### Pitfall 1: Breaking Existing test_time_far_match

**What goes wrong:** The existing `test_time_far_match` test uses a 4-hour gap and expects 0.3 (far_factor). With the new 4th tier, 4 hours > 2 hours → it should now return 0.15.
**How to avoid:** Update the test expectation from 0.3 to 0.15, and add a new test for the 90-120 minute range that still expects 0.3.

### Pitfall 2: RapidFuzz Import in Geo Scorer

**What goes wrong:** Geo scorer currently has no RapidFuzz dependency. Adding it could break if not imported correctly.
**Why it happens:** Only title_scorer currently imports RapidFuzz.
**How to avoid:** RapidFuzz is already a project dependency (used by title_scorer). Just add the import.

### Pitfall 3: Venue Factor When Distance is 0

**What goes wrong:** When coordinates are identical (distance = 0), the base score is 1.0. If venue names are very different, the score drops to 0.5 — which might seem counter-intuitive when coordinates match exactly.
**How to avoid:** This is actually correct behavior. Identical coordinates with different venue names means the coordinates are imprecise (city-center fallback). The venue name mismatch is a valuable signal.

## Test Strategy

### Time Gap Penalty Tests
1. **Update test_time_far_match:** 4h gap now returns 0.15 instead of 0.3
2. **New: test_time_gap_boundary_below:** 119 min gap → returns far_factor (0.3)
3. **New: test_time_gap_boundary_at:** 120 min gap → returns time_gap_penalty_factor (0.15)
4. **New: test_time_gap_custom_threshold:** Custom 3h threshold, 150 min gap → still far_factor

### Venue Name Matching Tests
1. **New: test_same_venue_name:** Same coordinates, same location_name → 1.0
2. **New: test_different_venue_name_close:** Same coordinates, different names → 0.5
3. **New: test_venue_name_missing:** Same coordinates, one name missing → 1.0
4. **New: test_venue_name_far_distance:** Different coordinates (>1km), different names → distance-only score (no venue penalty)
5. **New: test_similar_venue_name:** Same coordinates, similar names (ratio > 0.5) → 1.0

### Config Tests
1. **Update test_default_date:** Add assertions for time_gap_penalty_hours and time_gap_penalty_factor
2. **Update test_default_geo:** Add assertions for venue_match_distance_km and venue_mismatch_factor

## Sources

### Primary (HIGH confidence)
- Direct code inspection of date_scorer.py, geo_scorer.py, config.py
- Test files: test_scorers.py, test_matching_config.py
- Frontend: ConfigPage.tsx, types/index.ts

### Code File References
| File | Key Lines | Purpose |
|------|-----------|---------|
| `src/event_dedup/matching/scorers/date_scorer.py` | 64-83 | _time_proximity_factor to extend |
| `src/event_dedup/matching/scorers/geo_scorer.py` | 27-59 | geo_score to extend |
| `src/event_dedup/matching/config.py` | 44-58 | GeoConfig + DateConfig to extend |
| `tests/test_scorers.py` | 13-85, 91-142 | Existing tests to update |
| `tests/test_matching_config.py` | 78-83 | Config default tests to update |
| `config/matching.yaml` | 27-31 | YAML config to update |
| `frontend/src/types/index.ts` | 192-203 | TypeScript types to update |
| `frontend/src/components/ConfigPage.tsx` | 201-294 | Config sections to update |

## Metadata

**Confidence breakdown:**
- Time gap penalty: HIGH — Straightforward extension of existing tier system
- Venue name matching: HIGH — RapidFuzz already available, clean integration point
- Config integration: HIGH — Phase 8 auto-exposes new Pydantic fields
- Test strategy: HIGH — Clear existing patterns to follow

**Research date:** 2026-02-28
**Valid until:** Indefinite (internal codebase)
