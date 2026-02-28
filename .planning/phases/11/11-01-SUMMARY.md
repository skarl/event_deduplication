---
phase: 11-frontend-ux
plan: 01
subsystem: backend-filters-sort
tags: [api, filtering, sorting, pagination, backend]
dependency_graph:
  requires: [10-01, 10-02]
  provides: [categories-endpoint, cities-endpoint, multi-filter, sort-api, size-cap]
  affects: [canonical-events-api]
tech_stack:
  added: []
  patterns: [multi-value-query-params, or-semantics, and-semantics, nullslast-nullsfirst]
key_files:
  created: []
  modified:
    - src/event_dedup/api/routes/canonical_events.py
    - tests/test_api.py
decisions:
  - Multi-value city filter with OR semantics (event matches ANY selected city)
  - Multi-value category filter with AND semantics (event must have ALL selected categories)
  - nullslast for desc sort, nullsfirst for asc sort on nullable columns
  - size cap raised from le=100 to le=10000 to support ALL option
metrics:
  duration: ~2m
  completed: 2026-02-28
  tasks_completed: 2
  tasks_total: 2
  tests_added: 9
  tests_total: 407
  files_created: 0
  files_modified: 2
---

# Phase 11 Plan 1: Backend — Multi-Filter, Sort, Size Cap, and Distinct-Value Endpoints

Added multi-value city/category filtering, 7-column sorting, raised size cap, and two new distinct-value endpoints for frontend autocomplete.

## What Was Built

### Task 1: Distinct-value endpoints and updated list_canonical_events

**File:** `src/event_dedup/api/routes/canonical_events.py`

- `GET /api/canonical-events/categories` — returns sorted distinct category values (flattened from JSON arrays)
- `GET /api/canonical-events/cities` — returns sorted distinct city values
- Both registered BEFORE `/{event_id}` to avoid route conflict
- `list_canonical_events` updated:
  - `city: list[str]` with OR semantics (ilike matching)
  - `category: list[str]` with AND semantics (all must match)
  - `sort_by` with 7-column map (title, city, date, categories, source_count, confidence, review)
  - `sort_dir` with nullslast (desc) / nullsfirst (asc) handling
  - `size` cap raised to `le=10000`

### Task 2: Tests

**File:** `tests/test_api.py`

9 new tests:
- test_list_distinct_categories
- test_list_distinct_cities
- test_categories_route_not_matched_as_event_id
- test_list_multi_city_filter
- test_list_multi_category_and_semantics
- test_list_sort_by_city_asc
- test_list_sort_by_city_desc
- test_list_size_200_accepted
- test_list_size_10000_accepted

## Test Results

407 tests pass. 9 new tests added.

## Deviations

None — plan executed as written.

## Self-Check: PASSED
