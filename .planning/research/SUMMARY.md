# Project Research Summary

**Project:** Event Deduplication Service
**Domain:** Entity resolution / record linkage for regional German-language event data
**Researched:** 2026-02-27
**Confidence:** MEDIUM-HIGH

## Executive Summary

This project is a domain-specific entity resolution system for regional events in the Emmendingen/Breisgau area sourced from German-language PDF publications. Expert practitioners in this domain (dedupe.io, Splink, recordlinkage) follow a well-established pipeline architecture: ingest -> preprocess -> block -> match (tiered) -> cluster -> canonicalize -> persist. The recommended approach is to build a monolithic Python service with clear module boundaries rather than microservices -- at 2000 events/week the scale does not warrant distributed infrastructure. The pipeline runs as a batch process triggered by file arrival, with a separate always-on FastAPI server for the frontend. The two services share a Python codebase and a single PostgreSQL database.

The recommended matching approach is tiered: fast deterministic matching (date + geo + title similarity using rapidfuzz and TF-IDF) handles the clear-cut 80-90% of cases, and GPT-4o-mini via the OpenAI SDK handles the ambiguous remainder at negligible cost (~$2-10/week). The key architectural insight is that deduplication is a clustering problem, not a pairwise problem -- events must be grouped using graph-based connected components (networkx), not compared event-by-event. This distinction is the single most common source of systemic failure in naively built dedup systems and must be addressed in the initial design.

The primary risks are: (1) missing ground truth data for threshold calibration -- building any matching logic without labeled pairs means tuning by intuition and losing the ability to measure accuracy objectively; (2) German-language-specific text matching failure due to compound words, dialect variants, and OCR artifacts that defeat English-oriented string similarity; and (3) false merges from the "same venue, different event" pattern common during Fasnet/carnival season. All three risks are preventable with upfront design choices described in detail in PITFALLS.md.

## Key Findings

### Recommended Stack

The stack is straightforward and well-reasoned for the domain. Python 3.12 is the only viable language choice given the NLP/fuzzy matching ecosystem. FastAPI with SQLAlchemy 2.0 (async) and asyncpg provides a clean, type-safe API layer. The three PostgreSQL extensions (pg_trgm, unaccent, PostGIS) enable in-database candidate pre-filtering before Python-side detailed matching. For the frontend, React 19 + Vite + TanStack Table/Query + Tailwind is the pragmatic choice for a data-heavy internal tool.

See STACK.md for full version matrix and alternatives analysis.

**Core technologies:**
- Python 3.12 + FastAPI + Uvicorn: Backend API and pipeline orchestration -- only language with the required NLP ecosystem
- rapidfuzz: Fuzzy title matching -- 10-100x faster than fuzzywuzzy, MIT licensed, superior German Unicode handling
- scikit-learn (TfidfVectorizer): Batch title comparison pre-filtering -- fast, deterministic, right level of sophistication for this volume
- PostgreSQL 15 + pg_trgm + unaccent: Candidate pre-filtering and persistent storage -- leverage existing infrastructure
- networkx: Graph-based clustering for transitive duplicate grouping -- essential for correct dedup semantics
- openai SDK (gpt-4o-mini): AI-assisted matching for ambiguous pairs -- ~$2-10/week, trivial cost for the accuracy gain
- watchfiles: Rust-based async file watcher -- more reliable than watchdog on Docker volumes
- React 19 + TanStack Table/Query + Tailwind: Frontend -- best data-table ecosystem for internal tools
- uv + Ruff: Python toolchain -- modern standard, dramatically faster than pip/poetry/black+flake8

### Expected Features

See FEATURES.md for the full feature dependency graph and complexity budget.

**Must have (table stakes):**
- Multi-signal similarity scoring (date + geo + title + description combined) -- single-signal matching is what produced the current 65% accuracy
- Blocking by date + city/geo grid -- eliminates 95%+ of candidate comparisons, required for performance
- Date matching with tolerance -- same-day with time fuzziness; date range overlap for multi-day events
- Geo-proximity matching weighted by confidence score -- coordinates degrade to city centroids at low confidence
- Fuzzy title matching with German normalization (umlauts, compound words, dialect synonyms)
- Canonical event synthesis with field-level provenance -- pick best per field, not best source overall
- Source event preservation with foreign key linking -- never modify or delete source data
- Idempotent file processing using source event ID as natural key
- Directory watch + batch JSON ingestion with transaction safety (all-or-nothing per file)
- Manual review: searchable event list, canonical-to-source drill-down, split and merge operations
- Match confidence indicators in the review UI

