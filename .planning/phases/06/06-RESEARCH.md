# Phase 6: Manual Review & Operations - Research

**Researched:** 2026-02-28
**Domain:** Review UI, audit trail, batch dashboard (FastAPI + React + SQLAlchemy)
**Confidence:** HIGH

## Summary

Phase 6 adds manual review operations (split, merge, review queue) and a batch processing dashboard to the existing event deduplication service. The codebase is well-structured with clear patterns: async FastAPI with SQLAlchemy ORM on the backend, React + TanStack Query + Tailwind CSS on the frontend, and Alembic for database migrations.

The core challenge is implementing split and merge operations that correctly manipulate the `canonical_events` / `canonical_event_sources` / `match_decisions` tables and then re-trigger canonical synthesis. The existing `synthesize_canonical()` function is a pure function that takes a list of source event dicts and returns a canonical dict -- this is directly reusable for re-synthesis after split/merge. The `enrich_canonical()` function adds downgrade prevention on top. Both are in `src/event_dedup/canonical/`.

The existing `CanonicalEvent` model already has `needs_review` (boolean) and `match_confidence` (float) fields, which provide the foundation for the review queue (REV-03). The `FileIngestion` and `AIUsageLog` tables already store processing metadata that can power the batch dashboard (REV-05). A new `AuditLog` table is needed for REV-04.

**Primary recommendation:** Add a new `audit_log` table and corresponding SQLAlchemy model, create new API route modules for review operations and dashboard stats, and build three new React pages (review queue, merge/split UI, dashboard) following the existing hand-crafted Tailwind component pattern.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| REV-01 | Manual split -- detach a source event from a canonical event (create new canonical or assign to another) | Split API endpoint manipulates `CanonicalEventSource` links and calls `synthesize_canonical()` to re-synthesize both affected canonicals. Existing `replace_canonical_events` persistence pattern shows how to create/update canonical events. |
| REV-02 | Manual merge -- combine two canonical events into one, re-synthesize canonical fields | Merge API endpoint reassigns all `CanonicalEventSource` links to target canonical, deletes the donor canonical, calls `synthesize_canonical()` on combined sources. Existing `enrich_canonical()` provides downgrade-prevention logic. |
| REV-03 | Review queue of low-confidence matches sorted by uncertainty | Existing `CanonicalEvent.needs_review` boolean and `match_confidence` float enable a simple query: `WHERE needs_review = True OR match_confidence < threshold ORDER BY match_confidence ASC`. |
| REV-04 | All manual override decisions logged with audit trail | New `audit_log` table with columns: id, action_type, canonical_event_id, source_event_id, operator, details (JSON), created_at. Follows existing model patterns. |
| REV-05 | Batch processing dashboard showing match rates, error rates, processing trends | Existing `FileIngestion` (status, event_count, ingested_at) and `AIUsageLog` (batch_id, costs) tables provide raw data. New aggregate API endpoints query and group this data by time period. |
</phase_requirements>

## Standard Stack

### Core (Already in Use -- No New Dependencies)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115 | API framework | Already used, async support, Pydantic schemas |
| SQLAlchemy | >=2.0 | ORM + async sessions | Already used with `mapped_column` pattern |
| Alembic | >=1.14 | Database migrations | Already configured at `config/alembic/` |
| Pydantic | >=2.9 | Request/response schemas | Already used with `model_validate`, `from_attributes` |
| React | ^19.2.0 | Frontend framework | Already used |
| TanStack Query | ^5.90.21 | Data fetching + cache | Already used for all API calls |
| react-router-dom | ^7.13.1 | Client-side routing | Already used for `/` and `/events/:id` |
| Tailwind CSS | ^4.2.1 | Styling | Already used, hand-crafted components |
| date-fns | ^4.1.0 | Date formatting | Already used |

### Supporting (No New Dependencies Needed)

No new npm or Python packages are required. The existing stack fully supports all Phase 6 requirements:

- **Mutations (split/merge)**: TanStack Query's `useMutation` hook handles POST/PUT/DELETE with cache invalidation -- already installed.
- **Charts for dashboard**: Use simple HTML/CSS bar representations with Tailwind (consistent with existing `ScoreBar` component in `ConfidenceIndicator.tsx`). A charting library is unnecessary for the simple metrics described in REV-05.
- **Audit logging**: Standard SQLAlchemy model + Alembic migration.

### Alternatives Considered

| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Hand-crafted Tailwind charts | recharts/chart.js | Adds dependency; existing ScoreBar pattern proves simple bars work. Only add if user wants time-series line charts. |
| JSON details column in audit_log | Separate audit detail tables | JSON is simpler, more flexible; PostgreSQL JSONB enables querying. Existing models already use sa.JSON for highlights, categories, field_provenance. |

## Architecture Patterns

### Backend: New Route Modules

```
src/event_dedup/api/routes/
  canonical_events.py    # (existing) GET list, GET detail
  health.py              # (existing) GET /health
  review.py              # (NEW) POST split, POST merge, GET review queue
  dashboard.py           # (NEW) GET stats, GET processing history
```

**Pattern:** Each router uses `APIRouter(prefix="/api/...", tags=[...])` and is registered in `app.py` via `app.include_router()`. Dependencies are injected via `Depends(get_db)` yielding an `AsyncSession`.

### Backend: New Model

```
src/event_dedup/models/
  audit_log.py           # (NEW) AuditLog model
```

**Pattern:** All models inherit from `Base` (in `models/base.py`), use `Mapped` type annotations with `mapped_column`, and are registered in `models/__init__.py`. The `Base.metadata` has a naming convention for constraints.

### Frontend: New Pages and Components

```
frontend/src/
  components/
    ReviewQueue.tsx       # (NEW) List of low-confidence events
    MergeDialog.tsx       # (NEW) Modal/inline merge two canonicals
    SplitDialog.tsx       # (NEW) Modal/inline detach source from canonical
    Dashboard.tsx         # (NEW) Batch processing stats
    AuditTrail.tsx        # (NEW) Audit log display for an event
  hooks/
    useReview.ts          # (NEW) TanStack Query hooks for review operations
    useDashboard.ts       # (NEW) TanStack Query hooks for dashboard stats
  api/
    client.ts             # (EXTEND) Add review and dashboard API functions
  types/
    index.ts              # (EXTEND) Add review and dashboard types
  App.tsx                 # (EXTEND) Add new routes
```

### Pattern: API Mutation with TanStack Query

```typescript
// Source: TanStack Query docs (useMutation pattern used in this project)
import { useMutation, useQueryClient } from '@tanstack/react-query';

export function useSplitEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: (params: SplitRequest) => splitEvent(params),
    onSuccess: () => {
      // Invalidate affected queries so UI refreshes
      queryClient.invalidateQueries({ queryKey: ['canonical-events'] });
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });
}
```

### Pattern: Async SQLAlchemy Transaction (existing codebase pattern)

```python
# Source: worker/persistence.py pattern
async with session.begin():
    # All operations in a single transaction
    # Step 1: Modify CanonicalEventSource links
    # Step 2: Re-synthesize canonical
    # Step 3: Create audit log entry
    # Commit happens automatically at end of `begin()` block
```

### Anti-Patterns to Avoid

- **Non-transactional split/merge:** Split and merge MUST be atomic. If re-synthesis fails after link changes, the DB is left inconsistent. Always use `async with session.begin()` to wrap the full operation.
- **Re-running the full pipeline after manual operations:** The existing `replace_canonical_events` does a full clear-and-replace. Manual operations must NOT trigger this -- they should surgically update only the affected canonical events.
- **Storing operator identity in the API without a mechanism:** The codebase has no authentication (explicitly out of scope per REQUIREMENTS.md). The audit trail should accept an `operator` string parameter in the request body, defaulting to "system" or "anonymous".
- **Building a separate source-event-to-dict conversion for synthesis:** The `load_all_events_as_dicts` function in `worker/persistence.py` already converts SQLAlchemy `SourceEvent` objects to the dict format that `synthesize_canonical()` expects. Extract a reusable `source_event_to_dict()` helper rather than duplicating this logic.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Canonical re-synthesis | Custom field merging for split/merge | `synthesize_canonical()` from `canonical/synthesizer.py` | Already handles all 15+ field strategies, provenance tracking, date union. Tested. |
| Downgrade prevention | Manual field comparison | `enrich_canonical()` from `canonical/enrichment.py` | Handles text field length comparison and version increment. |
| Source event dict conversion | Inline dict comprehension | Extract helper from `worker/persistence.py:load_all_events_as_dicts` | 30+ field mapping with date sub-object conversion -- error-prone to duplicate. |
| Cache invalidation | Manual refetch on mutation | TanStack Query `invalidateQueries` | Built-in, handles stale data, loading states, error states. |
| Paginated responses | Custom pagination logic | Existing `PaginatedResponse[T]` generic from `api/schemas.py` | Already tested, consistent with existing API. |

