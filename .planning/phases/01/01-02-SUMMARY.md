---
phase: 01-foundation
plan: 02
subsystem: preprocessing
tags: [normalization, blocking, prefix-stripping, german-text]
dependency-graph:
  requires: [01-01]
  provides: [preprocessing-pipeline, blocking-keys, normalized-fields]
  affects: [file-processor, source-events]
tech-stack:
  added: [pyyaml]
  patterns: [config-driven-normalization, unicode-nfc, geo-grid-blocking]
key-files:
  created:
    - src/event_dedup/preprocessing/normalizer.py
    - src/event_dedup/preprocessing/prefix_stripper.py
    - src/event_dedup/preprocessing/blocking.py
    - src/event_dedup/preprocessing/__init__.py
    - src/event_dedup/config/prefixes.yaml
    - src/event_dedup/config/city_aliases.yaml
    - tests/test_normalizer.py
    - tests/test_prefix_stripper.py
    - tests/test_blocking.py
  modified:
    - src/event_dedup/config/settings.py
    - src/event_dedup/ingestion/file_processor.py
    - tests/test_file_processor.py
decisions:
  - Use Unicode NFC normalization before umlaut expansion to handle both composed and decomposed forms
  - Prefix matching against original German forms (real umlauts) before normalization
  - Config defaults use __file__-relative paths for portability
key-decisions:
  - "Unicode NFC before umlaut expansion: ensures both composed (single codepoint) and decomposed (base+combining) forms are handled correctly"
  - "Prefixes.yaml uses original German (real umlauts): matching happens against original titles, then result is normalized"
  - "FileProcessor loads configs at init, not per-file: avoids repeated YAML parsing"
metrics:
  duration: 4m
  completed: 2026-02-27
  tasks: 2/2
  tests-added: 43
  tests-total: 57
  files-created: 9
  files-modified: 3
---

# Phase 1 Plan 02: Text Preprocessing Pipeline Summary

German text normalization with umlaut expansion, config-driven prefix stripping, city alias resolution, and date+location blocking key generation integrated into file ingestion.

## What Was Built

### Normalization Pipeline (`normalizer.py`)
- `normalize_text()`: lowercase, Unicode NFC normalization, umlaut expansion (ae/oe/ue/ss), whitespace collapse, punctuation removal (hyphens preserved for German compound words)
- `normalize_city()`: text normalization plus alias resolution for district-to-municipality mappings
- `load_city_aliases()`: loads YAML config with normalized keys/values at load time

### Prefix Stripping (`prefix_stripper.py`)
- `strip_prefixes()`: case-insensitive prefix removal supporting dash (-, --, en-dash, em-dash) and colon separators
- `normalize_title()`: strip-then-normalize pipeline for titles
- `PrefixConfig`: Pydantic model for type-safe config loading
- Supports 6 dash prefixes, 11 colon prefixes, 1 generic prefix from research findings

### Blocking Key Generation (`blocking.py`)
- `generate_blocking_keys()`: produces `dc|{date}|{city}` and `dg|{date}|{geo_grid}` keys
- `geo_grid_key()`: snaps coordinates to ~10km grid cells (0.09 lat x 0.13 lon)
- `is_valid_geo()`: filters by confidence >= 0.85 AND Breisgau bounding box (lat 47.5-48.5, lon 7.3-8.5)
- Outlier coordinates (e.g., Darmstadt geocoding errors) automatically excluded

### File Processor Integration
- `FileProcessor.__init__` loads prefix and city alias configs once at init time
- Every ingested event now has: `title_normalized`, `short_description_normalized`, `location_name_normalized`, `location_city_normalized`, `blocking_keys`
- Prefix stripping applied to titles before normalization
- City alias resolution applied during city normalization

### Configuration Files
- `prefixes.yaml`: 18 prefix patterns with original German forms (real umlauts)
- `city_aliases.yaml`: 20 district-to-municipality mappings for the Breisgau region

## Commits

| Commit | Type | Description |
|--------|------|-------------|
| 86f035b | feat | Text normalization, prefix stripping, and blocking key generation (Task 1) |
| 5c16403 | feat | Integrate preprocessing into file processor (Task 2) |

## Test Results

57 tests total, all passing:
- 13 normalizer tests (text, umlaut, city, alias)
- 15 prefix stripper tests (dash, colon, generic, case-insensitive, separators)
- 13 blocking tests (dc keys, dg keys, geo filtering, bounding box, multi-date)
- 11 file processor tests (6 existing + 5 new integration tests)
- 8 JSON loader tests (unchanged)

## Deviations from Plan

None -- plan executed exactly as written.

## Decisions Made

1. **Unicode NFC before umlaut expansion**: Normalizing to NFC first merges decomposed forms (base + combining diaeresis) into composed single codepoints, which are then expanded. This handles both input forms correctly.

2. **Prefixes.yaml uses original German forms**: The YAML config contains real umlauts (Bundnis -> Bündnis, Tür not Tuer). Prefix matching happens case-insensitively against the original title text, then the stripped result is normalized.

3. **FileProcessor loads configs at init**: Avoids re-parsing YAML on every file, improving performance for batch processing.

## Interfaces Provided

For Plan 01-03 (candidate generation):
```python
# Blocking keys are stored per-event as JSON arrays
source_event.blocking_keys  # ["dc|2026-02-12|kenzingen", "dg|2026-02-12|48.15|7.80"]

# Normalized fields for fuzzy matching
source_event.title_normalized  # "kita-gizig-umzug" (prefix stripped, lowercased, umlauts expanded)
source_event.location_city_normalized  # "kenzingen" (alias-resolved, normalized)
```

## Self-Check: PASSED

All 9 created files verified present. Both commits (86f035b, 5c16403) verified in git log.