**Should have (competitive differentiators):**
- Tiered matching: deterministic fast path + LLM fallback for ambiguous cases
- German-language synonym dictionary (Fasnet/Fasching/Fastnacht/Karneval etc.)
- Category-aware matching weights (carnival season needs different calibration)
- Match decision audit log (all decisions, not just matches -- essential for debugging)
- Manual review queue with prioritization by uncertainty score
- Location normalization layer (standardize "Marktplatz" to "Marktplatz, Waldkirch" from context)
- Batch processing dashboard (operational visibility)

**Defer (v2+):**
- Feedback loop for automated threshold tuning (needs labeled data accumulation first)
- Duplicate cluster visualization (nice-to-have, not blocking)
- Incremental blocking key indexing (only needed if volume grows past 10K/week)

**Anti-features (explicitly excluded):**
- Real-time streaming (source files arrive in weekly batches; batch is sufficient and far simpler)
- User authentication (internal tool; add reverse-proxy auth later if needed)
- Mobile-responsive frontend (desktop-only audience; responsive doubles frontend effort)
- ML model training (insufficient labeled data; LLM outperforms at this scale)
- Elasticsearch/Solr (PostgreSQL pg_trgm handles this volume trivially)

### Architecture Approach

The system follows the canonical record linkage pipeline architecture: a stateless pipeline (file watcher -> preprocessor -> blocker -> Tier 1 matcher -> Tier 2 AI matcher -> clusterer -> canonicalizer -> PostgreSQL) running as a batch worker process, plus a separate FastAPI server for the frontend API. Both share the same Python codebase and PostgreSQL database but run as distinct Docker containers. This is a monolith with module boundaries, not microservices -- the scale does not justify service decomposition.

See ARCHITECTURE.md for the full data flow diagrams, API endpoint design, and database schema.

**Major components:**
1. File Watcher (watchfiles) -- detects new JSON files in watched directory, triggers pipeline
2. Preprocessor -- normalizes text (lowercase, umlauts, prefix stripping), parses dates to canonical format, generates blocking keys
3. Blocker -- queries PostgreSQL for existing canonical events matching blocking keys (date+city, date+geo grid); reduces O(n*m) to O(k*n) where k=5-50
4. Tier 1 Matcher -- weighted scoring: date (0.30) + location (0.25) + title (0.30) + description (0.15); routes to match / no-match / ambiguous
5. Tier 2 Matcher (AI) -- sends ambiguous pairs to gpt-4o-mini with structured prompt; requires structured JSON output with decision + confidence + reasoning
6. Clusterer (networkx) -- builds match graph, finds connected components, validates cluster coherence, flags over-large clusters for review
7. Canonicalizer -- field-level best-value selection with explicit per-field rules and source provenance tracking
8. Persistence Layer (SQLAlchemy + asyncpg) -- upserts canonical events, inserts source links, records all match decisions including no-matches
9. API Server (FastAPI) -- REST API for frontend: event list/search, detail/source drill-down, review queue, split/merge operations
10. Frontend (React + TanStack) -- searchable event list, canonical-source comparison, manual review UI

**Key database tables:** canonical_events, source_events (with canonical_event_id FK), match_decisions (all decisions + tier + reasoning), manual_overrides (audit of human corrections)

### Critical Pitfalls

See PITFALLS.md for full details including warning signs and detection methods.

1. **Pairwise matching instead of clustering** -- model deduplication as connected-component discovery from day one; using union-find or networkx. Retrofitting clustering onto a pairwise system is a near-complete rewrite. (CRITICAL -- must be in initial design)

2. **String similarity alone for German titles** -- title is one of four signals, not the primary one; build normalization pipeline (lowercase, umlaut normalization, prefix stripping, synonym dictionary: Fasnet=Fasching=Fastnacht) before any comparison runs. (CRITICAL -- in core matching design)

3. **No date windowing in blocking** -- date overlap must be the first and hardest blocking pass; without it, recurring events (weekly markets, annual Fasnet) merge across time and processing time grows linearly with database size. (CRITICAL -- Phase 1 correctness and performance requirement)

