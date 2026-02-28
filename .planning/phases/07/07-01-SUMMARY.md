# Plan 07-01 Summary

**Phase:** 07 - Accuracy Refinement
**Plan:** 01 - German dialect synonym dictionary + source-type-aware title scoring
**Status:** COMPLETE
**Duration:** ~5m
**Requirements:** MTCH-07, MTCH-09

## What Was Done

### Task 1: Synonym dictionary, loading module, and normalizer integration

- Created `src/event_dedup/config/synonyms.yaml` with two synonym groups:
  - **fastnacht** (canonical): fasnets, fasent, fasend, fasnet, fasnacht, fasching, karneval (7 variants)
  - **hemdglunker** (canonical): hemdklunker, hemdglunki, hendglunki (3 variants)
- Created `src/event_dedup/preprocessing/synonyms.py` with `load_synonym_map()` and `apply_synonyms()` functions
  - Variants sorted longest-first at load time for correct compound word handling
- Updated `normalizer.py`: `normalize_text()` now accepts optional `synonym_map` parameter, applies synonyms after umlaut expansion
- Updated `prefix_stripper.py`: `normalize_title()` passes `synonym_map` through
- Updated `file_processor.py`: `FileProcessor` loads `synonym_map` at init and uses it during ingestion
- Created `scripts/renormalize_titles.py`: async batch update script for existing DB records
- Created `tests/test_synonyms.py` (22 tests): covers loading, replacement, compounds, edge cases
- Extended `tests/test_normalizer.py` (4 new tests): synonym-aware normalization

### Task 2: Source-type-aware title scoring with cross_source_type config

- Added `cross_source_type: TitleConfig | None` field to `TitleConfig` (self-referential with `model_rebuild()`)
- Updated `title_scorer.py`: uses `cross_source_type` config when source types differ (artikel vs terminliste)
- Added `cross_source_type` section to `config/matching.yaml`: primary_weight=0.4, secondary_weight=0.6, blend_lower=0.25, blend_upper=0.95
- Extended `tests/test_scorers.py` (6 new tests): cross-type override, same-type no override, missing source_type, anzeige excluded, wider blend range
- Extended `tests/test_matching_config.py` (3 new tests): YAML loading, None default, real config

### Bug Fix: Cross-source enforcement

- Fixed `generate_candidate_pairs()` to filter out same-source pairs per decision [02-02]
- Updated `tests/test_candidate_pairs.py` to match corrected behavior

## Decisions

- [07-01]: All synonym entries use post-normalization forms (lowercase, umlauts expanded)
- [07-01]: Synonym replacement applied at normalization time O(events), not scoring time O(pairs)
- [07-01]: cross_source_type only triggers for artikel-terminliste pairs, not anzeige

## Verification

```
371 passed in 1.60s
```

All existing and new tests pass.
