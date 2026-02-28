# Phase 7: Accuracy Refinement - UAT Report

**Date:** 2026-02-28
**Status:** ALL PASS

## Success Criteria Results

### SC1: German Dialect Synonyms (MTCH-07) - PASS

- Synonym dictionary defines 2 groups: fastnacht (7 variants), hemdglunker (3 variants)
- All replacements correct: fasnet, fasching, karneval, fasent, fasend -> fastnacht
- Compound words handled: fasnetsumzug -> fastnachtumzug (longest-first replacement)
- Canonical forms unchanged: fastnacht stays fastnacht
- Integrated into normalize_text() pipeline after umlaut expansion
- FileProcessor loads synonyms at init and applies during ingestion
- Re-normalization script (scripts/renormalize_titles.py) exists for existing DB records

### SC2: Category-Aware Matching Weights (MTCH-08) - PASS

- CategoryWeightsConfig with priority list and ScoringWeights overrides
- fasnacht: title=0.25 (lowered from 0.30), geo=0.30 (raised from 0.25)
- versammlung: title=0.40 (raised from 0.30), geo=0.20 (lowered from 0.25)
- Priority ordering works: fasnacht wins when both categories present
- Default weights used when no shared category or no override defined
- resolve_weights() integrated in score_candidate_pairs()
- evaluate_category_subset() available for per-category F1 reporting
- Combiner completely unchanged (8 combiner tests pass unmodified)

### SC3: Source-Type-Aware Comparison (MTCH-09) - PASS

- cross_source_type config: primary_weight=0.4, secondary_weight=0.6, blend=[0.25, 0.95]
- Score improvements for artikel-terminliste pairs:
  - Preismaskenball: 0.64 -> 0.79 (+0.15)
  - Schiebeschlage: 0.39 -> 0.76 (+0.36)
  - Landschaftspflegetag: 0.87 -> 0.95 (+0.08)
- Same-type pairs unaffected (scores identical with/without cross config)
- Anzeige pairs excluded from cross-type logic

## Test Suite

- **371/371 tests pass** (0 failures, 0 regressions)
- 142 tests in Phase 7-related test files all pass
- No existing tests required modification

## Issues Found

None.