**Key insight:** The biggest risk in this phase is incorrectly reimplementing canonical synthesis logic. The `synthesize_canonical()` function is a pure function that takes `list[dict]` and returns a `dict` -- it can be called directly after any link manipulation without needing the full pipeline.

## Common Pitfalls

### Pitfall 1: Orphaned Source Events After Split

**What goes wrong:** After splitting a source event from a canonical, if the canonical has only one remaining source, its `source_count` and `match_confidence` become stale. If the canonical has zero remaining sources, it becomes an empty shell.
**Why it happens:** The split operation only removes the `CanonicalEventSource` link but forgets to update the canonical event itself.
**How to avoid:** After removing the link, check remaining source count. If 0, delete the canonical event. If 1+, re-synthesize the canonical from remaining sources.
**Warning signs:** `source_count` on canonical events doesn't match actual `COUNT(canonical_event_sources)`.

### Pitfall 2: Merge Creates Duplicate Source Links

**What goes wrong:** When merging canonical A into canonical B, if both already share a source event (rare but possible in manual correction scenarios), the unique constraint `uq_canonical_event_sources_pair` will cause a database error.
**Why it happens:** The merge blindly reassigns all links from A to B without checking for duplicates.
**How to avoid:** Before reassigning, query existing links on the target canonical. Use `INSERT ... ON CONFLICT DO NOTHING` or check-then-insert pattern.
**Warning signs:** IntegrityError on merge operations.

### Pitfall 3: Review Queue Becomes Stale After Manual Actions

**What goes wrong:** An operator splits/merges events, but the review queue still shows the old canonical events.
**Why it happens:** The review queue is based on `needs_review` flag and `match_confidence` which aren't updated after manual operations.
**How to avoid:** After any split/merge, explicitly set `needs_review = False` on the affected canonical events (the operator has reviewed them). Invalidate the review queue query cache on the frontend.
**Warning signs:** Review queue shows events that have already been manually corrected.

### Pitfall 4: Audit Log Missing Context for Undo/Review

**What goes wrong:** Audit entries say "split happened" but don't capture enough context to understand or undo the action.
**Why it happens:** Only storing action type and IDs without before/after state.
**How to avoid:** Store a `details` JSON column with before/after snapshots: which source events were involved, what the canonical looked like before the change, what it looks like after.
**Warning signs:** Operators can see the audit trail but can't understand what changed.

### Pitfall 5: Dashboard Queries Become Slow on Large Datasets

**What goes wrong:** Dashboard aggregation queries (GROUP BY date, COUNT, AVG) scan the entire `file_ingestions` and `match_decisions` tables.
**Why it happens:** No indexes on timestamp columns used for grouping.
**How to avoid:** Add indexes on `file_ingestions.ingested_at` and `match_decisions.decided_at`. Use date-truncated grouping with `DATE_TRUNC('day', ingested_at)`.
**Warning signs:** Dashboard page takes >2 seconds to load.

## Code Examples

### Example 1: Split Operation (Backend)

```python
# Pattern derived from existing persistence.py and synthesizer.py
from event_dedup.canonical.synthesizer import synthesize_canonical
from event_dedup.models.audit_log import AuditLog

async def split_source_from_canonical(
    session: AsyncSession,
    canonical_event_id: int,
    source_event_id: str,
    target_canonical_id: int | None,  # None = create new
    operator: str = "anonymous",
) -> dict:
    """Detach a source event from its canonical, optionally assigning to another."""

    async with session.begin():
        # 1. Remove the link
        link = await session.execute(
            sa.select(CanonicalEventSource).where(
                CanonicalEventSource.canonical_event_id == canonical_event_id,
                CanonicalEventSource.source_event_id == source_event_id,
            )
        )
        link_row = link.scalar_one_or_none()
        if not link_row:
            raise HTTPException(404, "Source event not linked to this canonical")
        await session.delete(link_row)

        # 2. Re-synthesize the original canonical (or delete if empty)
        remaining_links = await session.execute(
            sa.select(CanonicalEventSource).where(
                CanonicalEventSource.canonical_event_id == canonical_event_id
            ).options(selectinload(CanonicalEventSource.source_event))
        )
        remaining = remaining_links.scalars().all()

        if len(remaining) == 0:
            # Delete the now-empty canonical
            await session.execute(
                sa.delete(CanonicalEvent).where(CanonicalEvent.id == canonical_event_id)
            )
        else:
            # Re-synthesize from remaining sources
            source_dicts = [source_event_to_dict(r.source_event) for r in remaining]
            new_canonical_data = synthesize_canonical(source_dicts)
            # Update the canonical event fields...

        # 3. Handle the detached source event
        if target_canonical_id:
            # Assign to existing canonical
            new_link = CanonicalEventSource(
                canonical_event_id=target_canonical_id,
                source_event_id=source_event_id,
            )
            session.add(new_link)
            # Re-synthesize target canonical...
        else:
            # Create new singleton canonical
            source_event = await session.get(SourceEvent, source_event_id)
            source_dict = source_event_to_dict(source_event)
            new_canonical_data = synthesize_canonical([source_dict])
            # Create new CanonicalEvent + link...

        # 4. Audit log
        audit = AuditLog(
            action_type="split",
            canonical_event_id=canonical_event_id,
            source_event_id=source_event_id,
            operator=operator,
            details={
                "target_canonical_id": target_canonical_id,
                "remaining_sources": len(remaining),
            },
        )
        session.add(audit)
```

