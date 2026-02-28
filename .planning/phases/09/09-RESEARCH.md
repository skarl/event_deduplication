# Phase 9: AI Matching Verification & Indicators - Research

**Researched:** 2026-02-28
**Domain:** AI matching pipeline verification, database schema extension, full-stack indicator display
**Confidence:** HIGH

## Summary

Phase 9 adds end-to-end verification of AI matching and surfaces AI involvement throughout the system. The codebase already has a fully functional AI matching pipeline (resolver, client, cache, cost tracker) with comprehensive unit tests. What's missing is: (1) an end-to-end integration test that exercises the full flow with mocked Gemini, (2) an `ai_assisted` boolean on `CanonicalEvent` that tracks whether AI was involved, (3) frontend display of AI indicators in the event list and detail pages, and (4) visual distinction of `"ai"` and `"ai_low_confidence"` tiers in the ConfidenceIndicator component.

The data flow is clear: the resolver sets `tier="ai"` or `tier="ai_low_confidence"` on `MatchDecisionRecord`, these are persisted to `MatchDecision.tier` in the database (no DB constraint on tier values), and the pipeline already passes tier through clustering and persistence. The key gap is propagating AI involvement from match decisions up to canonical events during synthesis/persistence, and exposing it via the API and frontend.

**Primary recommendation:** Add `ai_assisted` column to `CanonicalEvent` model + Alembic migration, compute it in the persistence layer by checking if any match decision in the cluster has an AI tier, extend API schemas and frontend types, and add visual indicators in EventList and ConfidenceIndicator.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| AIM-01 | End-to-end integration test for AI matching flow | Existing test infrastructure (conftest.py fixtures, mocked Gemini pattern in test_ai_resolver.py), full pipeline path through orchestrator._maybe_resolve_ai -> resolver -> cache/cost_tracker |
| AIM-02 | `ai_assisted` boolean field on CanonicalEvent | CanonicalEvent model at line 18, Alembic migration pattern (006_*), persistence.py replace_canonical_events at line 73, pipeline.py canonical_events dict construction |
| AIM-03 | AI indicator in frontend event list and detail page | EventList.tsx table structure, EventDetail.tsx header section, CanonicalEventSummary/Detail types, API schemas |
| AIM-04 | Visual distinction of `"ai"` and `"ai_low_confidence"` tiers in ConfidenceIndicator | ConfidenceIndicator.tsx line 61 already displays `d.tier`, MatchDecision type has `tier: string` |
</phase_requirements>

## Current State

### 1. CanonicalEvent Model (`src/event_dedup/models/canonical_event.py`)

The model has 26 columns including provenance, quality, and timestamp fields. There is NO `ai_assisted` field yet. Key existing fields relevant to this phase:
- `match_confidence: Mapped[float | None]` -- average cluster confidence score
- `needs_review: Mapped[bool]` -- flags incoherent clusters
- `source_count: Mapped[int]` -- number of source events
- `field_provenance: Mapped[dict | None]` -- which source contributed each field

The model uses SQLAlchemy 2.0 declarative mapped_column style with `Base` from `event_dedup.models.base`.

### 2. MatchDecision Model (`src/event_dedup/models/match_decision.py`)

The `tier` field is `Mapped[str]` with default `"deterministic"`. There is NO CHECK constraint on tier values (only on `decision`), so `"ai"`, `"ai_low_confidence"`, and `"ai_unexpected"` values already work without any schema changes.

Current valid tier values set by code:
- `"deterministic"` -- default from `MatchDecisionRecord` dataclass
- `"ai"` -- set by `_apply_ai_result()` when confidence >= threshold
- `"ai_low_confidence"` -- set by `_apply_ai_result()` when confidence < threshold
- `"ai_unexpected"` -- set by `_apply_ai_result()` for unexpected AI decision values

### 3. AI Matching Module (`src/event_dedup/ai_matching/`)

