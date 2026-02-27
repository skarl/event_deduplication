# Feature Landscape

**Domain:** Event deduplication / entity resolution for regional event data
**Researched:** 2026-02-27
**Overall confidence:** MEDIUM -- based on established entity resolution patterns applied to the specific event domain; no live web search available to verify latest tooling

## Table Stakes

Features the system must have to function correctly and be useful. Missing any of these means the system fails its core purpose.

### Matching & Deduplication Core

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Multi-signal similarity scoring** | Single-signal matching (e.g., title only) produces too many false positives/negatives. Must combine date, location, title, and geo proximity into a composite score. | Medium | This is the heart of the system. The current ~65% accuracy proves single-signal is insufficient. |
| **Blocking / candidate reduction** | Comparing every event to every other event is O(n^2). At 2000+/week against a growing DB, this becomes prohibitive. Must narrow comparisons to plausible candidates. | Medium | Block on date + city/district. Events on different dates in different cities cannot be duplicates. Reduces comparisons by 95%+. |
| **Configurable similarity thresholds** | No single threshold works for all event types. Carnival events need different tuning than political events. Thresholds need adjustment as accuracy data accumulates. | Low | Start with global thresholds, evolve to category-specific if needed. |
| **Date matching with tolerance** | Sources report slightly different times for the same event (e.g., 19:11 vs 19:30). Must match same-day events and handle time fuzziness. | Low | Same date = strong signal. Same date + time within ~30 min = very strong signal. Multi-day events need date range overlap logic. |
| **Geo-proximity matching** | Location names vary between sources ("Marktplatz" vs "Marktplatz Waldkirch"). Geo coordinates provide a source-independent signal. | Low | Haversine distance between coordinates. Events within ~500m on same date are strong candidates. Geo confidence scores already in data -- weight accordingly. |
| **Fuzzy title matching** | Titles for the same event vary substantially (60-100% match per PROJECT.md). Need string similarity that handles German compound words. | Medium | Trigram similarity or Levenshtein ratio. German-specific: handle compound word splitting, umlauts normalized. "Primel-Aktion Emmendingen" vs "Primeltöpfchen-Aktion" must score high. |
| **Source event preservation** | All original source records must be kept intact and linked to their canonical event. Destroying source data means losing information and audit trail. | Low | Simple foreign key: source_events.canonical_event_id. Never delete or modify source events. |

### Canonical Event Management

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Canonical event synthesis** | When multiple sources describe the same event, create one "best" record picking the best title, longest description, richest highlights, most precise location. | Medium | Field-level selection: pick best per field, not best source overall. One source may have the best title while another has the best description. |
| **Field-level provenance tracking** | Must know which source each canonical field came from. Required for debugging, manual review, and enrichment decisions. | Low | Store source_event_id per canonical field, or at minimum per canonical event track which sources contributed. |
| **Enrichment on re-processing** | When a new source file arrives containing events that match existing canonical events, update the canonical with any better information. | Medium | Compare field quality (length, completeness, confidence) and upgrade canonical fields when new source is better. Must not downgrade existing good data. |
| **Confidence scoring for match decisions** | Each dedup decision needs a confidence score so operators know which ones to trust and which to review. | Low | Composite of individual signal scores (title similarity, geo distance, date match, etc.). Expose as 0-1 score. |

### Data Pipeline

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Directory watch for JSON ingestion** | Must integrate with existing pipeline that drops JSON files into a directory. | Low | fswatch/inotify or polling. Process file, move to processed/failed directory. |
| **Idempotent processing** | Re-processing the same file must not create duplicate canonical events or duplicate source links. | Medium | Track processed files by hash or filename+timestamp. Source event IDs (e.g., "pdf-9d58bea1-1-6") are already unique -- use them. |
| **Batch processing with transaction safety** | A file with 28 events must be processed atomically. Partial failures leave the database inconsistent. | Medium | Wrap entire file processing in a DB transaction. All-or-nothing per file. |
| **PostgreSQL direct integration** | Project requires direct DB connection, not export/import. Must read existing canonical events for matching and write new ones. | Low | Standard connection pool. Read for matching, write for new canonicals/sources. |
| **Processing status and logging** | Operators need to know what happened: how many events processed, how many matched, how many new canonicals created, any errors. | Low | Structured logging per file. Summary stats stored in DB or logged. |