### Example 2: Review Queue Query

```python
# Follows existing list_canonical_events pattern in routes/canonical_events.py
@router.get("/api/review/queue", response_model=PaginatedResponse[CanonicalEventSummary])
async def get_review_queue(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
) -> PaginatedResponse[CanonicalEventSummary]:
    """Low-confidence matches sorted by uncertainty (most ambiguous first)."""
    stmt = (
        sa.select(CanonicalEvent)
        .where(
            sa.or_(
                CanonicalEvent.needs_review == True,
                sa.and_(
                    CanonicalEvent.match_confidence.isnot(None),
                    CanonicalEvent.match_confidence < 0.8,
                    CanonicalEvent.source_count > 1,
                ),
            )
        )
        .order_by(
            # needs_review first, then lowest confidence
            CanonicalEvent.needs_review.desc(),
            sa.func.coalesce(CanonicalEvent.match_confidence, 0.0).asc(),
        )
    )
    # ... pagination follows existing pattern ...
```

### Example 3: AuditLog Model

```python
# Follows existing model patterns (Base, Mapped, mapped_column)
class AuditLog(Base):
    __tablename__ = "audit_log"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    action_type: Mapped[str] = mapped_column(sa.String)  # "split", "merge", "override"
    canonical_event_id: Mapped[int | None] = mapped_column(
        sa.Integer, sa.ForeignKey("canonical_events.id", ondelete="SET NULL"), nullable=True
    )
    source_event_id: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    operator: Mapped[str] = mapped_column(sa.String, default="anonymous")
    details: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP")
    )

    __table_args__ = (
        sa.CheckConstraint(
            "action_type IN ('split', 'merge', 'override', 'review_approve', 'review_dismiss')",
            name="valid_action_type",
        ),
    )
```

### Example 4: Dashboard Stats Query

```python
# Aggregate file ingestion stats for dashboard
@router.get("/api/dashboard/stats")
async def get_dashboard_stats(
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> dict:
    cutoff = datetime.utcnow() - timedelta(days=days)

    # File processing stats
    file_stats = await db.execute(
        sa.select(
            sa.func.count(FileIngestion.id).label("total_files"),
            sa.func.sum(FileIngestion.event_count).label("total_events"),
            sa.func.count(
                sa.case((FileIngestion.status == "completed", 1))
            ).label("completed"),
            sa.func.count(
                sa.case((FileIngestion.status == "error", 1))
            ).label("errors"),
        ).where(FileIngestion.ingested_at >= cutoff)
    )

    # Match decision distribution
    match_stats = await db.execute(
        sa.select(
            MatchDecision.decision,
            sa.func.count().label("count"),
        ).group_by(MatchDecision.decision)
    )

    # Canonical event summary
    canonical_stats = await db.execute(
        sa.select(
            sa.func.count(CanonicalEvent.id).label("total"),
            sa.func.count(
                sa.case((CanonicalEvent.needs_review == True, 1))
            ).label("needs_review"),
            sa.func.avg(CanonicalEvent.match_confidence).label("avg_confidence"),
        )
    )

    return {
        "files": dict(file_stats.one()._mapping),
        "matches": {row.decision: row.count for row in match_stats},
        "canonicals": dict(canonical_stats.one()._mapping),
    }
```

### Example 5: Source Event to Dict Helper

