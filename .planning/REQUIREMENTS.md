# Requirements: Event Deduplication Service

**Defined:** 2026-02-27
**Core Value:** Accurate event deduplication — the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.

## v1 Requirements

Requirements for initial release. Each maps to roadmap phases.

### Ground Truth & Evaluation

- [ ] **EVAL-01**: System includes a labeled ground truth dataset of 200-300 event pairs (same/different) from the 765-event sample data
- [ ] **EVAL-02**: Evaluation harness reports precision, recall, and F1 score for deduplication decisions
- [ ] **EVAL-03**: Evaluation can be run against any threshold configuration to measure impact of changes

### Matching Core

- [ ] **MTCH-01**: System scores event similarity using multiple signals: date, geo proximity, title, and description
- [ ] **MTCH-02**: System uses blocking by date + city/geo grid to reduce candidate comparisons (>95% reduction)
- [ ] **MTCH-03**: Date matching handles same-day events with time tolerance (~30 min) and multi-day event date range overlap
- [ ] **MTCH-04**: Geo-proximity matching uses haversine distance weighted by each event's geo confidence score
- [ ] **MTCH-05**: Fuzzy title matching handles German compound words, umlauts, and OCR artifacts
- [ ] **MTCH-06**: Similarity thresholds are configurable without code changes (high-confidence auto-match, ambiguous zone, auto-reject)
- [ ] **MTCH-07**: German dialect synonym dictionary maps equivalent terms (Fasnet/Fasching/Fastnacht/Karneval etc.)
- [ ] **MTCH-08**: Category-aware matching weights adjust calibration per event type (carnival events weighted differently than political events)
- [ ] **MTCH-09**: Source-type-aware comparison adjusts for artikel (journalistic headline) vs terminliste (event name) title formats
- [ ] **MTCH-10**: Deduplication uses graph-based clustering (connected components), not pairwise decisions

### AI-Assisted Matching

- [ ] **AI-01**: Ambiguous event pairs (scoring between low and high threshold) are sent to an LLM for resolution
- [ ] **AI-02**: AI matching uses Gemini Flash (or best cost-effective model determined during implementation research)
- [ ] **AI-03**: AI responses include structured decision, confidence score, and reasoning
- [ ] **AI-04**: AI match results are cached to avoid re-evaluating identical pairs
- [ ] **AI-05**: AI usage is cost-monitored with per-batch and per-period reporting

### Canonical Event Management

- [ ] **CANL-01**: Canonical event is synthesized by selecting the best field value from each source (longest description, most precise location, richest highlights, etc.)
- [ ] **CANL-02**: Field-level provenance tracks which source event contributed each canonical field
- [ ] **CANL-03**: When new source events match an existing canonical, the canonical is enriched with any better information without downgrading existing good data
- [ ] **CANL-04**: Each match/group decision has a confidence score (0-1) derived from individual signal scores

### Data Pipeline

- [ ] **PIPE-01**: Docker container watches a configured directory for new JSON files
- [ ] **PIPE-02**: Processing is idempotent — re-processing the same file does not create duplicate records
- [ ] **PIPE-03**: Each file is processed in a single database transaction (all-or-nothing)
- [ ] **PIPE-04**: Service connects directly to PostgreSQL to read existing events and write canonical events + source links
- [ ] **PIPE-05**: Structured processing logs report events processed, matches found, new canonicals created, and errors per file

### Frontend: Browse & Search

- [ ] **UI-01**: Searchable paginated list of canonical events with filters for title, city, date range, and category
- [ ] **UI-02**: Canonical event detail view shows all fields (title, description, highlights, dates, location, categories, flags)
- [ ] **UI-03**: Drill-down from canonical event to all contributing source events with side-by-side comparison
- [ ] **UI-04**: Match confidence indicators show per-source signal scores (title similarity %, geo distance, date match)

### Frontend: Manual Review

- [ ] **REV-01**: Manual split — detach a source event from a canonical event (create new canonical or assign to another)
- [ ] **REV-02**: Manual merge — combine two canonical events into one, re-synthesize canonical fields
- [ ] **REV-03**: Review queue of low-confidence matches sorted by uncertainty (most ambiguous first)
- [ ] **REV-04**: All manual override decisions are logged with an audit trail
- [ ] **REV-05**: Batch processing dashboard showing match rates, error rates, and processing trends over time

### Deployment

- [ ] **DEPL-01**: All services run as Docker containers (pipeline worker, API server, frontend)
- [ ] **DEPL-02**: docker-compose.yml defines the full stack including PostgreSQL for development
- [ ] **DEPL-03**: Environment-based configuration (database connection, watched directory, AI API keys, thresholds)

## v2 Requirements

Deferred to future release. Tracked but not in current roadmap.

### Accuracy & Optimization

- **ACC-01**: Feedback loop — manual review decisions automatically inform threshold tuning recommendations
- **ACC-02**: Duplicate cluster visualization (network graph showing source overlap patterns)
- **ACC-03**: Incremental blocking key indexing for datasets >10K events/week

## Out of Scope

Explicitly excluded. Documented to prevent scope creep.

| Feature | Reason |
|---------|--------|
| Real-time streaming ingestion | Source files arrive in weekly batches; batch processing is sufficient |
| User authentication | Internal tool, no auth needed; add reverse-proxy auth later if needed |
| Mobile-responsive frontend | Desktop-first internal tool; responsive doubles frontend effort |
| ML model training pipeline | Insufficient labeled data; LLM outperforms at this scale |
| Elasticsearch/Solr | PostgreSQL pg_trgm handles this volume trivially |
| PDF extraction modifications | Upstream pipeline is separate; we accept JSON as-is |
| Event recommendations | This is a dedup system, not a consumer-facing event platform |

## Traceability

Which phases cover which requirements. Updated during roadmap creation.

| Requirement | Phase | Status |
|-------------|-------|--------|
| (populated by roadmap) | | |

**Coverage:**
- v1 requirements: 33 total
- Mapped to phases: 0
- Unmapped: 33

---
*Requirements defined: 2026-02-27*
*Last updated: 2026-02-27 after initial definition*