4. **No ground truth dataset before building** -- before writing matching code, manually label 200-300 event pairs from the existing 765-event sample as same/different; this 2-4 hour investment enables measurable precision/recall and is the single highest-ROI task in the project. (CRITICAL -- should be Phase 0)

5. **Geo coordinate false confidence** -- many events geocode to village centroids (same coordinates appear for multiple distinct venues); weight geo proximity by the confidence score of both events and treat geo with confidence < 0.85 as "unknown location" not a matching signal. (MODERATE -- in matching algorithm design)

6. **Same venue, different event** -- during Fasnet, a Halle hosts Kinderball at 14:00 and Preismaskenball at 20:00; strong location + date match is necessary but not sufficient -- require higher title similarity when location match is strong, and use time-of-day as additional signal. (MODERATE -- matching refinement)

## Implications for Roadmap

Based on combined research, the architecture and pitfalls research agree on a clear dependency order. The suggested phase structure below maps directly to the ARCHITECTURE.md build order, adjusted to front-load the ground truth creation that PITFALLS.md identifies as the single highest-ROI task.

### Phase 0: Ground Truth and Evaluation Harness

**Rationale:** All threshold tuning is guesswork without labeled pairs. PITFALLS.md identifies this as the single highest-value task (2-4 hours of manual work saves weeks of blind tuning). No matching code can be validated without an evaluation harness to measure precision/recall.
**Delivers:** 200-300 labeled event pairs (same/different) from the existing 765-event sample; evaluation harness that reports precision, recall, F1 per category; baseline accuracy measurement.
**Addresses:** PITFALL #4 (threshold tuning without ground truth)
**Avoids:** Entering endless tuning loops with no ability to measure improvement
**Research flag:** Standard practice in entity resolution -- no additional research needed, execution-focused work.

### Phase 1: Foundation -- Database Schema, Data Models, and Preprocessor

**Rationale:** Everything depends on a stable data model and the ability to read/write PostgreSQL. The preprocessor (normalization) must exist before any matching can be built. ARCHITECTURE.md is explicit: database first because you cannot test matching without persisting results.
**Delivers:** PostgreSQL schema (canonical_events, source_events, match_decisions, manual_overrides, blocking_keys); SQLAlchemy models with Alembic migrations; normalization pipeline (lowercase, umlaut handling, date parsing, blocking key generation); JSON ingestion with idempotency (source event ID as natural key).
**Addresses:** Directory watch + JSON ingestion (table stakes), idempotent processing (table stakes), source event preservation (table stakes)
**Uses:** PostgreSQL + pg_trgm + unaccent extensions, SQLAlchemy 2.0, asyncpg, Alembic, watchfiles
**Avoids:** PITFALL #9 (non-idempotent processing), PITFALL #13 (unicode normalization), PITFALL #10 (multi-date event normalization)
**Research flag:** Well-documented patterns. Standard FastAPI + SQLAlchemy stack with established conventions. No additional research phase needed.

### Phase 2: Core Matching Pipeline -- Blocker, Tier 1 Matcher, Clusterer, Canonicalizer

**Rationale:** This is the core value of the system. ARCHITECTURE.md notes this must come before AI matching because you need to understand the score distribution before calibrating the ambiguous zone. PITFALLS.md is clear: blocking and clustering must be designed from scratch correctly -- they cannot be bolted on later.
**Delivers:** Blocking by date+city and date+geo grid; weighted multi-signal Tier 1 scoring (date + geo + title + description); networkx-based graph clustering with coherence validation; field-level canonicalization with provenance; complete match decision audit log (all decisions, not just matches); evaluated against ground truth with precision/recall reporting.
**Addresses:** Multi-signal similarity scoring, blocking/candidate reduction, date matching with tolerance, geo-proximity matching, fuzzy title matching, canonical synthesis, confidence scoring (all table stakes)
**Uses:** rapidfuzz, scikit-learn TfidfVectorizer, geopy, networkx, PostgreSQL pg_trgm
**Implements:** Blocker, Tier 1 Matcher, Clusterer, Canonicalizer, Persistence Layer components
**Avoids:** PITFALL #1 (pairwise instead of clustering), PITFALL #2 (string similarity only), PITFALL #3 (no date windowing), PITFALL #5 (merge field conflicts), PITFALL #6 (geo false confidence), PITFALL #7 (blocking too aggressive/loose), PITFALL #11 (same-venue different event)
**Research flag:** Entity resolution patterns are mature and well-documented. The German-language synonym dictionary and umlaut normalization may benefit from a targeted research pass on German NLP preprocessing conventions.

