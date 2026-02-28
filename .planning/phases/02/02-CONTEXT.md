# Phase 2 Context: Core Matching Pipeline

**Phase goal**: The system accurately deduplicates events using multi-signal scoring and graph-based clustering, producing canonical events that combine the best information from all sources.

**Created**: 2026-02-27
**Requirements**: MTCH-01, MTCH-02, MTCH-03, MTCH-04, MTCH-05, MTCH-06, MTCH-10, CANL-01, CANL-02, CANL-03, CANL-04

---

## Success Criteria

1. Processing the 765-event sample dataset produces canonical events where the same real-world event from different sources is grouped together, measured by F1 score against the ground truth dataset
2. Blocking reduces candidate comparisons by >95% (verified by comparing blocked vs. unblocked pair counts)
3. Canonical events contain the best field from each source (longest description, most precise location, richest highlights) with provenance tracking showing which source contributed each field
4. When new source events match an existing canonical event, the canonical is enriched with better information without losing existing good data
5. Similarity thresholds (high-confidence, ambiguous zone, auto-reject) can be changed via configuration without code changes

## Phase 1 Interfaces (What We Build On)

### Database Models
- `SourceEvent`: 30+ columns including normalized fields (`title_normalized`, `location_city_normalized`, `location_name_normalized`, `short_description_normalized`), geo fields, `blocking_keys` (JSON array), `source_type`, `source_code`, `categories`, `confidence_score`
- `EventDate`: `date`, `start_time`, `end_time`, `end_date` linked to `SourceEvent`
- `FileIngestion`: tracks processed files with SHA-256 hash
- `GroundTruthPair`: labeled event pairs (1181 pairs: 248 same, 933 different)

### Preprocessing Pipeline
- `normalize_text()`: lowercase, NFC, umlaut expansion (ae/oe/ue/ss), whitespace collapse, punctuation removal (hyphens kept)
- `normalize_city()`: text normalization + alias resolution (20 Breisgau district mappings)
- `strip_prefixes()`: config-driven removal of 18 source-specific prefix patterns
- `generate_blocking_keys()`: produces `dc|{date}|{city}` and `dg|{date}|{geo_grid}` keys per event-date

### Blocking Keys Format
```
dc|2026-02-12|kenzingen     (date + city)
dg|2026-02-12|48.15|7.80    (date + geo grid ~10km cell)
```
- Geo grid only for events with confidence >= 0.85 AND within Breisgau bounding box
- Events can have multiple blocking keys (one per date x location type)

### Evaluation Harness
- `generate_predictions_from_events()`: pure function, blocking-based matching, returns predicted pairs
- `compute_metrics()`: precision, recall, F1 from predicted vs. ground truth
- `run_threshold_sweep()`: evaluates across multiple thresholds
- Ground truth: 248 "same" pairs, 933 "different" pairs, 157 ambiguous excluded

## What Phase 2 Must Build

### New Database Tables
- `canonical_events`: synthesized events with best fields from all sources
- `canonical_event_sources`: linking table (canonical_event_id, source_event_id, added_at)
- `match_decisions`: all pairwise decisions (match/no_match/ambiguous) with scores, tier, reasoning

### Matching Pipeline Components
1. **Individual Signal Scorers**: date_score, geo_score, title_score, description_score
2. **Combined Weighted Scorer**: configurable weights (research suggests date=0.30, location=0.25, title=0.30, description=0.15)
3. **Candidate Pair Generator**: uses blocking keys from Phase 1 to find candidate pairs
4. **Graph Clusterer**: networkx connected_components on match pairs
5. **Cluster Coherence Validator**: flags over-large or inconsistent clusters
6. **Canonical Synthesizer**: field-level best-value selection with provenance
7. **Enrichment Engine**: updates existing canonical events when new sources arrive

### Configuration (no code changes to tune)
- Signal weights (date, geo, title, description)
- Thresholds: HIGH (auto-match), LOW (auto-reject), zone in between = ambiguous (for future Phase 5 AI)
- Field selection strategies per canonical field

## Key Domain Constraints

From research + Phase 1 learnings:
- **German compound words**: hyphens preserved in normalization (handled in Phase 1)
- **Same venue, different event**: require higher title similarity when location matches strongly (Pitfall #11)
- **Geo false confidence**: weight by confidence score, treat < 0.85 as unknown (Pitfall #6)
- **Pairwise → clustering**: use graph connected components from day one (Pitfall #1)
- **Multi-date events**: date range overlap matching, not exact equality (Pitfall #10)
- **Source-type bias**: artikel vs. terminliste have different title formats (Pitfall #12)
- **Title is ONE signal, not THE signal**: multi-signal scoring is the whole point (Pitfall #2)

## Data Characteristics (for scoring calibration)

- 765 events across ~20 files from 11 sources
- Title similarity for true duplicates ranges from ~60% to 100%
- Many events geocode to village centroids (same coords for different venues)
- Carnival season: 10+ events per day per small town — high false positive risk
- Source types: "artikel" (journalistic), "terminliste" (calendar listing), "anzeige" (advertisement)

## Deferred to Later Phases

- AI-assisted matching (Phase 5) — Phase 2 identifies the "ambiguous zone" but doesn't resolve it
- German dialect synonym dictionary (Phase 7) — Phase 2 uses existing normalization from Phase 1
- Category-aware weights (Phase 7) — Phase 2 uses uniform weights
- Source-type-aware weights (Phase 7) — Phase 2 uses uniform weights

---
*Context captured: 2026-02-27*
*Ready for: research-phase or plan-phase*
