---
phase: "02"
plan: "01"
subsystem: "matching-foundation"
tags: [models, scoring, config, matching]
dependency-graph:
  requires: [01-01, 01-02, 01-03]
  provides: [matching-config, signal-scorers, combiner, phase2-models]
  affects: [02-02, 02-03, 02-04]
tech-stack:
  added: [networkx]
  patterns: [pure-function-scorers, pydantic-config, haversine, jaccard, rapidfuzz-blending]
key-files:
  created:
    - src/event_dedup/models/canonical_event.py
    - src/event_dedup/models/canonical_event_source.py
    - src/event_dedup/models/match_decision.py
    - src/event_dedup/matching/__init__.py
    - src/event_dedup/matching/config.py
    - src/event_dedup/matching/combiner.py
    - src/event_dedup/matching/scorers/__init__.py
    - src/event_dedup/matching/scorers/date_scorer.py
    - src/event_dedup/matching/scorers/geo_scorer.py
    - src/event_dedup/matching/scorers/title_scorer.py
    - src/event_dedup/matching/scorers/desc_scorer.py
    - config/matching.yaml
    - tests/test_matching_config.py
    - tests/test_scorers.py
    - tests/test_combiner.py
    - config/alembic/versions/a621d57eaaf3_add_phase_2_tables.py
  modified:
    - pyproject.toml
    - uv.lock
    - src/event_dedup/models/__init__.py
decisions:
  - "Scorers are pure functions taking dict args for testability and decoupling from ORM"
  - "Geo scorer returns neutral 0.5 for missing/low-confidence coordinates"
  - "Date scorer uses Jaccard overlap with time proximity multiplier"
  - "Title scorer blends token_set_ratio only in the ambiguous 0.40-0.80 range"
  - "Description scorer returns 0.5 when both missing, 0.4 when one missing"
  - "CanonicalEvent stores merged field values with JSON provenance tracking"
  - "MatchDecision uses canonical ordering constraint (id_a < id_b) matching GroundTruthPair pattern"
metrics:
  duration: "~5 minutes"
  completed: "2026-02-28"
  tasks: 14
  tests-added: 65
  tests-total: 159
---

# Phase 2 Plan 1: Foundation Layer -- Models, Config, Scorers, Combiner

Four signal scorers (date, geo, title, description) with weighted combiner and threshold-based decision logic, backed by Pydantic config with YAML loading and three new database models for the matching pipeline.

## What Was Built

### Database Models (3 new tables)

1. **CanonicalEvent** -- The deduplicated merged event representation with all content fields, provenance tracking (which source contributed each field), quality metadata (match_confidence, needs_review, version), and a one-to-many relationship to CanonicalEventSource.

2. **CanonicalEventSource** -- Join table linking canonical events to their contributing source events with timestamps. Unique constraint prevents duplicate links.

3. **MatchDecision** -- Records pairwise comparison results with all four signal scores, combined score, decision (match/no_match/ambiguous), and tier. Uses canonical ordering constraint matching the GroundTruthPair pattern.

### Matching Configuration

- **MatchingConfig** Pydantic BaseModel with 7 nested sub-configs: ScoringWeights, ThresholdConfig, GeoConfig, DateConfig, TitleConfig, ClusterConfig, CanonicalConfig (with FieldStrategies)
- **load_matching_config()** loads from YAML with graceful fallback to defaults
- **config/matching.yaml** ships all parameters with documentation comments

### Signal Scorers (4 pure functions)

All scorers take `(event_a: dict, event_b: dict, config=None) -> float` and return values in [0, 1]:

1. **date_score** -- Expands date ranges, computes Jaccard set overlap, multiplied by time proximity factor (exact match within tolerance=1.0, close=0.7, far=0.3, missing=1.0)
2. **geo_score** -- Haversine distance normalized by max_distance_km. Returns neutral 0.5 for missing coords or low confidence (<0.85)
3. **title_score** -- RapidFuzz token_sort_ratio as primary, blends token_set_ratio only in ambiguous range [0.40, 0.80]
4. **description_score** -- RapidFuzz token_sort_ratio with graceful missing-data handling (both missing=0.5, one missing=0.4)

### Score Combiner

- **SignalScores** frozen dataclass holding the four signal values
- **combined_score()** computes normalized weighted average
- **decide()** applies threshold-based classification: >= 0.75 match, <= 0.35 no_match, else ambiguous

### Tests

65 new tests covering all components:
- 16 config tests (loading, defaults, partial override, validation)
- 35 scorer tests (normal, edge, missing data, custom configs)
- 14 combiner tests (weighted average, normalization, decision boundaries)

All 159 project tests pass with no regressions.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `166690a` | chore | Add networkx dependency |
| `fdcd317` | feat | Add Phase 2 database models |
| `5b28378` | chore | Add Alembic migration for Phase 2 tables |
| `8cecd9d` | feat | Add matching config with YAML loading and tests |
| `d902d66` | feat | Implement four matching signal scorers |
| `7ff80d4` | feat | Add score combiner and decision logic |
| `e7a0f16` | test | Add tests for scorers and combiner |

## Deviations from Plan

None -- plan executed exactly as written.

## Self-Check: PASSED

- All 16 created files verified on disk
- All 7 commit hashes verified in git log
- All 159 tests passing (65 new + 94 existing)