Fully implemented with 6 modules:
- **resolver.py**: `resolve_ambiguous_pairs()` orchestrates the full flow -- filters ambiguous decisions, checks cache, calls Gemini, applies confidence threshold, returns updated `MatchResult`. Uses `_apply_ai_result()` to map AI decisions to pipeline decisions with appropriate tier values.
- **client.py**: `call_gemini()` async function using `google-genai` SDK with structured output (response_schema=AIMatchResult). Returns (AIMatchResult, prompt_tokens, completion_tokens).
- **cache.py**: Content-hash cache using SHA-256 of event pair content. `compute_pair_hash()`, `lookup_cache()`, `store_cache()`. Supports model staleness detection.
- **cost_tracker.py**: `estimate_cost()`, `log_usage()`, `get_batch_summary()`, `get_period_summary()`. Logs to `ai_usage_log` table.
- **schemas.py**: `AIMatchResult` Pydantic model with decision (same/different), confidence (0.0-1.0), reasoning.
- **prompt.py**: German event-specific system prompt and event pair formatting.

### 4. Matching Pipeline (`src/event_dedup/matching/pipeline.py`)

`MatchDecisionRecord` is a dataclass with `tier: str = "deterministic"`. The pipeline's `score_candidate_pairs()` creates decisions with default tier. After AI resolution, `_apply_ai_result()` in the resolver creates new `MatchDecisionRecord` instances with updated tier values.

Key functions:
- `run_full_pipeline()` -- deterministic scoring + clustering + synthesis
- `rebuild_pipeline_result()` -- re-clusters and re-synthesizes after AI resolution modifies decisions
- `_avg_cluster_confidence()` -- computes average combined_score for match decisions within a cluster

The canonical event dict built in `run_full_pipeline()` and `rebuild_pipeline_result()` includes `needs_review` and `match_confidence` but NOT `ai_assisted`. This is where `ai_assisted` computation should be added.

### 5. Clustering (`src/event_dedup/clustering/graph_cluster.py`)

Uses networkx connected components. Returns `ClusterResult` with `clusters` and `flagged_clusters` (both lists of `set[str]`). The clustering only uses `decision == "match"` edges and ignores tier. No changes needed here.

### 6. Synthesizer (`src/event_dedup/canonical/synthesizer.py`)

Pure function `synthesize_canonical()` merges source events into a canonical dict. Returns a dict with all merged fields, `field_provenance`, and `source_count`. Does NOT handle `ai_assisted` -- this field should be computed in the pipeline or persistence layer, not here, since it depends on match decisions (not source events).

### 7. Persistence Layer (`src/event_dedup/worker/persistence.py`)

`replace_canonical_events()` does a clear-and-replace: deletes all existing MatchDecision, CanonicalEventSource, and CanonicalEvent rows, then creates new ones from the `PipelineResult`. The `CanonicalEvent` creation (line 105-129) maps `canonical_dict` fields to ORM columns. This is where `ai_assisted` would need to be set from the canonical_dict.

`MatchDecision` creation (line 143-154) already persists `decision.tier` correctly.

### 8. Orchestrator (`src/event_dedup/worker/orchestrator.py`)

`_maybe_resolve_ai()` calls `resolve_ambiguous_pairs()` and then `rebuild_pipeline_result()` if any ambiguous pairs were resolved. The pipeline result flows to `replace_canonical_events()`. No changes needed in the orchestrator itself.

### 9. API Schemas (`src/event_dedup/api/schemas.py`)

- `CanonicalEventSummary` (list view): id, title, location_city, dates, categories, source_count, match_confidence, needs_review. No `ai_assisted`.
- `CanonicalEventDetail` (detail view): All fields + sources + match_decisions. No `ai_assisted`.
- `MatchDecisionSchema`: Includes `tier: str` -- already passes through to frontend.

### 10. API Routes (`src/event_dedup/api/routes/canonical_events.py`)

`list_canonical_events()` returns `PaginatedResponse[CanonicalEventSummary]` via `model_validate()`. `get_canonical_event()` queries match decisions for the source group and returns `CanonicalEventDetail`. Both will automatically include `ai_assisted` once added to models and schemas.

### 11. Frontend Types (`frontend/src/types/index.ts`)

- `CanonicalEventSummary`: No `ai_assisted` field
- `CanonicalEventDetail`: No `ai_assisted` field
- `MatchDecision`: Has `tier: string` already

