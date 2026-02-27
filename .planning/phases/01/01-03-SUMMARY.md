---
phase: "01"
plan: "03"
subsystem: "ground-truth-evaluation"
tags: [ground-truth, candidate-generation, evaluation, metrics, labeling]
dependency-graph:
  requires: [01-01, 01-02]
  provides: [ground-truth-model, candidate-generator, evaluation-harness, labeling-tool]
  affects: [02-01, 02-02, 03-01]
tech-stack:
  added: [rapidfuzz.fuzz.token_sort_ratio]
  patterns: [pure-function-extraction, blocking-based-pairing, canonical-pair-ordering]
key-files:
  created:
    - src/event_dedup/models/ground_truth.py
    - src/event_dedup/ground_truth/candidate_generator.py
    - src/event_dedup/ground_truth/labeling_tool.py
    - src/event_dedup/evaluation/metrics.py
    - src/event_dedup/evaluation/harness.py
    - config/alembic/versions/fb9dbc7f41c6_add_ground_truth_pairs_table.py
    - tests/test_candidate_generator.py
    - tests/test_metrics.py
    - tests/test_harness.py
  modified:
    - src/event_dedup/models/__init__.py
decisions:
  - "Hard negative sampling skips when ratio=0.0 (no forced minimum of 1)"
  - "Evaluation harness uses pure function extraction for all blocking/pairing logic"
  - "Check constraints use SQLAlchemy CheckConstraint for SQLite+PG compatibility"
metrics:
  duration: "6m"
  completed: "2026-02-27"
  tasks: 2
  tests-added: 23
  tests-total: 80
---

# Phase 1 Plan 3: Ground Truth and Evaluation Summary

Ground truth candidate generator with blocking-based cross-source pairing, interactive CLI labeling tool, and evaluation harness with custom P/R/F1 metrics and threshold sweep

## What Was Built

### Task 1: Ground Truth Model, Candidate Generator, and Labeling Tool

**GroundTruthPair Model** (`src/event_dedup/models/ground_truth.py`):
- SQLAlchemy model with foreign keys to source_events
- Check constraints: canonical ordering (event_id_a < event_id_b), valid label (same/different)
- Unique constraint on (event_id_a, event_id_b)
- Alembic migration generated and verified

**Candidate Generator** (`src/event_dedup/ground_truth/candidate_generator.py`):
- Pure function `generate_candidates_from_events()` for testability
- Blocking-index-based grouping using dc| and dg| keys
- Cross-source-only pairing (same source never paired)
- Title similarity via `rapidfuzz.fuzz.token_sort_ratio`
- Configurable hard negative sampling with seeded reproducibility
- Async `generate_candidates()` wrapper for DB queries

**Labeling Tool** (`src/event_dedup/ground_truth/labeling_tool.py`):
- Interactive CLI with side-by-side event comparison
- Auto-suggest "same" for high-similarity pairs (configurable threshold)
- Skip already-labeled pairs
- Input: s=same, d=different, k=skip, q=quit, n=add note
- `get_labeling_stats()` for session statistics

**Tests** (8 tests in `tests/test_candidate_generator.py`):
- Cross-source pairs only, title similarity filtering, pair deduplication
- Canonical ID ordering, geo blocking candidates, hard negative sampling + reproducibility

### Task 2: Evaluation Harness with Metrics

**Metrics** (`src/event_dedup/evaluation/metrics.py`):
- Custom `compute_metrics()` -- no sklearn dependency
- Precision, Recall, F1 with canonical pair normalization
- `format_metrics()` for terminal display
- Handles edge cases: empty ground truth, empty predictions, all-FP, all-FN

**Harness** (`src/event_dedup/evaluation/harness.py`):
- Pure function `generate_predictions_from_events()` for testability
- `load_ground_truth()` separates same/different labels from DB
- `run_evaluation()` computes metrics + identifies FP/FN pairs for analysis
- `run_threshold_sweep()` across 8 thresholds with comparison table output

**Tests** (15 tests in `tests/test_metrics.py` + `tests/test_harness.py`):
- 8 metrics tests: perfect score, all-FP, all-FN, mixed results, canonical ordering, empty cases
- 7 harness tests: threshold filtering, FP/FN identification, DB ground truth loading

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Hard negative sampling forced minimum of 1**
- **Found during:** Task 1, test execution
- **Issue:** `max(1, int(len * ratio))` included 1 hard negative even when ratio=0.0
- **Fix:** Added `ratio > 0` guard before computing hard negative count
- **Files modified:** `src/event_dedup/ground_truth/candidate_generator.py`
- **Commit:** b7d4744

## Verification Results

1. `uv run pytest tests/ -x -v` -- 80 tests pass (57 existing + 23 new)
2. `from event_dedup.models import GroundTruthPair` -- OK
3. `from event_dedup.evaluation.metrics import compute_metrics` -- OK
4. `from event_dedup.ground_truth.candidate_generator import generate_candidates_from_events` -- OK
5. `compute_metrics({('a','b'),('c','d')}, {('a','b')}, {('c','d')})` -- P=0.5, R=1.0, F1=0.667

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | b7d4744 | Ground truth model, candidate generator, and labeling tool |
| 2 | ce9c616 | Evaluation harness with precision, recall, F1 metrics |

## Self-Check: PASSED

All 9 created files verified present on disk. Both commit hashes (b7d4744, ce9c616) verified in git log.
