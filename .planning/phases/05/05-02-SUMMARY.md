---
phase: 05-ai-matching
plan: 02
subsystem: ai-matching-pipeline
tags: [ai, gemini, resolver, pipeline-integration, evaluation, orchestrator]
dependency_graph:
  requires: [ai-matching-schemas, ai-matching-client, ai-matching-cache, ai-cost-tracker, ai-matching-config]
  provides: [ai-resolver, pipeline-rebuild, ai-orchestrator-integration, ai-evaluation-comparison]
  affects: [worker-orchestrator, matching-pipeline, evaluation-harness, docker-compose, settings]
tech_stack:
  added: []
  patterns: [async-semaphore-concurrency, cache-before-api, graceful-degradation, pipeline-rebuild]
key_files:
  created:
    - src/event_dedup/ai_matching/resolver.py
    - tests/test_ai_resolver.py
  modified:
    - src/event_dedup/matching/pipeline.py
    - src/event_dedup/worker/orchestrator.py
    - src/event_dedup/config/settings.py
    - src/event_dedup/worker/__main__.py
    - src/event_dedup/evaluation/harness.py
    - docker-compose.yml
    - tests/test_orchestrator.py
decisions:
  - resolve_ambiguous_pairs uses asyncio.Semaphore for concurrent API call limiting
  - _apply_ai_result maps same->match, different->no_match with confidence threshold gate
  - rebuild_pipeline_result re-clusters only when ambiguous pairs were actually resolved
  - _maybe_resolve_ai is the single integration point called by both process_new_file and process_file_batch
  - AI matching auto-enables when GEMINI_API_KEY env var is set (no config file change needed)
metrics:
  duration: 4m
  completed: 2026-02-28
  tasks: 2/2
  tests_added: 14
  tests_total: 316
  files_created: 2
  files_modified: 7
---

# Phase 5 Plan 2: AI Pipeline Integration Summary

AI resolver wired into worker orchestrator with cache-first resolution, semaphore-limited concurrency, graceful API failure handling, and evaluation harness for deterministic vs AI-assisted F1 comparison.

## What Was Built

### Task 1: AI resolver, pipeline rebuild function, and pipeline integration (00a15ab)

- **resolve_ambiguous_pairs** async function: filters ambiguous decisions, checks content-hash cache, calls Gemini Flash for uncached pairs, logs usage/cost per call, returns updated MatchResult
- **_apply_ai_result** maps AI decisions to pipeline decisions: same->match, different->no_match, with confidence threshold (>=0.6 overrides, <0.6 keeps as ambiguous with tier="ai_low_confidence")
- **rebuild_pipeline_result** public function in pipeline.py: re-runs clustering and canonical synthesis from an updated MatchResult without duplicating run_full_pipeline logic
- **_maybe_resolve_ai** private helper in orchestrator.py: checks ai.enabled and api_key, calls resolve_ambiguous_pairs, rebuilds pipeline result only when ambiguous pairs were actually resolved
- Both **process_new_file** and **process_file_batch** call _maybe_resolve_ai after run_full_pipeline; process_existing_files inherits via delegation
- **Settings.gemini_api_key** field maps to EVENT_DEDUP_GEMINI_API_KEY env var
- **Worker __main__** auto-enables AI matching when gemini_api_key is set
- **docker-compose.yml** passes GEMINI_API_KEY through to worker container

### Task 2: Evaluation harness update and resolver tests (a3a6470)

- **run_ai_comparison_evaluation** in harness.py: runs deterministic-only and AI-assisted matching, computes and prints side-by-side precision/recall/F1/TP/FP/FN comparison table with deltas
- **12 resolver tests** in test_ai_resolver.py: _apply_ai_result (5 tests: high confidence same/different, low confidence stays ambiguous, exactly at threshold, preserves signals) and resolve_ambiguous_pairs (7 tests: no ambiguous noop, resolve to match, resolve to no_match, low confidence stays ambiguous, API failure keeps ambiguous, non-ambiguous unchanged, cache hit skips API)
- **2 orchestrator tests**: verify resolve_ambiguous_pairs called when AI enabled (mock_resolve_ai.call_count==1) and skipped when disabled (call_count==0)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed CandidatePairStats field name in test**
- **Found during:** Task 2
- **Issue:** Plan used `total_pairs` but actual field is `total_possible_pairs`
- **Fix:** Updated _make_match_result helper to use correct field name
- **Files modified:** tests/test_ai_resolver.py
- **Commit:** a3a6470

## Test Results

```
tests/test_ai_resolver.py: 12 passed
tests/test_ai_matching.py: 19 passed
tests/test_orchestrator.py: 7 passed (including 2 new AI integration tests)
Full suite: 316 passed in 1.46s (zero regressions, +14 new tests)
```

## Key Files

| File | Purpose |
|------|---------|
| `src/event_dedup/ai_matching/resolver.py` | Core AI resolver: filter ambiguous -> cache check -> API call -> update decisions |
| `src/event_dedup/matching/pipeline.py` | Added rebuild_pipeline_result for re-clustering after AI resolution |
| `src/event_dedup/worker/orchestrator.py` | Added _maybe_resolve_ai helper, called by both process_new_file and process_file_batch |
| `src/event_dedup/config/settings.py` | Added gemini_api_key field (EVENT_DEDUP_GEMINI_API_KEY) |
| `src/event_dedup/worker/__main__.py` | Auto-enables AI matching when API key is provided |
| `src/event_dedup/evaluation/harness.py` | Added run_ai_comparison_evaluation for F1 comparison |
| `docker-compose.yml` | GEMINI_API_KEY env var for worker container |
| `tests/test_ai_resolver.py` | 12 tests for resolver with mocked Gemini client |
| `tests/test_orchestrator.py` | 2 new AI integration tests added |

## Self-Check: PASSED

- All 2 created files: FOUND
- All 7 modified files: verified via git
- Commit 00a15ab (Task 1): FOUND
- Commit a3a6470 (Task 2): FOUND