### 12. Frontend EventList (`frontend/src/components/EventList.tsx`)

Table with columns: Title, City, Date, Categories, Sources, Confidence, Review. The AI badge should be added as a new indicator, likely next to the title or as a separate column.

### 13. Frontend EventDetail (`frontend/src/components/EventDetail.tsx`)

Header section shows source_count badge, confidence badge, and needs_review badge. AI badge should be added to this badge row. The Match Scores section already shows `ConfidenceIndicator` with match_decisions.

### 14. Frontend ConfidenceIndicator (`frontend/src/components/ConfidenceIndicator.tsx`)

Currently displays `{d.decision} ({d.tier})` as plain text (line 61-63). No visual distinction between tier values. This needs colored badges/labels for "ai" and "ai_low_confidence" tiers.

### 15. Existing Tests

- **test_ai_matching.py**: Tests schemas, config, cache hashing, cost estimation, prompt formatting, DB cache operations (store/lookup/staleness), usage logging. All self-contained (no API key needed).
- **test_ai_resolver.py**: Tests `_apply_ai_result()` and `resolve_ambiguous_pairs()` with mocked Gemini client. Tests: high/low confidence, API failure, cache hits, non-ambiguous unchanged.
- **scripts/test_ai_integration.py**: Manual integration test script that calls real Gemini API. NOT automated -- requires `GEMINI_API_KEY` env var.

### 16. Database Migration Pattern

Alembic is fully configured at `config/alembic.ini` with versions in `config/alembic/versions/`. The most recent migration is `005_add_config_settings.py`. Pattern:
- Sequential numbered prefixes: 001_, 002_, 003_, 004_, 005_
- Simple `op.create_table()` or `op.add_column()` calls
- `down_revision` chains: initial -> a621 -> fb9d -> 002 -> 003 -> 004 -> 005
- Docker entrypoint runs `alembic -c config/alembic.ini upgrade head` on startup

The next migration should be `006_add_ai_assisted_column.py` with `down_revision = "005_config_settings"`.

## Key Integration Points

### Data Flow for `ai_assisted` Flag

```
1. resolver._apply_ai_result() sets tier="ai" or "ai_low_confidence"
   on MatchDecisionRecord

2. rebuild_pipeline_result() re-clusters using updated decisions
   -> PipelineResult.match_result.decisions contains AI-resolved records

3. pipeline._avg_cluster_confidence() and canonical dict construction
   -> HERE: compute ai_assisted per canonical event by checking if any
      match decision within the cluster has tier starting with "ai"

4. persistence.replace_canonical_events() creates CanonicalEvent from dict
   -> Maps canonical_dict["ai_assisted"] to CanonicalEvent.ai_assisted column

5. API routes return CanonicalEvent via schemas
   -> CanonicalEventSummary/Detail include ai_assisted field

6. Frontend types receive ai_assisted boolean
   -> EventList shows AI badge, EventDetail shows AI badge
   -> ConfidenceIndicator shows tier-specific styling
```

### Where to Compute `ai_assisted`

The best place is in `pipeline.py` within `run_full_pipeline()` and `rebuild_pipeline_result()`, right where `needs_review` and `match_confidence` are set on the canonical dict. For each cluster, check if any match decision between events in the cluster has `tier.startswith("ai")`.

```python
canonical["ai_assisted"] = _cluster_has_ai_decisions(cluster, match_result.decisions)
```

This mirrors the existing pattern for `match_confidence` computation.

### Frontend Integration Points

1. **EventList table**: Add an "AI" column or inline badge next to the title/confidence. Best as inline badge (less column sprawl).
2. **EventDetail header badges**: Add purple/indigo badge "AI Assisted" in the flex badge row (line 75-94).
3. **EventDetail match decisions**: The ConfidenceIndicator already shows tier text. Enhance with colored styling.
4. **ConfidenceIndicator**: Add tier-specific badge colors -- e.g., purple for "ai", orange for "ai_low_confidence", gray for "deterministic".

## Architecture Patterns

### Pattern 1: Adding a Database Column

Follow the established pattern:
1. Add `mapped_column` to SQLAlchemy model
2. Create Alembic migration with `op.add_column()`
3. Add field to API Pydantic schema
4. Add field to frontend TypeScript interface
5. Set field during persistence

