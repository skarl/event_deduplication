# Phase 6: Manual Review & Operations - UAT

**Phase Goal:** Operators can correct grouping mistakes and monitor system health through the review UI
**Session Started:** 2026-02-28
**Status:** PASSED (2 issues found and fixed)

## Test Results

| # | Test | Criterion | Result | Notes |
|---|------|-----------|--------|-------|
| 1 | Split: detach source, create new canonical | REV-01 | PASS | Detached pdf-9d58bea1-0-1 from #5843 (5->4 sources), new #6280 created with 1 source |
| 2 | Split: detach source, assign to existing + auto-delete | REV-01 | PASS | Moved source from #6280 back to #5843 (4->5 sources), empty #6280 auto-deleted |
| 3 | Merge: combine two canonicals | REV-02 | PASS | Merged #5950 into #5917, donor deleted, target has 2 sources, re-synthesized |
| 4 | Review queue: sorted by uncertainty | REV-03 | PASS | 26 items, sorted by confidence ascending (0.761, 0.773, 0.787...) |
| 5 | Audit trail: all operations logged | REV-04 | PASS | 3 entries (2 splits, 1 merge) with operator, timestamps, details JSON. Filtering works. |
| 6 | Dashboard: stats and processing trends | REV-05 | PASS | Stats: 20 files/765 events/294 matches/950 ambiguous. History: daily data. |
| 7 | Frontend: routes + nginx proxy | UI | PASS | /review, /dashboard, all /api/* endpoints return 200 via nginx |
| 8 | Frontend: JS bundle includes components | UI | PASS | ReviewQueue, Dashboard, Split, Merge, AuditTrail all in production bundle |
| 9 | Dismiss from review queue | REV-03 | PASS | Dismissed #5728, queue 26->25, confidence set to 1.0 (manually verified) |
| 10-12 | Frontend visual verification | UI | SKIPPED | Deferred -- user accepted API-level verification |

## Issues Found & Fixed

### Issue 1: Timezone-aware datetime vs naive PostgreSQL column (FIXED)
- **Found:** Test 1 (split operation returned 500)
- **Root cause:** `datetime.now(dt.UTC)` in `update_canonical_from_dict` creates timezone-aware datetime, but `canonical_events.updated_at` is `TIMESTAMP WITHOUT TIME ZONE`
- **Fix:** Changed to `datetime.now(dt.UTC).replace(tzinfo=None)` in `helpers.py`

### Issue 2: Dismiss doesn't remove from low-confidence queue (FIXED)
- **Found:** Dismiss test -- event remained in queue
- **Root cause:** Queue shows items matching `needs_review=True OR (match_confidence < 0.8 AND source_count > 1)`. Dismiss only set `needs_review=False`, not `match_confidence`.
- **Fix:** On dismiss, set `match_confidence=1.0` (manually verified) when original was < 0.8. Original confidence preserved in audit details.

## Test Details

### Test 1: Split - Create new canonical
```
POST /api/review/split {canonical_event_id: 5843, source_event_id: "pdf-9d58bea1-0-1"}
Response: {original_canonical_id: 5843, new_canonical_id: 6280, original_deleted: false}
Verified: #5843 has 4 sources, #6280 has 1 source "Politischer Aschermittwoch"
```

### Test 2: Split - Assign to existing + auto-delete empty
```
POST /api/review/split {canonical_event_id: 6280, source_event_id: "pdf-9d58bea1-0-1", target_canonical_id: 5843}
Response: {original_canonical_id: 6280, target_canonical_id: 5843, original_deleted: true}
Verified: #5843 has 5 sources again, #6280 returns 404 (deleted)
```

### Test 3: Merge
```
POST /api/review/merge {source_canonical_id: 5950, target_canonical_id: 5917}
Response: {surviving_canonical_id: 5917, deleted_canonical_id: 5950, new_source_count: 2}
Verified: #5917 has 2 sources, #5950 returns 404
```

### Test 4: Review queue
```
GET /api/review/queue?page=1&size=5
26 items, sorted ascending: [0.761, 0.773, 0.787, 0.790, 0.791]
```

### Test 5: Audit trail
```
GET /api/audit-log
3 entries: split (new canonical), split (to existing, delete empty), merge
All with operator="uat-test", timestamps, and details JSON
Filtering by action_type=split returns 2, action_type=merge returns 1
```

### Test 6: Dashboard
```
GET /api/dashboard/stats?days=30
{files: {total: 20, events: 765, completed: 20, errors: 0},
 matches: {match: 294, no_match: 94, ambiguous: 950},
 canonicals: {total: 555, needs_review: 0, avg_confidence: 0.8897}}

GET /api/dashboard/processing-history?days=30
[{date: "2026-02-28", files_processed: 20, events_ingested: 765, errors: 0}]
```