### Phase 3: File Watcher and End-to-End Pipeline Integration

**Rationale:** Wire Phase 1 (ingestion) and Phase 2 (matching) into a working end-to-end pipeline. This is the first moment the system actually processes real files and produces canonical events. Must verify idempotency, transaction safety, and error handling on real data before building the UI on top of it.
**Delivers:** Complete working pipeline: JSON file drop -> deduplication -> canonical events in PostgreSQL; transaction-wrapped batch processing (all-or-nothing per file); file hash tracking; structured per-file processing logs; processing status stored to database.
**Addresses:** Batch processing with transaction safety, processing status and logging (table stakes)
**Uses:** watchfiles, asyncio, Python logging
**Avoids:** PITFALL #9 (idempotency), partial-file processing failures
**Research flag:** Standard asyncio + watchfiles integration. No additional research needed.

### Phase 4: API Server

**Rationale:** The API contract must exist before the frontend can be built. Can begin during Phase 2-3 once the database schema is stable. ARCHITECTURE.md recommends starting this early as it runs independently.
**Delivers:** FastAPI REST API: GET /events (paginated, searchable), GET /events/:id (with sources), GET /events/:id/matches (match decisions), POST /events/:id/split, POST /events/merge, GET /review-queue; OpenAPI docs auto-generated; pagination, filtering, full-text search on canonical events.
**Addresses:** Searchable canonical event list (table stakes -- backend portion)
**Uses:** FastAPI, Pydantic v2, SQLAlchemy async queries, PostgreSQL tsvector for full-text search
**Implements:** API Server component
**Avoids:** Schema drift between API and frontend by establishing the contract early
**Research flag:** Well-documented FastAPI patterns. No additional research needed.

### Phase 5: Frontend -- Browse and Search

**Rationale:** Users need to see what the system produced before they can review and correct it. Browse/search comes before the review UI because operators need situational awareness first. FEATURES.md notes the dependency: searchable list -> drill-down -> manual review.
**Delivers:** React SPA with searchable paginated canonical event list; canonical-to-source drill-down view with side-by-side source comparison; match confidence indicators (per-source signal scores); Vite build served from nginx container.
**Addresses:** Searchable canonical event list, canonical-to-source drill-down, match confidence indicators (table stakes)
**Uses:** React 19, Vite, TanStack Table, TanStack Query, Tailwind CSS
**Research flag:** Standard React + TanStack stack. No additional research needed.

### Phase 6: Tier 2 AI-Assisted Matching

**Rationale:** Build AI matching after deterministic matching is tuned because you need real score distributions from Phase 2 to define the ambiguity zone correctly. PITFALLS.md warns that building AI matching before knowing what "ambiguous" looks like in practice leads to miscalibrated thresholds.
**Delivers:** LLM integration (gpt-4o-mini) for pairs scoring between LOW_THRESHOLD and HIGH_THRESHOLD; structured prompt with both events' normalized fields + deterministic score breakdown; structured JSON response (decision + confidence + reasoning); response caching to avoid re-evaluating same pairs; AI decision logging in match_decisions table; cost monitoring.
**Addresses:** Tiered matching with AI fallback (differentiator)
**Uses:** openai SDK, structured outputs (response_format), httpx
**Implements:** Tier 2 Matcher component
**Avoids:** PITFALL #8 (AI black box), PITFALL #14 (under-using AI from cost fear), PITFALL #4 (AI accuracy measured against ground truth)
**Research flag:** Structured outputs with gpt-4o-mini for entity matching is a well-documented pattern. May benefit from targeted research on optimal prompt design for German-language event comparison.

### Phase 7: Frontend -- Manual Review and Override UI

