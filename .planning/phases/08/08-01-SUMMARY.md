---
phase: 08-dynamic-config
plan: 01
subsystem: config-api
tags: [config, api, encryption, backend]
dependency_graph:
  requires: []
  provides: [config-api, config-model, encryption-util, db-config-loading]
  affects: [worker, matching-pipeline]
tech_stack:
  added: [cryptography]
  patterns: [deep-merge, singleton-row, fernet-encryption, per-run-config]
key_files:
  created:
    - src/event_dedup/config/encryption.py
    - src/event_dedup/models/config_settings.py
    - src/event_dedup/api/routes/config.py
    - config/alembic/versions/005_add_config_settings.py
    - tests/test_config_api.py
  modified:
    - src/event_dedup/models/__init__.py
    - src/event_dedup/config/settings.py
    - src/event_dedup/api/schemas.py
    - src/event_dedup/api/app.py
    - src/event_dedup/matching/config.py
    - src/event_dedup/worker/orchestrator.py
    - src/event_dedup/worker/watcher.py
    - src/event_dedup/worker/__main__.py
    - tests/test_watcher.py
    - pyproject.toml
    - uv.lock
decisions:
  - Use singleton row (id=1) for config_settings rather than key-value store
  - Fernet encryption with graceful plain-text fallback for development
  - Per-run config loading from DB with YAML fallback for backward compatibility
  - Deep merge strategy for partial PATCH updates to preserve unset fields
metrics:
  duration: 5m 24s
  completed: 2026-02-28
  tasks_completed: 2
  tasks_total: 2
  tests_added: 9
  tests_total: 380
  files_created: 5
  files_modified: 11
---

# Phase 8 Plan 1: Dynamic Configuration System Backend Summary

Database-backed configuration API with Fernet encryption, deep-merge partial updates, and per-run config loading from DB with YAML fallback.

## What Was Built

### 1. Encryption Utility (`src/event_dedup/config/encryption.py`)
- `get_fernet()`: Returns Fernet instance from `EVENT_DEDUP_ENCRYPTION_KEY` env var, or None
- `encrypt_value()`: Encrypts with Fernet; falls back to `plain:` prefix if no key configured
- `decrypt_value()`: Decrypts Fernet tokens; handles `plain:` prefix for backward compatibility

### 2. ConfigSettings Model (`src/event_dedup/models/config_settings.py`)
- Singleton row (id=1) with `config_json` (JSON), `encrypted_api_key` (Text), `updated_at`, `updated_by`
- Uses `sa.JSON` (not PostgreSQL dialect) for SQLite test compatibility

### 3. Alembic Migration (`config/alembic/versions/005_add_config_settings.py`)
- Creates `config_settings` table with down_revision `004_audit_log`

### 4. API Schemas (`src/event_dedup/api/schemas.py`)
- `AIConfigResponse`: All AIMatchingConfig fields except `api_key`
- `ConfigResponse`: Full config structure with `has_api_key` boolean and `updated_at`
- `ConfigUpdateRequest`: All sections optional for partial updates, plus `ai_api_key` write-only field
- `config_to_response()`: Converts MatchingConfig to response dict, stripping api_key

### 5. Config API Endpoints (`src/event_dedup/api/routes/config.py`)
- `GET /api/config`: Returns current config from DB or defaults; never includes api_key
- `PATCH /api/config`: Deep-merge partial updates; handles API key encryption/clearing; upserts config row

### 6. Per-Run Config Loading (`src/event_dedup/matching/config.py`)
- `load_config_for_run()`: Loads config from DB with API key decryption; falls back to YAML + env var
- `ScoringWeights.warn_if_weights_dont_sum()`: model_validator that logs warning if weights deviate from 1.0

### 7. Worker Simplification
- Orchestrator functions now accept `matching_config: MatchingConfig | None = None` and load from DB when None
- Watcher no longer receives or passes matching_config
- Worker `__main__.py` no longer loads config or overrides env vars; orchestrator handles per-run

## Test Results

```
380 passed in 1.61s
```

9 new tests in `tests/test_config_api.py`:
- test_get_config_defaults
- test_patch_config_scoring
- test_patch_config_preserves_unset
- test_patch_api_key_not_in_get
- test_clear_api_key
- test_patch_ai_enabled_toggle
- test_deep_merge_nested
- test_config_round_trip
- test_load_config_for_run

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Fixed existing watcher test for removed parameter**
- **Found during:** Task 2
- **Issue:** `test_watch_and_process_stops_on_stop_event` in `tests/test_watcher.py` passed `matching_config` keyword argument that was removed from `watch_and_process()` signature
- **Fix:** Removed the `matching_config=None` kwarg from the test call
- **Files modified:** tests/test_watcher.py
- **Commit:** bac5a63

## Self-Check: PASSED

All 5 created files verified. All 2 commits verified.
