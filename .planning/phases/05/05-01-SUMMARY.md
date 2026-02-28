---
phase: 05-ai-matching
plan: 01
subsystem: ai-matching
tags: [ai, gemini, cache, cost-tracking, schemas, prompt-engineering]
dependency_graph:
  requires: []
  provides: [ai-matching-schemas, ai-matching-client, ai-matching-cache, ai-cost-tracker, ai-matching-config, ai-db-models]
  affects: [matching-config, models-init]
tech_stack:
  added: [google-genai]
  patterns: [structured-output, content-hash-cache, token-cost-estimation, async-api-wrapper]
key_files:
  created:
    - src/event_dedup/ai_matching/__init__.py
    - src/event_dedup/ai_matching/schemas.py
    - src/event_dedup/ai_matching/prompt.py
    - src/event_dedup/ai_matching/cache.py
    - src/event_dedup/ai_matching/cost_tracker.py
    - src/event_dedup/ai_matching/client.py
    - src/event_dedup/models/ai_match_cache.py
    - src/event_dedup/models/ai_usage_log.py
    - config/alembic/versions/003_add_ai_matching_tables.py
    - tests/test_ai_matching.py
  modified:
    - pyproject.toml
    - src/event_dedup/matching/config.py
    - src/event_dedup/models/__init__.py
decisions:
  - google-genai SDK (unified, not deprecated google-generativeai) for Gemini API access
  - Content-hash cache uses SHA-256 of matching-relevant fields only, with canonical ID ordering
  - Cache staleness detection by model name comparison (auto-invalidates on model upgrade)
  - AIMatchingConfig defaults to enabled=False for safe rollout
  - Gemini 2.5 Flash pricing used for cost estimation (0.30/1M input, 2.50/1M output)
metrics:
  duration: 3m
  completed: 2026-02-28
  tasks: 2/2
  tests_added: 19
  tests_total: 302
  files_created: 10
  files_modified: 3
---

# Phase 5 Plan 1: AI Matching Infrastructure Summary

Complete ai_matching/ package with Gemini client, structured output schemas, prompt engineering, content-hash cache, cost tracker, and database models -- all testable without a live API key.

## What Was Built

### Task 1: Schemas, Prompt, Config, and DB Models (07cb9a1)

- **AIMatchResult** Pydantic schema with decision/confidence/reasoning fields and validation bounds
- **SYSTEM_PROMPT** tuned for German regional event deduplication (handles dialect variations, source type differences)
- **format_event_pair()** formats both events with pre-computed signal scores for context
- **AIMatchingConfig** added to MatchingConfig with enabled=False, Gemini 2.5 Flash defaults, cost pricing
- **AIMatchCache** SQLAlchemy model with SHA-256 pair_hash unique index and decision constraint
- **AIUsageLog** SQLAlchemy model with batch_id index for usage aggregation
- **Alembic migration 003** creating both tables, chained from 002_pg_trgm_dates

### Task 2: Cache, Cost Tracker, Client, and Tests (c594a1e)

- **compute_pair_hash()** extracts matching-relevant fields, canonical-orders by ID, produces deterministic SHA-256
- **lookup_cache()/store_cache()** with model staleness detection and concurrent insert deduplication
- **estimate_cost()** computes USD from token counts and per-1M-token pricing
- **log_usage()** persists each API call or cache hit to ai_usage_log
- **get_batch_summary()/get_period_summary()** aggregate token usage and costs
- **create_client()/call_gemini()** wrap google-genai SDK with structured output and async API
- **19 unit tests** covering schemas, config, cache hashing, cost estimation, prompt formatting, DB cache operations, and usage logging

## Deviations from Plan

None -- plan executed exactly as written.

## Test Results

```
tests/test_ai_matching.py: 19 passed
Full suite: 302 passed in 1.11s (zero regressions)
```

## Key Files

| File | Purpose |
|------|---------|
| `src/event_dedup/ai_matching/schemas.py` | AIMatchResult Pydantic model for structured Gemini output |
| `src/event_dedup/ai_matching/prompt.py` | System prompt and event pair formatting |
| `src/event_dedup/ai_matching/client.py` | Async Gemini API wrapper with structured output |
| `src/event_dedup/ai_matching/cache.py` | Content-hash computation and DB cache operations |
| `src/event_dedup/ai_matching/cost_tracker.py` | Token cost estimation and usage logging |
| `src/event_dedup/matching/config.py` | AIMatchingConfig integrated into MatchingConfig |
| `src/event_dedup/models/ai_match_cache.py` | SQLAlchemy model for cached AI decisions |
| `src/event_dedup/models/ai_usage_log.py` | SQLAlchemy model for token usage tracking |
| `config/alembic/versions/003_add_ai_matching_tables.py` | Alembic migration for AI tables |
| `tests/test_ai_matching.py` | 19 unit tests for all AI matching components |

## Self-Check: PASSED

- All 10 created files: FOUND
- All 3 modified files: verified via git
- Commit 07cb9a1 (Task 1): FOUND
- Commit c594a1e (Task 2): FOUND