```python
# In canonical_event.py
ai_assisted: Mapped[bool] = mapped_column(sa.Boolean, default=False)
```

```python
# In Alembic migration 006
def upgrade() -> None:
    op.add_column(
        "canonical_events",
        sa.Column("ai_assisted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

def downgrade() -> None:
    op.drop_column("canonical_events", "ai_assisted")
```

### Pattern 2: Computing Derived Fields in Pipeline

Follow the existing pattern for `match_confidence` and `needs_review`:

```python
# In pipeline.py, within run_full_pipeline() and rebuild_pipeline_result()
canonical["ai_assisted"] = _cluster_has_ai_decisions(cluster, match_result.decisions)

def _cluster_has_ai_decisions(
    cluster: set[str],
    decisions: list[MatchDecisionRecord],
) -> bool:
    """Check if any match decision in a cluster was AI-resolved."""
    return any(
        d.tier.startswith("ai")
        and d.event_id_a in cluster
        and d.event_id_b in cluster
        for d in decisions
    )
```

### Pattern 3: Frontend Tier Badge Styling

```tsx
// In ConfidenceIndicator.tsx
function tierBadge(tier: string): { label: string; className: string } {
  switch (tier) {
    case 'ai':
      return { label: 'AI', className: 'bg-purple-100 text-purple-800' };
    case 'ai_low_confidence':
      return { label: 'AI (low)', className: 'bg-orange-100 text-orange-800' };
    default:
      return { label: tier, className: 'bg-gray-100 text-gray-600' };
  }
}
```

### Anti-Patterns to Avoid

- **Computing `ai_assisted` in the API route**: This would require querying match decisions for every event in the list view, causing N+1 queries. Compute it once during persistence instead.
- **Adding `ai_assisted` to the synthesizer**: The synthesizer works with source events only and has no access to match decisions. Keep it in the pipeline where decisions are available.
- **Hardcoding tier string checks**: Use `tier.startswith("ai")` to catch all AI tiers (ai, ai_low_confidence, ai_unexpected) rather than exact string matching.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Tier-to-color mapping | Custom CSS logic | Tailwind utility classes with a lookup map | Consistent with existing codebase pattern |
| AI badge icon | Custom SVG | Tailwind text badge with "AI" label | Matches existing badge patterns (Review, categories) |
| Column addition migration | Manual SQL | Alembic op.add_column() | Project already uses Alembic |

## Common Pitfalls

### Pitfall 1: Forgetting to Update Both Pipeline Functions

**What goes wrong:** `ai_assisted` is computed in `run_full_pipeline()` but not in `rebuild_pipeline_result()`, so AI-resolved events don't get the flag.
**Why it happens:** `rebuild_pipeline_result()` is a copy of the canonical event construction logic from `run_full_pipeline()`.
**How to avoid:** Extract the canonical dict enrichment into a shared helper function, or ensure both functions set `ai_assisted`.
**Warning signs:** `ai_assisted` is always False even when AI resolves pairs.

### Pitfall 2: Missing Server Default in Migration

**What goes wrong:** Adding `ai_assisted` column without `server_default=sa.text("false")` causes the migration to fail on PostgreSQL if existing rows exist (NOT NULL constraint violation).
**Why it happens:** PostgreSQL requires a default for NOT NULL columns when existing data exists.
**How to avoid:** Always include `server_default` for new NOT NULL columns on existing tables.

### Pitfall 3: Forgetting the Persistence Layer Mapping

**What goes wrong:** `ai_assisted` is computed in the pipeline dict but not mapped in `replace_canonical_events()`, so it's never written to the database.
**Why it happens:** The persistence layer has an explicit field-by-field mapping (line 105-129) rather than using `**kwargs`.
**How to avoid:** Add `ai_assisted=canonical_dict.get("ai_assisted", False)` to the CanonicalEvent constructor in persistence.py.

### Pitfall 4: Frontend Type Not Updated