### Frontend

| Feature | Why Expected | Complexity | Notes |
|---------|--------------|------------|-------|
| **Searchable canonical event list** | Core browsing capability. Must search by title, city, date range, category. | Medium | Full-text search on title + description. Filter by date range, city, category. Pagination. |
| **Canonical-to-source drill-down** | Must see which source events were grouped under a canonical event and compare their data side-by-side. | Low | Click canonical event, see list of contributing sources with their original data. |
| **Manual review: split wrong groups** | System will make mistakes. Must be able to detach a source event from a canonical event (creating a new canonical or moving to another). | Medium | UI to select source events within a group and split them out. Recalculate canonical fields after split. |
| **Manual review: merge missed groups** | System will miss some duplicates. Must be able to merge two canonical events into one. | Medium | Select two canonicals, merge source events under one, re-synthesize canonical fields, delete the other. |
| **Match confidence indicators** | Review UI must show why events were grouped -- which signals matched and at what strength. | Low | Display per-source match scores: title similarity %, geo distance, date match. Helps operator decide if grouping is correct. |

## Differentiators

Features that elevate the system from "basic dedup" to "reliable event management." Not strictly required for v1, but provide significant value.

| Feature | Value Proposition | Complexity | Notes |
|---------|-------------------|------------|-------|
| **Tiered matching: fast deterministic + AI fallback** | Fast matching handles the easy 70-80% of cases cheaply. AI (LLM) handles the ambiguous 20-30% where title similarity and geo alone are insufficient. Dramatically improves accuracy while controlling costs. | High | The key differentiator per PROJECT.md. Deterministic matching is the baseline; AI matching for cases below confidence threshold but above rejection threshold. Critical to get the threshold tuning right. |
| **German-language-aware text similarity** | Standard English-oriented NLP tools perform poorly on German compound words, inflections, and regional dialects. Purpose-built normalization handles "Kinderball" vs "Kinder-Ball" vs "Ball fuer Kinder." | Medium | Normalize: strip umlauts, split compounds, stem German words. Significant accuracy boost for this specific domain. |
| **Category-aware matching weights** | "Fasnacht" events in the same town on the same day are very likely distinct (many carnival events per day). Political events are more likely unique. Matching weights should vary by category. | Medium | Different event categories have different base rates of duplication. Carnival season = many similar events at same location. Weight title similarity higher for these. |
| **Duplicate cluster visualization** | Visual representation of how events cluster -- which sources overlap, which events form strong vs weak clusters. Helps operators understand the dedup landscape at a glance. | Medium | Network graph or matrix view showing source overlap. Useful for identifying systematic issues (e.g., source X always conflicts with source Y). |
| **Incremental matching** | When a new file arrives, only compare new events against existing canonicals -- do not re-match the entire database. | Medium | Index existing canonicals by date+city blocks. New events query only relevant blocks. Scales to much larger datasets. |
| **Match decision audit log** | Record every match/non-match decision with the signals and scores that drove it. Enables accuracy analysis, threshold tuning, and debugging. | Low | Append-only log: event_a_id, event_b_id, decision, score_breakdown, timestamp. Invaluable for improving the system over time. |
| **Manual review queue with prioritization** | Automatically surface low-confidence matches for human review, ordered by uncertainty (most ambiguous first). Reduces review burden vs. reviewing everything. | Medium | Queue of match decisions where confidence is in the "gray zone" (e.g., 0.4-0.7). Operator resolves, system learns implicit thresholds. |
| **Location normalization layer** | Standardize location names before matching. "Marktplatz" -> "Marktplatz, Waldkirch" when city context is available. Reduces false negatives from inconsistent location naming. | Medium | Lookup table or geocoder-based normalization. The data already has `_sanitizeResult` with confidence -- leverage and extend this. |
| **Batch processing dashboard** | Overview of all processed batches: when, how many events, match rates, error rates, pending reviews. Operational visibility. | Low | Simple table/chart view. Shows trends over time (is accuracy improving?). |
| **Feedback loop for threshold tuning** | Manual review decisions feed back to improve matching thresholds. When operators consistently approve matches at score 0.55, the threshold can be adjusted. | High | Requires collecting enough review data, computing precision/recall at different thresholds, and suggesting or auto-adjusting. Long-term accuracy improvement. |

