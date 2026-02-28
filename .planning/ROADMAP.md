# Roadmap: Event Deduplication Service

## Overview

This roadmap takes the event deduplication service from zero to a fully operational system that ingests JSON event files, deduplicates them with high accuracy using tiered matching (fast deterministic + Gemini Flash AI), maintains a canonical event database in PostgreSQL, and provides a frontend for browsing, searching, and manually reviewing event groupings. The phases are ordered by dependency: ground truth and data foundation first (because matching without measurement is guesswork), then the core matching algorithm (the system's entire value), then pipeline integration and deployment (making it run as a service), then the user-facing layers, and finally accuracy refinement informed by real operational data.

## Phases

**Phase Numbering:**
- Integer phases (1, 2, 3): Planned milestone work
- Decimal phases (2.1, 2.2): Urgent insertions (marked with INSERTED)

Decimal phases appear between their surrounding integers in numeric order.

- [x] **Phase 1: Foundation & Ground Truth** - Database schema, data models, JSON ingestion, preprocessing, and labeled evaluation dataset
- [ ] **Phase 2: Core Matching Pipeline** - Multi-signal blocking, Tier 1 scoring, graph clustering, and canonical event synthesis
- [ ] **Phase 3: Pipeline Integration & Deployment** - File watcher, end-to-end pipeline orchestration, Docker containers, and docker-compose
- [ ] **Phase 4: API & Browse Frontend** - FastAPI REST API and React frontend for searching and viewing canonical events
- [ ] **Phase 5: AI-Assisted Matching** - Gemini Flash integration for ambiguous pairs with caching and cost monitoring
- [ ] **Phase 6: Manual Review & Operations** - Review queue UI, split/merge operations, audit trail, and batch processing dashboard
- [ ] **Phase 7: Accuracy Refinement** - German dialect synonyms, category-aware weights, source-type calibration

## Phase Details

### Phase 1: Foundation & Ground Truth
**Goal**: The system can ingest event JSON files into PostgreSQL with full preprocessing, and a labeled ground truth dataset enables objective accuracy measurement for all subsequent matching work
**Depends on**: Nothing (first phase)
**Requirements**: EVAL-01, EVAL-02, EVAL-03, PIPE-02, PIPE-03, PIPE-04
**Success Criteria** (what must be TRUE):
  1. A JSON file from the existing extraction pipeline can be loaded into PostgreSQL, and re-processing the same file does not create duplicate records
  2. Source events are stored with all fields preserved (title, description, dates, location, categories, geo coordinates, etc.) and linked to their source file
  3. A labeled ground truth dataset of 200-300 event pairs (same/different) exists from the 765-event sample data
  4. Running the evaluation harness against any matching configuration produces precision, recall, and F1 scores
  5. Text preprocessing normalizes umlauts, lowercases, strips prefixes, and generates blocking keys (date+city, date+geo grid) for every ingested event
**Plans**: 4 plans

Plans:
- [x] 01-01-PLAN.md -- Project setup, database schema, SQLAlchemy models, Alembic migrations, JSON ingestion with idempotency
- [x] 01-02-PLAN.md -- Text normalization (umlauts, prefixes, city aliases), blocking key generation, preprocessing integration
- [x] 01-03-PLAN.md -- Ground truth candidate generator, CLI labeling tool, evaluation harness (precision/recall/F1)
- [x] 01-04-PLAN.md -- Auto-generated ground truth dataset (1181 labeled pairs via conservative multi-signal heuristics)

### Phase 2: Core Matching Pipeline
**Goal**: The system accurately deduplicates events using multi-signal scoring and graph-based clustering, producing canonical events that combine the best information from all sources
**Depends on**: Phase 1
**Requirements**: MTCH-01, MTCH-02, MTCH-03, MTCH-04, MTCH-05, MTCH-06, MTCH-10, CANL-01, CANL-02, CANL-03, CANL-04
**Success Criteria** (what must be TRUE):
  1. Processing the 765-event sample dataset produces canonical events where the same real-world event from different sources is grouped together, measured by F1 score against the ground truth dataset
  2. Blocking reduces candidate comparisons by >95% (verified by comparing blocked vs. unblocked pair counts)
  3. Canonical events contain the best field from each source (longest description, most precise location, richest highlights) with provenance tracking showing which source contributed each field
  4. When new source events match an existing canonical event, the canonical is enriched with better information without losing existing good data
  5. Similarity thresholds (high-confidence, ambiguous zone, auto-reject) can be changed via configuration without code changes
**Plans**: 4 plans

Plans:
- [ ] 02-01-PLAN.md -- Database models (CanonicalEvent, CanonicalEventSource, MatchDecision), matching config (YAML + Pydantic), signal scorers (date, geo, title, description), weighted combiner
- [ ] 02-02-PLAN.md -- Candidate pair generator using blocking keys, matching pipeline orchestrator that scores all pairs
- [ ] 02-03-PLAN.md -- Graph-based clustering with networkx connected_components, cluster coherence validation
- [ ] 02-04-PLAN.md -- Canonical event synthesis with field strategies and provenance, enrichment engine, full pipeline orchestrator, updated evaluation harness

### Phase 3: Pipeline Integration & Deployment
**Goal**: The complete pipeline runs as Docker containers that automatically process new JSON files dropped into a watched directory
**Depends on**: Phase 2
**Requirements**: PIPE-01, PIPE-05, DEPL-01, DEPL-02, DEPL-03
**Success Criteria** (what must be TRUE):
  1. Dropping a JSON file into the watched directory triggers automatic processing, and canonical events appear in the database without manual intervention
  2. Each file is processed in a single database transaction -- if processing fails partway through, no partial data is written
  3. Structured processing logs report events processed, matches found, new canonicals created, and errors for each file
  4. Running `docker-compose up` starts the full stack (pipeline worker, API server, frontend, PostgreSQL) with all configuration provided via environment variables
  5. The pipeline worker, API server, and frontend each run as separate Docker containers
**Plans**: TBD

Plans:
- [ ] 03-01: TBD
- [ ] 03-02: TBD

### Phase 4: API & Browse Frontend
**Goal**: Users can search, browse, and inspect canonical events and their source events through a web interface
**Depends on**: Phase 3
**Requirements**: UI-01, UI-02, UI-03, UI-04
**Success Criteria** (what must be TRUE):
  1. User can search canonical events by title, filter by city, date range, and category, and paginate through results
  2. User can view a canonical event's full details including title, description, highlights, dates, location, categories, and flags
  3. User can drill down from a canonical event to see all contributing source events in a side-by-side comparison
  4. Match confidence indicators show per-source signal scores (title similarity percentage, geo distance, date match quality) for each source event in a group
**Plans**: TBD

Plans:
- [ ] 04-01: TBD
- [ ] 04-02: TBD

### Phase 5: AI-Assisted Matching
**Goal**: Ambiguous event pairs that deterministic matching cannot confidently resolve are sent to Gemini Flash for AI-assisted resolution, improving accuracy on the hardest cases
**Depends on**: Phase 2 (needs score distribution data to calibrate ambiguity zone)
**Requirements**: AI-01, AI-02, AI-03, AI-04, AI-05
**Success Criteria** (what must be TRUE):
  1. Event pairs scoring between the low and high thresholds are automatically sent to Gemini Flash and resolved with a structured decision (same/different), confidence score, and reasoning
  2. AI match results are cached so identical event pairs are never re-evaluated
  3. AI usage costs are tracked and reported per batch and per time period
  4. F1 score on the ground truth dataset improves after enabling AI-assisted matching compared to Tier 1 deterministic matching alone
**Plans**: TBD

Plans:
- [ ] 05-01: TBD
- [ ] 05-02: TBD

### Phase 6: Manual Review & Operations
**Goal**: Operators can correct grouping mistakes and monitor system health through the review UI
**Depends on**: Phase 4 (needs browse UI), Phase 5 (review queue is most useful after AI has resolved clear ambiguous cases)
**Requirements**: REV-01, REV-02, REV-03, REV-04, REV-05
**Success Criteria** (what must be TRUE):
  1. Operator can detach a source event from its canonical event and either create a new canonical or assign it to a different existing canonical (split)
  2. Operator can merge two canonical events into one, with canonical fields automatically re-synthesized from the combined sources
  3. A review queue shows low-confidence matches sorted by uncertainty (most ambiguous first), allowing the operator to work through the hardest cases systematically
  4. Every manual split, merge, and override decision is logged with an audit trail showing who changed what and when
  5. A batch processing dashboard shows match rates, error rates, and processing trends over time
**Plans**: TBD

Plans:
- [ ] 06-01: TBD
- [ ] 06-02: TBD

### Phase 7: Accuracy Refinement
**Goal**: Matching accuracy is improved for German-specific edge cases through synonym dictionaries, category-aware weighting, and source-type calibration
**Depends on**: Phase 5 (needs operational data to calibrate weights), Phase 6 (manual review data informs where accuracy fails)
**Requirements**: MTCH-07, MTCH-08, MTCH-09
**Success Criteria** (what must be TRUE):
  1. German dialect synonyms (Fasnet/Fasching/Fastnacht/Karneval, etc.) are treated as equivalent during title matching, measurably reducing missed duplicates for carnival-season events
  2. Category-aware matching weights adjust scoring per event type (e.g., carnival events weighted differently than political events), verified by improved F1 on category-specific subsets of the ground truth
  3. Source-type-aware comparison adjusts for title format differences between artikel (journalistic headlines) and terminliste (event listing names)
**Plans**: TBD

Plans:
- [ ] 07-01: TBD

## Progress

**Execution Order:**
Phases execute in numeric order: 1 -> 2 -> 3 -> 4 -> 5 -> 6 -> 7

| Phase | Plans Complete | Status | Completed |
|-------|----------------|--------|-----------|
| 1. Foundation & Ground Truth | 4/4 | Complete | 2026-02-27 |
| 2. Core Matching Pipeline | 2/4 | In progress | - |
| 3. Pipeline Integration & Deployment | 0/2 | Not started | - |
| 4. API & Browse Frontend | 0/2 | Not started | - |
| 5. AI-Assisted Matching | 0/2 | Not started | - |
| 6. Manual Review & Operations | 0/2 | Not started | - |
| 7. Accuracy Refinement | 0/1 | Not started | - |