**What goes wrong:** Backend returns `ai_assisted` but frontend ignores it because TypeScript type doesn't include it.
**Why it happens:** TypeScript types and Pydantic schemas are maintained separately.
**How to avoid:** Update both `CanonicalEventSummary` and `CanonicalEventDetail` in `frontend/src/types/index.ts`.

### Pitfall 5: Integration Test Not Covering Cache and Cost

**What goes wrong:** Integration test only checks that AI resolves decisions but doesn't verify cache storage or cost logging.
**Why it happens:** Focus on the happy path (decision application) without verifying side effects.
**How to avoid:** After resolution, query `ai_match_cache` and `ai_usage_log` tables to verify entries were created.

## Code Examples

### Adding ai_assisted to CanonicalEvent Model

```python
# src/event_dedup/models/canonical_event.py - add after match_confidence
ai_assisted: Mapped[bool] = mapped_column(sa.Boolean, default=False)
```

### Computing ai_assisted in Pipeline

```python
# src/event_dedup/matching/pipeline.py - add helper function
def _cluster_has_ai_decisions(
    cluster: set[str],
    decisions: list[MatchDecisionRecord],
) -> bool:
    """Check if any match decision in a cluster was resolved by AI."""
    return any(
        d.tier.startswith("ai")
        and d.event_id_a in cluster
        and d.event_id_b in cluster
        for d in decisions
    )
```

### Alembic Migration

```python
# config/alembic/versions/006_add_ai_assisted_column.py
revision = "006_ai_assisted"
down_revision = "005_config_settings"

def upgrade() -> None:
    op.add_column(
        "canonical_events",
        sa.Column("ai_assisted", sa.Boolean(), server_default=sa.text("false"), nullable=False),
    )

def downgrade() -> None:
    op.drop_column("canonical_events", "ai_assisted")
```

### Persistence Layer Update

```python
# In replace_canonical_events(), CanonicalEvent constructor
ai_assisted=canonical_dict.get("ai_assisted", False),
```

### API Schema Update

```python
# In schemas.py CanonicalEventSummary and CanonicalEventDetail
ai_assisted: bool = False
```

### Frontend Type Update

```typescript
// In types/index.ts CanonicalEventSummary
ai_assisted: boolean;

// In types/index.ts CanonicalEventDetail
ai_assisted: boolean;
```

### ConfidenceIndicator Tier Styling

```tsx
function TierBadge({ tier }: { tier: string }) {
  const styles: Record<string, string> = {
    ai: 'bg-purple-100 text-purple-800',
    ai_low_confidence: 'bg-orange-100 text-orange-800',
    deterministic: 'bg-gray-100 text-gray-600',
  };
  const labels: Record<string, string> = {
    ai: 'AI',
    ai_low_confidence: 'AI (low confidence)',
    deterministic: 'Deterministic',
  };
  return (
    <span className={`text-xs px-2 py-0.5 rounded font-medium ${styles[tier] || styles.deterministic}`}>
      {labels[tier] || tier}
    </span>
  );
}
```

### EventList AI Badge

```tsx
// In the title cell, after the Link
{event.ai_assisted && (
  <span className="ml-1.5 inline-block bg-purple-100 text-purple-800 text-xs px-1.5 py-0.5 rounded font-medium">
    AI
  </span>
)}
```

### Integration Test Pattern

```python
# tests/test_ai_integration_e2e.py
@patch("event_dedup.ai_matching.resolver.call_gemini")
@patch("event_dedup.ai_matching.resolver.create_client")
async def test_e2e_ai_matching(mock_create, mock_call, test_session_factory):
    """Full pipeline: ingest -> score -> AI resolve -> persist -> verify."""
    mock_create.return_value = AsyncMock()
    mock_call.return_value = (
        AIMatchResult(decision="same", confidence=0.9, reasoning="Same event"),
        800, 100,
    )
    # 1. Create source events
    # 2. Run pipeline with AI enabled
    # 3. Verify canonical event has ai_assisted=True
    # 4. Verify match decision has tier="ai"
    # 5. Verify ai_match_cache has entry
    # 6. Verify ai_usage_log has entry
```

## Test Strategy

### AIM-01: End-to-End Integration Test

**Approach:** Create a pytest test that exercises the full pipeline flow with mocked Gemini, from source events through AI resolution to persisted canonical events.

