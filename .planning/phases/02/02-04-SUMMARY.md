---
phase: 02-matching-pipeline
plan: 04
subsystem: canonical-synthesis
tags: [canonical, synthesis, enrichment, pipeline, evaluation, end-to-end]
dependency_graph:
  requires: [02-01, 02-02, 02-03]
  provides: [synthesize_canonical, enrich_canonical, run_full_pipeline, generate_predictions_multisignal]
  affects: [evaluation-harness, matching-pipeline]
tech_stack:
  added: []
  patterns: [field-strategy-dispatch, downgrade-prevention, lazy-import-circular-break, provenance-tracking]
key_files:
  created:
    - src/event_dedup/canonical/__init__.py
    - src/event_dedup/canonical/synthesizer.py
    - src/event_dedup/canonical/enrichment.py
    - tests/test_synthesizer.py
    - tests/test_enrichment.py
    - tests/test_end_to_end.py
  modified:
    - src/event_dedup/matching/pipeline.py
    - src/event_dedup/evaluation/harness.py
decisions:
  - Lazy imports in pipeline.py to break circular dependency (pipeline -> clustering -> pipeline)
  - TYPE_CHECKING guard for ClusterResult type annotation in PipelineResult dataclass
  - Provenance uses "union_all_sources" for list/date fields since multiple sources contribute
  - Boolean provenance tracks first source with True value
metrics:
  duration: 6m
  completed: 2026-02-28
  tasks_completed: 2
  tasks_total: 2
  test_count: 66
  total_test_suite: 257
  files_created: 6
  files_modified: 2
  lines_added: ~1498
---

# Phase 2 Plan 4: Canonical Event Synthesis, Enrichment, Full Pipeline, and End-to-End Tests Summary

Canonical event synthesis with 7 field selection strategies and provenance tracking, enrichment with downgrade prevention, full pipeline orchestrator (blocking -> scoring -> clustering -> synthesis), updated evaluation harness with multi-signal predictions, and 66 new tests covering all strategies and end-to-end scenarios.

## What Was Built

### Canonical Event Synthesizer (`synthesizer.py`, 297 lines)
Pure function `synthesize_canonical(source_events, config)` that creates a single canonical event from a cluster of source events. Implements 7 field selection strategies:

| Strategy | Fields | Logic |
|----------|--------|-------|
| longest_non_generic | title | Prefer titles >= 10 chars, fallback to longest |
| longest | short_description, description | Longest non-empty value |
| union | highlights, categories | Flatten + deduplicate preserving order |
| most_complete | location_name, district, street, zipcode | Longest non-empty (semantic alias) |
| most_frequent | location_city | Counter-based, ties by first occurrence |
| highest_confidence | geo | Event with highest geo_confidence |
| any_true | is_family_event, is_child_focused, admission_free | True if any source is True |

Field provenance tracks which source event contributed each canonical field (event ID or "union_all_sources" for aggregate fields).

### Canonical Event Enrichment (`enrichment.py`, 64 lines)
Pure function `enrich_canonical(existing_canonical, all_sources, config)` that re-synthesizes a canonical when new sources arrive. Key feature: **downgrade prevention** -- if the existing canonical already had a longer text field (title, short_description, description), that value and its provenance are preserved. Version is incremented, source_count updated.

### Full Pipeline Orchestrator (`pipeline.py` additions)
`run_full_pipeline(events, config) -> PipelineResult` -- a pure function that chains:
1. `score_candidate_pairs()` -- blocking + 4-signal scoring
2. `cluster_matches()` -- graph-based connected components with coherence
3. `synthesize_canonical()` -- best-field selection per cluster

Each canonical event gets `needs_review` (True for flagged clusters) and `match_confidence` (average combined_score of internal match decisions; None for singletons).

`extract_predicted_pairs()` provides the evaluation interface.

### Updated Evaluation Harness (`harness.py` additions)
- `generate_predictions_multisignal(events, config)` -- pure function replacement for Phase 1 title-only prediction
- `run_multisignal_evaluation(session, config)` -- async function connecting multi-signal predictions to ground truth DB for F1 measurement

### Test Coverage (66 new tests)
- `test_synthesizer.py` (32 tests): All field strategies, provenance, edge cases
- `test_enrichment.py` (11 tests): Upgrades, downgrades, versioning, source counting
- `test_end_to_end.py` (12 tests): Full pipeline with duplicates, different events, multiple clusters, transitive matches, best-field selection, blocking stats

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed circular import between pipeline.py and graph_cluster.py**
- **Found during:** Task 2
- **Issue:** Adding `from event_dedup.clustering.graph_cluster import ClusterResult, cluster_matches` at the top of `pipeline.py` created a circular import chain: `pipeline.py` -> `graph_cluster.py` -> `pipeline.py` (for `MatchDecisionRecord`)
- **Fix:** Moved `cluster_matches` and `synthesize_canonical` imports to lazy imports inside `run_full_pipeline()` function body. Added `TYPE_CHECKING` guard for `ClusterResult` type annotation.
- **Files modified:** `src/event_dedup/matching/pipeline.py`
- **Commit:** d984af8

## Verification Results

All verification checks from the plan pass:
- 66 new tests: PASS
- Full test suite (257 tests): PASS
- Import chain verification: PASS
- Smoke test (2 duplicate events -> 1 canonical, 1 match, 1 cluster): PASS

## Commits

| Task | Commit | Description |
|------|--------|-------------|
| 1 | 1e53ba0 | Canonical synthesis + enrichment with provenance and 42 tests |
| 2 | d984af8 | Full pipeline orchestrator, evaluation harness, 12 end-to-end tests |

## Requirements Addressed

- **CANL-01**: Canonical event synthesized by selecting best field from each source (7 strategies)
- **CANL-02**: Field-level provenance tracks source event contribution per field
- **CANL-03**: Enrichment re-synthesizes without downgrading existing good data