## Anti-Features

Features to explicitly NOT build. These are tempting but wrong for this system.

| Anti-Feature | Why Avoid | What to Do Instead |
|--------------|-----------|-------------------|
| **Real-time streaming ingestion** | PROJECT.md explicitly scopes this as batch. Real-time adds enormous complexity (exactly-once processing, back-pressure, ordering guarantees) for no benefit -- source PDFs arrive in weekly batches. | Directory watch with batch processing per file. Simple, reliable, sufficient. |
| **User authentication / multi-tenancy** | Internal tool used by a small team. Auth adds development time and operational complexity for zero value. | No auth. If needed later, add reverse proxy auth (e.g., Nginx basic auth) without touching application code. |
| **Mobile-responsive frontend** | Desktop-first internal tool per PROJECT.md. Responsive design doubles frontend development time. | Standard desktop layout. Tables, side-by-side comparisons, dense information display -- all suited to desktop. |
| **ML model training pipeline** | Tempting to "train a custom dedup model." Massive complexity, needs labeled training data (which you do not have yet), and LLM-based matching will outperform a small trained model for this data volume. | Use LLM API calls for ambiguous cases. Collect labeled data from manual reviews as a byproduct -- if you ever have 10K+ labeled pairs, revisit. |
| **Automatic merging without confidence gates** | Tempting to auto-merge everything above a threshold. But false merges are worse than missed merges -- a false merge corrupts the canonical event. | High-confidence matches auto-merge. Medium-confidence goes to review queue. Low-confidence stays separate. Conservative is correct. |
| **Full-text search engine (Elasticsearch/Solr)** | Overkill for 2000 events/week. PostgreSQL full-text search and trigram extensions handle this volume trivially. Adding a search engine means another service to deploy, maintain, and sync. | PostgreSQL `pg_trgm` extension for fuzzy text search, `tsvector` for full-text search. Both built-in, battle-tested, zero additional infrastructure. |
| **Event recommendation / personalization** | Scope creep. This is a deduplication system, not a consumer-facing event platform. | Keep the system focused on dedup + canonical management. If recommendations are needed, it is a separate service consuming the canonical event database. |
| **PDF extraction modifications** | Explicitly out of scope. The extraction pipeline is upstream and separate. | Accept JSON as-is. Document quality issues to feed back to the extraction team, but never modify the pipeline itself. |
| **Complex role-based permissions** | Single-user internal tool does not need roles, permissions, or access control lists. | Everyone who can reach the frontend can do everything. |
| **Event change notifications / webhooks** | Nobody is subscribing to event updates in this internal tool context. | If downstream systems need to know about new canonicals, they can poll the database directly. |

## Feature Dependencies

```
Directory Watch (ingestion)
  --> JSON Parsing & Validation
    --> Blocking / Candidate Reduction
      --> Multi-Signal Similarity Scoring
        --> Configurable Thresholds
          --> Match/No-Match Decision
            --> Canonical Event Synthesis (new matches)
            --> Enrichment (existing canonical matches)
            --> Source Event Linking

Canonical Event Synthesis
  --> Field-Level Provenance Tracking

Multi-Signal Similarity Scoring
  --> Date Matching with Tolerance
  --> Geo-Proximity Matching
  --> Fuzzy Title Matching
  --> German-Language-Aware Normalization (enhances title matching)

Tiered Matching (differentiator)
  --> Fast Deterministic Matching (blocking + scoring)
  --> AI/LLM Fallback (for ambiguous cases below confidence threshold)

Frontend: Searchable Event List
  --> Frontend: Canonical-to-Source Drill-Down
    --> Frontend: Manual Review (split/merge)
      --> Match Confidence Indicators
      --> Manual Review Queue (differentiator)
        --> Feedback Loop for Threshold Tuning (differentiator)

Processing Status & Logging
  --> Match Decision Audit Log (differentiator)
    --> Batch Processing Dashboard (differentiator)
```

## MVP Recommendation

### Phase 1: Core Dedup Engine (must have)

Prioritize these table-stakes features first:

1. **Directory watch + JSON ingestion** -- get data flowing
2. **Blocking by date + city** -- reduce comparison space
3. **Multi-signal similarity scoring** (date + geo + title) -- the core matching logic
4. **Configurable thresholds** -- tunable without code changes
5. **Canonical event synthesis** -- create the output
6. **Source event preservation + linking** -- maintain data integrity
7. **Idempotent processing** -- safe re-runs
8. **PostgreSQL integration** -- read/write directly

### Phase 2: Frontend + Manual Review

9. **Searchable canonical event list** -- see what the system produced
10. **Canonical-to-source drill-down** -- verify groupings
11. **Match confidence indicators** -- understand decisions
12. **Manual split/merge** -- correct mistakes

### Phase 3: Accuracy Improvements

13. **German-language-aware normalization** -- accuracy boost
14. **Tiered matching with AI fallback** -- handle ambiguous cases
15. **Category-aware matching weights** -- reduce false positives for carnival season
16. **Location normalization layer** -- reduce false negatives

### Phase 4: Operational Excellence

17. **Match decision audit log** -- understand system behavior
18. **Manual review queue with prioritization** -- efficient review workflow
19. **Batch processing dashboard** -- operational visibility
20. **Feedback loop for threshold tuning** -- continuous improvement

### Defer Indefinitely

- ML model training (insufficient labeled data, LLM superior at this scale)
- Real-time streaming (batch is sufficient)
- Full-text search engine (PostgreSQL is sufficient)
- Mobile frontend (desktop-only audience)

## Complexity Budget

| Phase | Features | Total Complexity | Estimated Effort |
|-------|----------|------------------|------------------|
| Phase 1 | 8 core dedup features | Medium-High | 2-3 weeks |
| Phase 2 | 4 frontend features | Medium | 1-2 weeks |
| Phase 3 | 4 accuracy features | High (AI integration) | 2-3 weeks |
| Phase 4 | 4 operational features | Medium | 1-2 weeks |

## Domain-Specific Observations

### Why This Is Harder Than Generic Deduplication

1. **German language complexity**: Compound words ("Kinderfasnet" = "Kinder" + "Fasnet"), regional dialects, umlauts. English-trained NLP tools underperform significantly.

2. **Carnival season density**: During Fasching/Fasnacht, the same small town can have 10+ events per day at overlapping locations. Standard "same location + same date = duplicate" heuristics produce massive false positive rates.

3. **Varying data quality across sources**: Some sources provide rich descriptions and precise coordinates; others provide only a title and approximate city. The matching system must handle this asymmetry.

4. **Same venue, different events**: "Herrenberghalle, Nordweil" hosts both "Kinderfasnet" and "Narrenbaum fällen" on the same day. Location + date matching alone would incorrectly merge these.

5. **Title as article headline vs event name**: Source type "artikel" titles are journalistic headlines ("Nordwiler Narrenfahrplan - Kita-Gizig-Umzug"), while "terminliste" titles are event names ("Preismaskenball"). The same event can appear with very different title styles.

6. **Multi-day events**: Some events span multiple days (e.g., "Aubach Festival" 2026-08-21 to 2026-08-22). Date matching must handle single-date sources matching against a multi-day event's range.

### What Makes This Tractable

1. **Geographic constraint**: All events are in a small region (Emmendingen/Breisgau area). Geo-blocking is extremely effective.

2. **Date constraint**: Events happen on specific dates. Date blocking eliminates 95%+ of comparisons.

3. **Existing geo coordinates**: Source data already includes geocoded coordinates with confidence scores. No need to build geocoding.

4. **Unique source IDs**: Each source event has a unique ID (e.g., "pdf-9d58bea1-1-6"). Idempotency is straightforward.

5. **Moderate volume**: 2000 events/week is very manageable. No need for distributed computing.

6. **Structured data**: Events have well-defined fields (title, date, location, coordinates). This is structured entity resolution, not free-text dedup.

## Sources

- Analysis of 20 sample JSON files in `/eventdata/` directory (765 events across ~10 sources)
- PROJECT.md requirements and context documentation
- Entity resolution domain knowledge (Fellegi-Sunter model, blocking strategies, similarity scoring)
- Note: Web search unavailable during research. Confidence levels adjusted accordingly. Core entity resolution patterns are well-established and stable, so impact is limited for feature identification. Stack-specific library versions would benefit from live verification.