```python
# Extract from worker/persistence.py:load_all_events_as_dicts
# to avoid code duplication in review operations
def source_event_to_dict(evt: SourceEvent) -> dict:
    """Convert a SourceEvent ORM object to a dict for synthesize_canonical()."""
    return {
        "id": evt.id,
        "title": evt.title,
        "short_description": evt.short_description,
        "description": evt.description,
        "highlights": evt.highlights,
        "location_name": evt.location_name,
        "location_city": evt.location_city,
        "location_district": evt.location_district,
        "location_street": evt.location_street,
        "location_zipcode": evt.location_zipcode,
        "geo_latitude": evt.geo_latitude,
        "geo_longitude": evt.geo_longitude,
        "geo_confidence": evt.geo_confidence,
        "source_code": evt.source_code,
        "source_type": evt.source_type,
        "categories": evt.categories,
        "is_family_event": evt.is_family_event,
        "is_child_focused": evt.is_child_focused,
        "admission_free": evt.admission_free,
        "dates": [
            {
                "date": str(d.date),
                "start_time": str(d.start_time) if d.start_time else None,
                "end_time": str(d.end_time) if d.end_time else None,
                "end_date": str(d.end_date) if d.end_date else None,
            }
            for d in evt.dates
        ],
    }
```

### Example 6: Frontend Mutation Hook

```typescript
// Pattern: TanStack Query mutation with cache invalidation
// Follows existing useCanonicalEvents.ts pattern

import { useMutation, useQuery, useQueryClient, keepPreviousData } from '@tanstack/react-query';
import { fetchReviewQueue, splitEvent, mergeEvents } from '../api/client';

export function useReviewQueue(page: number, size: number = 20) {
  return useQuery({
    queryKey: ['review-queue', page, size],
    queryFn: () => fetchReviewQueue(page, size),
    placeholderData: keepPreviousData,
  });
}

export function useSplitEvent() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: splitEvent,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canonical-events'] });
      queryClient.invalidateQueries({ queryKey: ['canonical-event'] });
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });
}

export function useMergeEvents() {
  const queryClient = useQueryClient();
  return useMutation({
    mutationFn: mergeEvents,
    onSuccess: () => {
      queryClient.invalidateQueries({ queryKey: ['canonical-events'] });
      queryClient.invalidateQueries({ queryKey: ['canonical-event'] });
      queryClient.invalidateQueries({ queryKey: ['review-queue'] });
    },
  });
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Full pipeline re-run after manual edit | Surgical update of affected canonicals only | This phase | Avoids O(n^2) matching for a single edit |
| No audit trail | JSON-detail audit log table | This phase | Enables traceability for all manual operations |
| needs_review boolean only | needs_review + match_confidence threshold for queue | This phase | Enables prioritized review workflow |

**Key design decision:** Manual operations (split/merge) should NOT re-run the full matching pipeline. They should only re-synthesize the affected canonical events using the existing `synthesize_canonical()` pure function. This keeps manual operations fast (milliseconds, not seconds) and avoids changing unrelated canonical events.

## API Endpoint Design

Based on existing patterns in `routes/canonical_events.py`:

### New Endpoints

| Method | Path | Purpose | Request Body |
|--------|------|---------|-------------|
| POST | `/api/review/split` | Split source from canonical | `{ canonical_event_id, source_event_id, target_canonical_id?, operator? }` |
| POST | `/api/review/merge` | Merge two canonicals | `{ source_canonical_id, target_canonical_id, operator? }` |
| GET | `/api/review/queue` | Review queue (paginated) | Query params: `page`, `size`, `min_sources` |
| GET | `/api/review/queue/{id}/approve` | Mark as reviewed/approved | - |
| POST | `/api/review/queue/{id}/dismiss` | Dismiss from review queue | `{ operator?, reason? }` |
| GET | `/api/audit-log` | List audit entries | Query params: `page`, `size`, `canonical_event_id?`, `action_type?` |
| GET | `/api/dashboard/stats` | Aggregate dashboard stats | Query params: `days` |
| GET | `/api/dashboard/processing-history` | Time-series processing data | Query params: `days`, `granularity` |

### Response Schemas (following existing Pydantic patterns)

```python
class SplitRequest(BaseModel):
    canonical_event_id: int
    source_event_id: str
    target_canonical_id: int | None = None
    operator: str = "anonymous"

class MergeRequest(BaseModel):
    source_canonical_id: int  # This one gets deleted
    target_canonical_id: int  # This one survives
    operator: str = "anonymous"