**Rationale:** With AI matching in place (Phase 6), the review queue contains only the genuinely hard cases, making the review UI more immediately useful. FEATURES.md notes the dependency: manual review requires confidence indicators (Phase 5) and the match decision audit log (Phase 2).
**Delivers:** Review queue UI sorted by match uncertainty; manual split (detach source event from canonical, create new canonical or assign to another); manual merge (combine two canonicals, re-synthesize fields); manual override audit trail; batch processing dashboard showing match rates and error trends.
**Addresses:** Manual split/merge (table stakes), manual review queue with prioritization (differentiator), batch processing dashboard (differentiator)
**Uses:** React, TanStack Table, FastAPI split/merge endpoints
**Implements:** Frontend (Review + Manual Override) component
**Research flag:** Standard CRUD patterns for review queues. No additional research needed.

### Phase 8: Accuracy Improvements and Operational Excellence

**Rationale:** After the full pipeline is running and operators are using the review queue, the match decision audit log and manual override data provide the empirical basis for targeted accuracy improvements. FEATURES.md categorizes these as differentiators -- valuable but dependent on operational data.
**Delivers:** German dialect synonym dictionary (Fasnet/Fasching/Fastnacht/Karneval); category-aware matching weights (carnival vs. political event calibration); location normalization layer; source-type-aware comparison weights (artikel vs. terminliste); match decision audit log UI; feedback loop foundation (operator review decisions as implicit threshold calibration data).
**Addresses:** German-language-aware text similarity, category-aware matching weights, location normalization layer, source-type bias handling (differentiators); PITFALL #2 deeper resolution, PITFALL #12 (source-type bias), PITFALL #17 (seasonal robustness)
**Research flag:** German compound word normalization may benefit from research into existing German NLP libraries (spaCy de, HanTa stemmer). Category-aware threshold modeling needs empirical data from Phase 2-7 operation before being designed.

### Phase 9: Docker and Deployment

**Rationale:** Containerize all services and finalize docker-compose for the production stack. ARCHITECTURE.md specifies 3 containers: API server, pipeline worker, frontend (nginx). Defer until all functionality is working locally.
**Delivers:** Multi-stage Dockerfiles for Python services (slim) and frontend (nginx); docker-compose.yml defining the full stack (worker, api, frontend, postgresql for dev); environment-based configuration; production deployment documentation.
**Uses:** Docker, Docker Compose v2, nginx
**Research flag:** Standard Docker multi-container patterns. No additional research needed.

### Phase Ordering Rationale

- Ground truth first (Phase 0) because threshold tuning without labeled data is guesswork, and this 2-4 hour investment unlocks measurable accuracy tracking for all subsequent phases
- Database and preprocessor before matching (Phase 1 before Phase 2) because the data model must be stable before matching logic can be built or tested
- Core deterministic matching before AI matching (Phase 2 before Phase 6) because you must understand the score distribution to calibrate the ambiguity zone -- building AI matching first would be optimizing blindly
- API before frontend (Phase 4 before Phase 5) because the API contract defines what the frontend can display; misalignment here causes rework
- Browse/search before review UI (Phase 5 before Phase 7) because operators need to see events in context before performing corrections
- AI matching before review UI (Phase 6 before Phase 7) because the review queue is smaller and more useful when AI has already resolved the clear ambiguous cases
- Accuracy improvements after operational data (Phase 8 last) because the synonym dictionary and category weights should be calibrated against real data, not designed in a vacuum

### Research Flags

Phases likely needing a deeper research pass during planning:
- **Phase 2 (German NLP):** The German-specific text normalization (compound word splitting, dialect synonyms, OCR artifact handling) may benefit from a targeted research pass on available German NLP preprocessing tools (spaCy de, HanTa, custom approaches). The core matching algorithm design is standard entity resolution; it is specifically the German language adaptation that is less documented.
- **Phase 6 (AI prompt design):** Optimal structured prompt design for German-language event comparison with gpt-4o-mini is worth a targeted research pass. Specifically: how to represent multi-field events, how to handle bilingual/dialect inputs, and how to calibrate the confidence threshold in the structured response.

Phases with standard patterns (skip research-phase):
- **Phase 0:** Manual labeling workflow -- straightforward data annotation task
- **Phase 1:** FastAPI + SQLAlchemy 2.0 + Alembic stack -- well-documented, mature patterns
- **Phase 3:** watchfiles + asyncio file pipeline -- simple integration
- **Phase 4:** FastAPI REST API design -- standard CRUD + search patterns
- **Phase 5:** React + TanStack Table/Query -- well-documented component library patterns
- **Phase 7:** Review queue CRUD patterns -- standard frontend patterns
- **Phase 9:** Docker multi-container deployment -- standard patterns

