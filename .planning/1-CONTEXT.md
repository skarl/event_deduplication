# Phase 1 Context: Foundation & Ground Truth

**Phase goal**: The system can ingest event JSON files into PostgreSQL with full preprocessing, and a labeled ground truth dataset enables objective accuracy measurement for all subsequent matching work.

**Created**: 2026-02-27
**Requirements**: EVAL-01, EVAL-02, EVAL-03, PIPE-02, PIPE-03, PIPE-04

---

## Decisions

### 1. Ground Truth Labeling Approach

**Decision**: Semi-automated candidate generation with human review

- System generates candidate duplicate pairs using heuristics (same date + same/nearby city)
- User reviews each candidate, labeling as same/different
- Target: 200-300 labeled pairs from the 765-event sample across 20 files
- "Same event" definition: **same real-world gathering** — if people would physically attend the same thing at the same place and time, it's the same event, regardless of how sources describe it
- Hard negatives (look-alike non-duplicates): include when encountered during candidate review, don't actively hunt for them
- Storage: **PostgreSQL table** (`ground_truth_pairs` or similar: event_id_a, event_id_b, label, notes)

**Why this matters for downstream**: The researcher/planner must design a candidate generation script that surfaces likely duplicates for human labeling. The evaluation harness reads from this DB table. The labeling tool should present pairs side-by-side for quick review.

### 2. Database Schema

**Decision**: Separate tables, designed for future expansion

- **Separate `source_events` and `canonical_events` tables** with a linking table. Not a single table with type flag. Rationale: different field semantics (canonical fields are synthesized, source fields are raw), and separate tables are easier to expand independently.
- **`event_dates` table**: Separate table with (event_id, date, start_time, end_time). One row per date occurrence. Supports multi-day events (Primel-Aktion: Feb 13 + Feb 14) and events with no time specified.
- **`file_ingestions` table**: Tracks (filename, file_hash, ingested_at, event_count, status). Used for idempotency — if file_hash exists, skip processing.
- **Selective metadata storage**: Keep `_extracted_at` and `_batch_index` from JSON (useful for debugging). Drop `_sanitizeResult`, `_sanitized`, `_event_index` (internal to extraction pipeline, no downstream value).
- **Dual text storage**: Original values preserved as-is for display; normalized versions in separate columns for matching. Users see the real text, matching uses cleaned text.

**Table summary (Phase 1 scope)**:
| Table | Purpose |
|-------|---------|
| `source_events` | Raw events from JSON files, all fields preserved |
| `event_dates` | Date/time entries linked to source events |
| `file_ingestions` | File-level tracking for idempotent processing |
| `ground_truth_pairs` | Labeled event pairs for evaluation |

Note: `canonical_events` and linking tables are Phase 2 scope.

### 3. Idempotency Strategy

**Decision**: File-hash-based skip with stable event IDs

- **File hash check**: If a JSON file's SHA-256 hash matches a previously processed file, skip entirely. Byte-for-byte identical = no reprocessing.
- **Event IDs are stable**: IDs like `pdf-9d58bea1-1-6` are deterministic (derived from PDF hash + indices). Re-extracting the same PDF produces the same IDs. These can serve as natural unique keys in the database.
- **No batch/week distinction**: Every file is processed identically regardless of when it arrives. No special "re-import" vs "first import" logic.
- **Dead letter queue for failures**: Failed files are moved to an error directory. No auto-retry. Operator inspects the error, fixes the issue, and re-drops the file. File status in `file_ingestions` table marked as 'failed' with error details.
- **Transaction safety**: Each file is processed in a single DB transaction. If anything fails, the entire file's changes roll back. No partial data written.

### 4. Preprocessing Scope

**Decision**: Normalize title + location; research decides on additional fields

- **Locked for normalization**: Title and location name get normalized (lowercase, umlaut expansion, prefix stripping). These are the primary matching signals.
- **Research decides**: Whether description/short_description normalization adds matching value. The researcher should analyze the 765-event sample to determine if fuzzy description matching improves duplicate detection. Title + location may be sufficient.
- **Configurable prefix list**: Known source-specific prefixes (e.g., "Nordwiler Narrenfahrplan - ") are maintained in a configuration file, editable without code changes. The prefix list is applied during normalization to extract the core event name.
- **Dual blocking strategy**:
  - **Geo grid blocking**: For events with geo confidence >= 0.8, assign to ~5km grid cells. Events in the same cell on the same date are candidates.
  - **City-name fallback**: For events with low geo confidence (< 0.8) or missing coordinates, block by city name + date.
  - Events can appear in both blocks (belt and suspenders approach). This catches duplicates even when one source has precise coordinates and another has only a city name.
- **Edge case — online events**: Events with `city: null` or location name "Online" are excluded from geo blocking entirely. They can only match by title + date.

---

## Data Characteristics (from sample analysis)

Key observations that affect Phase 1 implementation:

- **20 JSON files**, 765 events total, from ~11 source codes (bwb, emt, rks, rkt, del, den, elt, elz, ets, rkb, rkm)
- Each JSON file has structure: `{"events": [...], "rejected": [...], "metadata": {...}}`
- Event IDs follow pattern: `pdf-{hash}-{batch}-{index}` (e.g., `pdf-9d58bea1-1-6`)
- `source_type` values: "artikel", "terminliste", "anzeige" — affects title format and detail level
- Some events have `description` and `highlights`, many don't — these are richer in "artikel" sources
- Dates can be: single date, single date + time, date + end_date range, or multiple separate dates
- Location data quality varies: some have full address (street, zipcode), some just city name
- Geo confidence ranges from ~0.79 to 1.0; one "Online" event had incorrect Swiss coordinates
- Categories include: fasnacht, kinder, versammlung, bildung, natur, fest, musik, tanz, markt, shopping, buehne, hock

---

## Deferred Ideas

Ideas mentioned during discussion that belong to future phases:

- (None captured — discussion stayed within Phase 1 scope)

---

## Open Questions for Research/Planning

These are intentionally left for the researcher/planner to resolve:

1. **Which additional fields benefit from normalization?** Analyze the 765-event sample to determine if description/highlights normalization improves duplicate pair identification beyond title + location alone.
2. **Optimal prefix patterns**: What prefix patterns exist across all 20 files? The configurable prefix list needs an initial set of entries derived from data analysis.
3. **Geo grid cell size tuning**: The ~5km grid is a starting point. The researcher should verify this against actual event density in the Emmendingen/Breisgau region.
4. **Ground truth candidate generation heuristics**: Exact parameters for the semi-automated pair generation (date window tolerance, city matching rules) need to be determined from data analysis.

---
*Context captured: 2026-02-27*
*Ready for: research-phase or plan-phase*
