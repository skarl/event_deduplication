# Plan 07-02 Summary

**Phase:** 07 - Accuracy Refinement
**Plan:** 02 - Category-aware matching weights + category-specific evaluation
**Status:** COMPLETE
**Duration:** ~4m
**Requirements:** MTCH-08

## What Was Done

### Task 1: Category-aware weight config and pipeline resolution

- Added `CategoryWeightsConfig` model to `config.py` with `priority` list and `overrides` dict of `ScoringWeights`
- Added `category_weights` field to `MatchingConfig` (defaults to empty)
- Created `resolve_weights()` function in `pipeline.py`: selects weights based on shared categories with priority ordering
- Integrated `resolve_weights()` into `score_candidate_pairs()`: replaces direct `config.scoring` usage
- Added `category_weights` section to `config/matching.yaml`:
  - fasnacht: title=0.25, geo=0.30 (lower title weight for carnival events)
  - versammlung: title=0.40, geo=0.20 (higher title weight for political events)
- Extended `tests/test_matching_config.py` (4 new tests): default empty, YAML loading, real config, partial override
- Extended `tests/test_pipeline.py` (9 new tests): shared category, no shared, None categories, priority order, empty priority, integration

### Task 2: Category-specific F1 evaluation in harness

- Added `evaluate_category_subset()` function to `harness.py`: filters ground truth and predicted pairs by category, computes per-category metrics
- Extended `tests/test_harness.py` (7 new tests): filtering, false negatives, false positives, empty category, either-event inclusion, missing categories

## Decisions

- [07-02]: Weight resolution happens in pipeline (upstream), combiner is unchanged
- [07-02]: Category overrides only apply when both events share the category
- [07-02]: Priority list determines which override wins when multiple categories overlap
- [07-02]: Conservative weight adjustments: fasnacht title 0.30->0.25, versammlung title 0.30->0.40

## Verification

```
371 passed in 1.60s
```

All existing and new tests pass. Combiner tests completely unaffected.