## Confidence Assessment

| Area | Confidence | Notes |
|------|------------|-------|
| Stack | HIGH | Library choices (rapidfuzz, FastAPI, SQLAlchemy, React, networkx) are stable, mature, actively maintained. Specific version numbers are based on training data through mid-2025 and should be verified against PyPI/npm before development. No live web search was available during research. |
| Features | MEDIUM-HIGH | Table stakes features derived from direct analysis of 765 events in the /eventdata/ directory and established entity resolution patterns. Differentiator prioritization is based on the same well-established domain knowledge. Confidence is high for core features; medium for later-phase operational features. |
| Architecture | MEDIUM-HIGH | Pipeline architecture for entity resolution is a mature, stable pattern documented in academic literature (Fellegi-Sunter 1969, Christen 2012) and major open-source frameworks (dedupe, Splink, recordlinkage). The specific component boundaries and data flow are direct applications of these patterns to the project constraints. No live documentation verification was possible. |
| Pitfalls | HIGH | The critical pitfalls (clustering vs. pairwise, German string matching, date windowing, ground truth) are derived from direct analysis of the actual event data files and are domain-specific to this project. The sample data clearly exhibits the patterns (same venue multiple events, Fasnet density, artikel vs terminliste title variation) that drive each pitfall. General pitfalls are from established entity resolution literature. |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address

- **Exact library versions:** All recommended minimum versions (FastAPI >=0.115, SQLAlchemy >=2.0, rapidfuzz >=3.10, etc.) should be verified against PyPI before development begins. Run `uv add <package>` without version pins and let the resolver find the latest. Web search was unavailable during research.
- **German NLP tooling:** The research recommends building a custom normalization pipeline and synonym dictionary rather than relying on a specific library. During Phase 2 planning, a targeted investigation of spaCy's German model, HanTa stemmer, and existing Fasnet/German event synonym resources would improve the normalization approach.
- **LLM prompt design:** The recommended gpt-4o-mini approach is well-founded on cost and capability grounds, but the optimal prompt structure for this specific German-language event comparison task should be prototyped and evaluated against the ground truth dataset before committing to a final design.
- **PostGIS availability:** The stack leverages PostGIS for geographic queries. If the existing production PostgreSQL instance does not have PostGIS installed, the geo proximity matching will need an alternative (pure-Python haversine via geopy, which is the stack recommendation anyway). Verify PostGIS availability in the production environment early.
- **Threshold calibration:** The suggested Tier 1 thresholds (HIGH=0.85, LOW=0.40) and signal weights (date 0.30, location 0.25, title 0.30, description 0.15) are reasonable starting points from the domain literature but must be calibrated against the ground truth dataset in Phase 0/2. Do not treat these as final values.

## Sources

### Primary (HIGH confidence)
- Direct analysis of 765 events across ~20 source files in /eventdata/ -- data-specific observations, title patterns, Fasnet density, source type differences
- PROJECT.md -- project constraints, 65% current accuracy baseline, technology requirements (Docker, PostgreSQL, JSON input, 2000 events/week)
- entity resolution pipeline architecture (Fellegi-Sunter model, Christen "Data Matching" 2012) -- pipeline stages, blocking strategy, clustering approach

### Secondary (MEDIUM confidence)
- Open-source entity resolution frameworks (dedupe.io, Splink, recordlinkage, Zingg) -- component boundary patterns, blocking key design, clustering validation
- FastAPI, SQLAlchemy 2.0, rapidfuzz, networkx documentation -- library capabilities and recommended usage patterns (from training data through mid-2025)
- Production entity resolution system patterns (Clearbit, ZoomInfo, data integration vendors) -- tiered matching with AI fallback

### Tertiary (LOW confidence -- needs live verification)
- Specific version numbers for all Python packages and npm packages -- should be verified against PyPI/npm before development begins
- gpt-4o-mini structured output behavior for entity matching -- should be prototyped before full Phase 6 implementation

---
*Research completed: 2026-02-27*
*Ready for roadmap: yes*