class SplitResponse(BaseModel):
    original_canonical_id: int
    new_canonical_id: int | None  # If created
    target_canonical_id: int | None  # If assigned to existing

class MergeResponse(BaseModel):
    surviving_canonical_id: int
    deleted_canonical_id: int
    new_source_count: int

class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    action_type: str
    canonical_event_id: int | None
    source_event_id: str | None
    operator: str
    details: dict | None
    created_at: str
```

## Database Migration

New migration file `004_add_audit_log.py` following the existing pattern:

```python
# Revision: 004_audit_log
# Revises: 003_ai_matching

def upgrade() -> None:
    op.create_table(
        "audit_log",
        sa.Column("id", sa.Integer(), primary_key=True, autoincrement=True),
        sa.Column("action_type", sa.String(), nullable=False),
        sa.Column("canonical_event_id", sa.Integer(),
                  sa.ForeignKey("canonical_events.id", ondelete="SET NULL"), nullable=True),
        sa.Column("source_event_id", sa.String(), nullable=True),
        sa.Column("operator", sa.String(), nullable=False, server_default="anonymous"),
        sa.Column("details", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(), server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.CheckConstraint(
            "action_type IN ('split', 'merge', 'override', 'review_approve', 'review_dismiss')",
            name="ck_audit_log_valid_action_type",
        ),
    )
    op.create_index("ix_audit_log_canonical_event_id", "audit_log", ["canonical_event_id"])
    op.create_index("ix_audit_log_created_at", "audit_log", ["created_at"])

    # Add index for dashboard queries
    op.create_index("ix_file_ingestions_ingested_at", "file_ingestions", ["ingested_at"])
    op.create_index("ix_match_decisions_decided_at", "match_decisions", ["decided_at"])
```

## Frontend Routing Plan

Extend `App.tsx` with new routes:

```typescript
<Routes>
  <Route path="/" element={<EventList />} />
  <Route path="/events/:id" element={<EventDetail />} />
  <Route path="/review" element={<ReviewQueue />} />       {/* NEW */}
  <Route path="/dashboard" element={<Dashboard />} />     {/* NEW */}
</Routes>
```

Add navigation links in the header for Review Queue and Dashboard.

## Open Questions

1. **Merge target selection UX**
   - What we know: The merge operation needs two canonical event IDs. The API is straightforward.
   - What's unclear: How does the operator select the second canonical to merge with? Options: (a) search dialog on the event detail page, (b) checkbox selection on the event list page, (c) "merge with" button that opens a search.
   - Recommendation: Add a "Merge with..." button on the event detail page that opens a search dialog. This is the simplest UX and matches the existing detail-page workflow.

2. **Split destination UX**
   - What we know: Split can either create a new singleton canonical or assign to an existing one.
   - What's unclear: How to present the "assign to existing" option.
   - Recommendation: Default to creating a new canonical (simpler). Offer an optional "assign to existing" with a search input. Most splits will be corrections where the source shouldn't have been matched at all, so new-canonical is the common case.

3. **Dashboard granularity**
   - What we know: REV-05 asks for "match rates, error rates, and processing trends over time."
   - What's unclear: What time granularity and what specific metrics.
   - Recommendation: Start with daily granularity for the last 30 days. Metrics: files processed per day, events ingested per day, match/ambiguous/no_match counts, average confidence, error count.

## Sources

### Primary (HIGH confidence)
- Codebase analysis of all source files at `/Users/svenkarl/workspaces/event-deduplication/src/event_dedup/` -- models, API routes, canonical synthesizer, worker persistence, matching pipeline
- Codebase analysis of frontend at `/Users/svenkarl/workspaces/event-deduplication/frontend/src/` -- App.tsx, components, hooks, types, API client
- Existing Alembic migrations at `config/alembic/versions/` -- migration patterns
- REQUIREMENTS.md at `.planning/REQUIREMENTS.md` -- REV-01 through REV-05 definitions

### Secondary (MEDIUM confidence)
- TanStack Query v5 useMutation patterns -- well-known, verified against package.json version

### Tertiary (LOW confidence)
- None. All findings are based on direct codebase analysis.

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies; everything is already in the codebase
- Architecture: HIGH - Patterns directly extracted from existing routes, models, and components
- Pitfalls: HIGH - Identified from analyzing the specific data model relationships and constraints
- API design: HIGH - Follows existing FastAPI patterns exactly
- Frontend: HIGH - Follows existing React/TanStack Query/Tailwind patterns exactly

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable -- no external dependency changes expected)