**What to test:**
1. Ambiguous pairs get routed to AI resolver
2. AI response (mocked) is applied correctly -- tier="ai" for high confidence
3. Cache is populated after API call
4. Cost tracking logs usage
5. Re-clustering happens with updated decisions
6. Canonical events are persisted with correct ai_assisted flag

**Fixtures:** Use existing `test_session_factory` and `test_engine` from conftest.py. Mock `call_gemini` and `create_client` as done in test_ai_resolver.py.

**Key difference from existing tests:** The existing tests test components in isolation (resolver, cache, cost). The integration test should flow through the full orchestrator path: `process_new_file()` or at minimum `run_full_pipeline()` -> `_maybe_resolve_ai()` -> `replace_canonical_events()`.

### AIM-02: ai_assisted Column

**Test:** After running the pipeline with AI-resolved pairs, query `CanonicalEvent.ai_assisted` and verify it's True for clusters that had AI-resolved pairs and False for clusters that didn't.

### AIM-03: Frontend AI Indicators

**Test:** Manual visual verification. Can also add a test to the API tests (test_api.py) verifying that `ai_assisted` appears in the JSON response.

### AIM-04: ConfidenceIndicator Styling

**Test:** Manual visual verification. The component changes are purely presentational.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| tier as plain text | tier as styled badge | This phase | Visual clarity of AI involvement |
| No AI tracking on canonical | ai_assisted boolean | This phase | Enables filtering/reporting on AI usage |

## Open Questions

1. **Should `ai_assisted` be filterable in the event list API?**
   - What we know: The list API has q, city, date_from, date_to, category filters. Adding ai_assisted filter would be straightforward.
   - Recommendation: Not required by AIM-02/03, can be added later if needed. Skip for now.

2. **EventDetail: How to show which specific pairs were AI-resolved?**
   - What we know: The ConfidenceIndicator already shows all match decisions with their tier. Adding visual distinction (AIM-04) inherently shows which pairs were AI-resolved.
   - Recommendation: The tier badge enhancement in ConfidenceIndicator satisfies this requirement. No additional UI needed.

3. **Should the dashboard stats include AI matching metrics?**
   - What we know: Dashboard has FileProcessingStats, MatchDistribution, CanonicalStats. AI usage logs exist in ai_usage_log.
   - Recommendation: Out of scope for Phase 9. Could be a future enhancement.

## Sources

### Primary (HIGH confidence)
- Direct code inspection of all 17 files listed in the research scope
- Alembic migration files in `config/alembic/versions/`
- Test infrastructure in `tests/conftest.py` and existing test files

### Code File References
| File | Key Lines | Purpose |
|------|-----------|---------|
| `src/event_dedup/models/canonical_event.py` | 18-73 | Model to extend with ai_assisted |
| `src/event_dedup/models/match_decision.py` | 36 | tier field (no DB constraint) |
| `src/event_dedup/ai_matching/resolver.py` | 193-246 | _apply_ai_result sets tier values |
| `src/event_dedup/matching/pipeline.py` | 202-262, 298-354 | run_full_pipeline + rebuild_pipeline_result |
| `src/event_dedup/worker/persistence.py` | 73-156 | replace_canonical_events |
| `src/event_dedup/api/schemas.py` | 86-128 | CanonicalEventSummary/Detail |
| `frontend/src/types/index.ts` | 8-17, 56-81 | TypeScript types |
| `frontend/src/components/ConfidenceIndicator.tsx` | 38-78 | Tier display |
| `frontend/src/components/EventList.tsx` | 88-170 | Event table |
| `frontend/src/components/EventDetail.tsx` | 72-105 | Header badges |
| `config/alembic/versions/005_add_config_settings.py` | 1-39 | Latest migration pattern |

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - Direct code inspection, no external dependencies needed
- Architecture: HIGH - All integration points clearly identified in existing code
- Pitfalls: HIGH - Based on direct analysis of data flow and existing patterns
- Test strategy: HIGH - Existing test patterns provide clear templates

**Research date:** 2026-02-28
**Valid until:** Indefinite (internal codebase, no external dependency changes)
