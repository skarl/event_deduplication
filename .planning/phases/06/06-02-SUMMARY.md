---
phase: 06-review-operations
plan: 02
subsystem: review-frontend
tags: [review-ui, dashboard, split, merge, audit-trail, react, tanstack-query]
dependency_graph:
  requires: [review-operations, audit-log-model, dashboard-api, frontend-framework]
  provides: [review-queue-page, split-dialog, merge-dialog, audit-trail-component, dashboard-page]
  affects: [event-detail-page, app-navigation]
tech_stack:
  added: []
  patterns: [debounced-search, modal-dialogs, mutation-invalidation, url-search-params]
key_files:
  created:
    - frontend/src/hooks/useReview.ts
    - frontend/src/hooks/useDashboard.ts
    - frontend/src/components/ReviewQueue.tsx
    - frontend/src/components/SplitDialog.tsx
    - frontend/src/components/MergeDialog.tsx
    - frontend/src/components/AuditTrail.tsx
    - frontend/src/components/Dashboard.tsx
  modified:
    - frontend/src/types/index.ts
    - frontend/src/api/client.ts
    - frontend/src/components/EventDetail.tsx
    - frontend/src/App.tsx
decisions:
  - "Nginx config already proxies all /api/* sub-paths -- no changes needed for new endpoints"
  - "Debounced search (300ms) with useQuery for canonical event search in split/merge dialogs"
  - "MergeDialog navigates to surviving event after merge since current event is deleted"
  - "Split buttons only shown when 2+ sources (single source split is meaningless)"
  - "Merge button always visible regardless of source count"
metrics:
  duration: 4m
  completed: 2026-02-28
  tasks: 3/3
  files_created: 7
  files_modified: 4
---

# Phase 6 Plan 02: Frontend Review UI and Dashboard Summary

Review queue page, split/merge modal dialogs with debounced canonical search, audit trail timeline, and processing dashboard with stats cards and bar charts -- all wired into EventDetail and App routes with TanStack Query cache invalidation.

## Tasks Completed

### Task 1: Types, API client, hooks, and nginx config
**Commit:** 58c896e

- Extended `types/index.ts` with 13 new interfaces: SplitRequest/Response, MergeRequest/Response, DismissRequest, AuditLogEntry, FileProcessingStats, MatchDistribution, CanonicalStats, DashboardStats, ProcessingHistoryEntry
- Extended `api/client.ts` with 8 new functions: fetchReviewQueue, splitEvent, mergeEvents, dismissFromQueue, fetchAuditLog, fetchDashboardStats, fetchProcessingHistory, searchCanonicalEvents
- Created `useReview.ts` with 5 hooks: useReviewQueue (paginated), useSplitEvent, useMergeEvents, useDismissEvent (all with multi-query invalidation), useAuditLog
- Created `useDashboard.ts` with 2 hooks: useDashboardStats, useProcessingHistory
- Verified nginx config already proxies all `/api/*` sub-paths via existing `location /api/` block

### Task 2: ReviewQueue, SplitDialog, MergeDialog, AuditTrail, Dashboard components
**Commit:** f2a1b4d

- **ReviewQueue**: Paginated table with confidence color coding (red/yellow/green), needs_review badge, dismiss button, URL search params for page state
- **SplitDialog**: Modal with radio choice between "create new canonical" and "assign to existing" with debounced search (300ms), selected target highlight, operator field, error display
- **MergeDialog**: Modal with debounced canonical search, direction indicator ("Merging X INTO Y"), orange destructive action button, navigates to surviving event on success
- **AuditTrail**: Timeline with color-coded left border (blue=split, green=merge, gray=dismiss), action badges, operator name, formatted timestamps, detail summaries
- **Dashboard**: Time range selector (7/30/90 days), stats cards grid (files/events/canonicals/confidence), match distribution horizontal bars (green/gray/yellow), processing history with daily file/event bars and error indicators

### Task 3: Wire components into EventDetail and App routes/navigation
**Commit:** 3ac2015

- **EventDetail**: Added "Merge with..." button in header section, per-source "Split" buttons below SourceComparison (only when 2+ sources), Audit Trail section at bottom, SplitDialog/MergeDialog rendered conditionally via state
- **App.tsx**: Added `/review` and `/dashboard` routes, navigation header with Events/Review Queue/Dashboard links using `<Link>` components

## Deviations from Plan

None -- plan executed exactly as written. Nginx config confirmed to already cover all `/api/*` sub-paths (no modification needed as anticipated by the plan).

## Self-Check: PASSED

All 11 files verified present. All 3 commit hashes (58c896e, f2a1b4d, 3ac2015) confirmed in git log. TypeScript compilation and Vite production build both succeed.
