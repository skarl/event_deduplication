---
phase: 11-frontend-ux
plan: 02
subsystem: frontend-ux
tags: [frontend, react, chip-selector, sorting, pagination]
dependency_graph:
  requires: [11-01]
  provides: [chip-selector, sortable-headers, page-size-selector]
  affects: [event-list, search-filters, pagination]
tech_stack:
  added: []
  patterns: [controlled-component, url-state, autocomplete-dropdown]
key_files:
  created:
    - frontend/src/components/ChipSelector.tsx
  modified:
    - frontend/src/types/index.ts
    - frontend/src/api/client.ts
    - frontend/src/hooks/useCanonicalEvents.ts
    - frontend/src/components/SearchFilters.tsx
    - frontend/src/components/Pagination.tsx
    - frontend/src/components/EventList.tsx
decisions:
  - ChipSelector as controlled component (parent owns selected state)
  - size=0 in UI maps to size=10000 for API (ALL sentinel)
  - No component library — native HTML + Tailwind for chips and dropdowns
  - onMouseDown (not onClick) on dropdown items to prevent blur timing issue
  - Sort state in URL params for shareable/bookmarkable URLs
metrics:
  duration: ~3m
  completed: 2026-02-28
  tasks_completed: 2
  tasks_total: 2
  files_created: 1
  files_modified: 6
---

# Phase 11 Plan 2: Frontend — ChipSelector, Sorting, Page Size, and Filter Wiring

Built four UX improvements: chip/tag selectors for city and category filters, sortable column headers on all 7 table columns, and configurable rows-per-page selector.

## What Was Built

### Task 1: Types, API client, and hooks

- Added `SortColumn` and `SortDir` type aliases to `types/index.ts`
- Updated `EventFilters` interface: `cities?: string[]`, `categories?: string[]`, `sort_by`, `sort_dir`
- Added `fetchDistinctCategories()` and `fetchDistinctCities()` to `client.ts`
- Updated `fetchCanonicalEvents()` with multi-value params and sort
- Added `useDistinctCategories()` and `useDistinctCities()` hooks (5min staleTime)

### Task 2: Components

**ChipSelector.tsx** (new) — Reusable autocomplete chip selector:
- Controlled component with `selected`/`onChange` props
- Autocomplete dropdown filtering available options
- Removable chips with "x" button
- onMouseDown for blur-safe selection

**SearchFilters.tsx** — Replaced city/category text inputs with ChipSelector:
- City ChipSelector populated from `/cities` endpoint
- Category ChipSelector populated from `/categories` endpoint
- Chip changes apply immediately (no form submit required)

**Pagination.tsx** — Added rows-per-page selector:
- Options: 25, 50, 100, 200, ALL
- `size`/`onSizeChange` props

**EventList.tsx** — Full refactor:
- `SortableHeader` component with click-to-sort and direction indicators
- All 7 columns sortable (title, city, date, categories, sources, confidence, review)
- Size state from URL params, 0 → 10000 conversion for API
- Page reset on size change

## Verification

- TypeScript compiles clean (`npx tsc --noEmit`)
- Frontend build succeeds (`npm run build`)

## Deviations

None — plan executed as written.

## Self-Check: PASSED
