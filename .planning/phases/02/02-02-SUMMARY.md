---
phase: "02"
plan: "02"
subsystem: "candidate-pairs-pipeline"
tags: [blocking, candidate-pairs, pipeline, scoring, matching]
dependency-graph:
  requires: [02-01]
  provides: [candidate-pair-generator, scoring-pipeline, match-pairs-for-clustering]
  affects: [02-03, 02-04]
tech-stack:
  added: []
  patterns: [blocking-index, cross-source-pairs, canonical-ordering, pure-function-pipeline]
key-files:
  created:
    - src/event_dedup/matching/candidate_pairs.py
    - src/event_dedup/matching/pipeline.py
    - tests/test_candidate_pairs.py
    - tests/test_pipeline.py
  modified: []
decisions:
  - "Candidate pairs deduplicated via set across blocking groups (events sharing N keys produce pair once)"
  - "Cross-source enforcement at pair generation level, not pipeline level"
  - "Pipeline is a pure function (no DB access) taking event dicts and MatchingConfig"
  - "get_match_pairs() provides the interface for Plan 02-03 clustering"
metrics:
  duration: "~4 minutes"
  completed: "2026-02-28"
  tasks: 2
  tests-added: 27
  tests-total: 186
---

# Phase 2 Plan 2: Candidate Pair Generator and Matching Pipeline Orchestrator

Blocking-based candidate pair generator with cross-source enforcement and reduction stats, plus a pure-function scoring pipeline that scores all pairs using four signal scorers and outputs three-tier match decisions.

## What Was Built

### Candidate Pair Generator (`candidate_pairs.py`)

- **`generate_candidate_pairs(events)`** builds a blocking index from event `blocking_keys`, then generates all cross-source pairs within each block using canonical ordering (`id_a < id_b`) and deduplication across blocking groups.
- **`CandidatePairStats`** dataclass reports: total events, total possible cross-source pairs (naive baseline), blocked pairs, and reduction percentage.
- **`_count_cross_source_pairs()`** helper computes the naive baseline by multiplying source group sizes for each pair of distinct sources.

### Matching Pipeline Orchestrator (`pipeline.py`)

- **`score_candidate_pairs(events, config)`** is a PURE FUNCTION (no DB access) that:
  1. Generates candidate pairs via blocking keys
  2. Scores each pair with all four signal scorers (date, geo, title, description)
  3. Combines scores into a weighted average via the combiner
  4. Applies threshold-based decision logic (match/ambiguous/no_match)
- **`MatchDecisionRecord`** dataclass captures: event IDs, all four signal scores, combined score, decision, and tier.
- **`MatchResult`** dataclass aggregates: all decisions, pair stats, and counts by decision type.
- **`get_match_pairs(result)`** extracts match-decision pairs as a set of (id_a, id_b) tuples -- the interface that Plan 02-03 (graph-based clustering) consumes.

### Tests

27 new tests (17 candidate pairs + 10 pipeline):

**Candidate pair tests (17):**
- Cross-source pair generation (different sources, same source, three events)
- Canonical ordering enforcement
- Deduplication across multiple shared blocking keys
- No shared keys, empty keys, None keys
- Blocking reduction statistics
- Stats dataclass fields and empty input
- Sorted output, _count_cross_source_pairs helper

**Pipeline tests (10):**
- Identical events -> match decision with high scores
- Completely different events -> no_match decision
- Partially similar events -> ambiguous decision
- Stats sum invariant (match + ambiguous + no_match == total)
- get_match_pairs returns only match decisions
- Cross-source enforcement (same source -> 0 decisions)
- Config passthrough (high threshold -> no matches)
- Decision record and result type verification
- Empty events list

All 186 project tests pass with no regressions.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `a5315ed` | feat | Add candidate pair generator with blocking reduction stats |
| `ac2aaee` | feat | Add matching pipeline orchestrator with full scoring |

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 1 - Bug] Fixed ambiguous pair test data**
- **Found during:** Task 2, test verification
- **Issue:** Test used titles "fasnetumzug nordweil" vs "nordwiler narrenfahrplan fasnetumzug" which produced title similarity ~0.69, pushing the combined score above the match threshold (0.83 combined). The test expected "ambiguous" but got "match".
- **Fix:** Changed second title to "nordwiler narrenfahrplan mit umzug" (title similarity ~0.41), producing a combined score ~0.75 which correctly falls in the ambiguous zone.
- **Files modified:** tests/test_pipeline.py

**2. [Rule 1 - Bug] Fixed high-threshold config test**
- **Found during:** Task 2, test verification
- **Issue:** Test used perfectly identical events (combined score = 1.0 exactly), which exceeded even the 0.99 threshold. The test expected "no matches" but got a match because 1.0 >= 0.99.
- **Fix:** Changed to similar-but-not-identical events (different title word order, slightly different geo coordinates, different descriptions) so the combined score falls below 0.99.
- **Files modified:** tests/test_pipeline.py

## Self-Check: PASSED

- All 5 files verified on disk (2 source + 2 test + 1 summary)
- All 2 commit hashes verified in git log
- All 186 tests passing (27 new + 159 existing)
