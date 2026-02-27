# Architecture Patterns

**Domain:** Event deduplication / entity resolution service
**Researched:** 2026-02-27
**Overall confidence:** MEDIUM-HIGH (based on well-established entity resolution patterns; web verification unavailable, but this is a mature domain with stable architecture conventions)

## Recommended Architecture

### High-Level: Pipeline Architecture with Tiered Matching

Event deduplication systems follow a **pipeline architecture** (also called a "record linkage pipeline" in the academic literature). The canonical stages are well-established across libraries like `dedupe`, `recordlinkage`, Zingg, and Splink:

```
                        +-------------------+
                        |  File Watcher     |
                        |  (Ingestion)      |
                        +--------+----------+
                                 |
                                 v
                        +-------------------+
                        |  Preprocessing    |
                        |  (Normalize/      |
                        |   Standardize)    |
                        +--------+----------+
                                 |
                                 v
                        +-------------------+
                        |  Blocking         |
                        |  (Candidate       |
                        |   Selection)      |
                        +--------+----------+
                                 |
                                 v
                   +-------------+-------------+
                   |                           |
                   v                           v
          +----------------+          +-----------------+
          |  Tier 1:       |          |  Tier 2:        |
          |  Deterministic |--ambig-->|  AI-Assisted    |
          |  Matching      |          |  Matching       |
          +-------+--------+          +--------+--------+
                  |                            |
                  +------------+---------------+
                               |
                               v
                      +-------------------+
                      |  Clustering       |
                      |  (Group Events)   |
                      +--------+----------+
                               |
                               v
                      +-------------------+
                      |  Canonicalization |
                      |  (Merge Best      |
                      |   Fields)         |
                      +--------+----------+
                               |
                               v
                      +-------------------+
                      |  Persistence      |
                      |  (PostgreSQL)     |
                      +--------+----------+
                               |
                               v
                      +-------------------+
                      |  Frontend         |
                      |  (Browse/Review)  |
                      +-------------------+
```

This is **not a microservices architecture**. For a service processing 2000+ events/week, a monolithic pipeline with clearly separated modules is the right call. Microservices would add deployment complexity without meaningful scalability benefits at this volume.

### Component Boundaries

| Component | Responsibility | Communicates With | Technology |
|-----------|---------------|-------------------|------------|
| **File Watcher** | Monitors directory for new JSON files, triggers pipeline | Preprocessing | `watchdog` or `inotify` |
| **Preprocessor** | Normalizes text, standardizes locations, parses dates | Blocking | Pure Python/library functions |
| **Blocker** | Reduces comparison space by grouping candidate pairs | Matcher (Tier 1) | PostgreSQL (read existing events) |
| **Tier 1 Matcher** | Fast deterministic matching on exact/near-exact signals | Clustering (matches), Tier 2 (ambiguous) | In-memory computation |
| **Tier 2 Matcher** | AI-assisted matching for ambiguous candidate pairs | Clustering | LLM API (OpenAI/Anthropic) |
| **Clusterer** | Groups matched pairs into transitive clusters | Canonicalizer | Graph algorithms |
| **Canonicalizer** | Selects best field values from cluster members | Persistence | Field-level merge rules |
| **Persistence Layer** | Reads/writes canonical events + source links to PostgreSQL | PostgreSQL, All upstream readers | SQLAlchemy / asyncpg |
| **API Server** | Serves data to frontend, handles manual review actions | Frontend, Persistence | FastAPI |
| **Frontend** | Browse, search, review, manual corrections | API Server | React / Next.js or similar SPA |

### Data Flow

#### Ingest Flow (Batch Processing)

```
1. JSON file lands in watched directory
2. File Watcher detects new file, reads and validates JSON
3. Events are extracted and sent to Preprocessor
4. Preprocessor normalizes each event:
   - Lowercase + strip titles/descriptions
   - Standardize location names (Marktplatz -> marktplatz waldkirch)
   - Parse dates to canonical format
   - Generate text fingerprints for comparison
5. Preprocessor output: list of NormalizedEvent records
```

#### Matching Flow (Core Logic)

```
6. Blocker queries PostgreSQL for existing canonical events
7. Blocker generates candidate pairs using blocking keys:
   - Block 1: Same date + same city (most common block)
   - Block 2: Same date + geo proximity (<5km radius)
   - Block 3: Same week + high title similarity (phonetic/n-gram)
   Purpose: Avoid O(n^2) comparisons. Only compare events
   within the same block.

8. Tier 1 Matcher scores each candidate pair:
   - Date match (exact date = 1.0, adjacent day = 0.5)
   - Location match (geo distance, name similarity)
   - Title similarity (TF-IDF cosine, Jaro-Winkler, token overlap)
   - Combined weighted score

9. Tier 1 decision:
   - Score >= HIGH_THRESHOLD (e.g. 0.85): MATCH -> Clustering
   - Score <= LOW_THRESHOLD (e.g. 0.40): NO MATCH -> discard pair
   - Score in between: AMBIGUOUS -> Tier 2

10. Tier 2 Matcher (AI) for ambiguous pairs only:
    - Constructs structured prompt with both events' fields
    - Asks LLM: "Are these the same real-world event?"
    - LLM returns: match/no-match + confidence + reasoning
    - Result -> Clustering or discard
```

#### Clustering and Canonicalization Flow

```
11. Clusterer receives all confirmed match pairs
    - Builds graph: events = nodes, matches = edges
    - Finds connected components (transitive closure)
    - Each component = one group of duplicate events
    - Checks for over-merging: if a cluster spans
      multiple distinct dates/locations, flag for review

12. Canonicalizer for each cluster:
    - Title: longest non-generic title, or highest confidence source
    - Description: longest description
    - Highlights: union of all highlights
    - Location: most specific (most fields filled, highest geo confidence)
    - Dates: most precise (earliest start time if ranges differ)
    - Categories: union
    - Creates canonical_event record
    - Links all source_events to canonical_event

13. Persistence writes to PostgreSQL:
    - Upsert canonical_event (update if enriched)
    - Insert source_events with foreign key to canonical
    - Record match decisions for audit trail
```

#### Review Flow (Frontend)

```
14. API serves:
    - GET /events - paginated canonical events with search/filter
    - GET /events/:id - canonical event with all source events
    - GET /events/:id/matches - match decisions that formed this group
    - POST /events/:id/split - split a source event out of a group
    - POST /events/merge - merge two canonical events
    - GET /review-queue - events flagged for manual review

15. Frontend displays:
    - Event list with search (title, date, location, source)
    - Event detail showing canonical vs. source events side-by-side
    - Review queue showing flagged ambiguous matches
    - Manual merge/split controls
```

## Patterns to Follow

### Pattern 1: Blocking for Candidate Selection

**What:** Before comparing events pairwise, partition them into "blocks" sharing a common key, and only compare within blocks.

**When:** Always. Without blocking, comparing 2000 new events against 50,000 existing events requires 100 million comparisons. With blocking by date+city, each event typically compares against 5-50 candidates.

**Why critical for this project:** The PROJECT.md notes ~2000 events/week. After a few months the database will hold 20,000+ canonical events. Naive O(n*m) pairwise comparison would become the bottleneck.

**Implementation:**
```python
def generate_blocking_keys(event: NormalizedEvent) -> list[str]:
    """Generate multiple blocking keys for an event.
    An event can appear in multiple blocks to reduce missed matches."""
    keys = []
    for date in event.dates:
        # Block by date + city
        if event.location.city:
            keys.append(f"{date.date}|{event.location.city.lower()}")
        # Block by date + geo grid cell (for events with coords but different city names)
        if event.location.lat and event.location.lon:
            grid_lat = round(event.location.lat, 2)  # ~1km grid
            grid_lon = round(event.location.lon, 2)
            keys.append(f"{date.date}|{grid_lat}|{grid_lon}")
    return keys
```

### Pattern 2: Tiered Matching with Cost Gating

**What:** Use cheap deterministic matching first; only send ambiguous pairs to expensive AI matching.

**When:** When you have a cost constraint on AI calls (this project explicitly does).

**Why:** From the PROJECT.md data characteristics, many duplicates are near-identical (100% title match) or clearly different (different dates). Only the middle band (60-85% similarity) needs AI judgment. Expect ~10-20% of candidate pairs to be ambiguous.

**Implementation:**
```python
@dataclass
class MatchResult:
    pair: tuple[str, str]  # event IDs
    score: float
    tier: Literal["deterministic", "ai"]
    decision: Literal["match", "no_match", "review"]
    reasoning: str | None = None

def tier1_match(event_a: NormalizedEvent, event_b: NormalizedEvent) -> MatchResult:
    score = weighted_score(
        date_score(event_a, event_b) * 0.30,
        location_score(event_a, event_b) * 0.25,
        title_score(event_a, event_b) * 0.30,
        description_score(event_a, event_b) * 0.15,
    )
    if score >= 0.85:
        return MatchResult(pair=(...), score=score, tier="deterministic", decision="match")
    elif score <= 0.40:
        return MatchResult(pair=(...), score=score, tier="deterministic", decision="no_match")
    else:
        return MatchResult(pair=(...), score=score, tier="deterministic", decision="ambiguous")
```

### Pattern 3: Graph-Based Clustering with Transitivity

**What:** Build a graph of match decisions, then find connected components to form event groups.

**When:** When duplicates are transitive (if A=B and B=C, then A=C) -- which is the typical case for event deduplication.

**Why:** Pairwise matching alone can miss the link between A and C if they look dissimilar to each other. Transitivity through B catches this. However, transitivity can also cause "cluster drift" (false merges propagating through chains), so cluster validation is needed.

**Implementation:**
```python
import networkx as nx

def cluster_matches(match_results: list[MatchResult]) -> list[set[str]]:
    G = nx.Graph()
    for result in match_results:
        if result.decision == "match":
            G.add_edge(result.pair[0], result.pair[1], weight=result.score)

    clusters = list(nx.connected_components(G))

    # Validate clusters: check for over-merging
    validated = []
    for cluster in clusters:
        if is_cluster_coherent(cluster):
            validated.append(cluster)
        else:
            # Split into sub-clusters and flag for review
            sub_clusters = split_incoherent_cluster(cluster, G)
            validated.extend(sub_clusters)

    return validated
```

### Pattern 4: Field-Level Canonicalization with Provenance

**What:** For each field in the canonical event, select the "best" value from all source events using field-specific rules, and record which source each field came from.

**When:** Always when creating canonical records from duplicates.

**Why:** Different sources have different strengths. One source may have the best title, another the most complete address. Blindly picking the "first" or "newest" loses information.

**Implementation:**
```python
FIELD_STRATEGIES = {
    "title": "longest_non_generic",    # Prefer specific titles
    "description": "longest",           # More detail is better
    "highlights": "union",              # Combine all highlights
    "location_name": "most_specific",   # Most address fields filled
    "geo_coordinates": "highest_confidence",  # Use confidence score
    "categories": "union",              # Combine categories
    "dates": "most_precise",            # Most specific time range
    "admission_free": "any_true",       # If any source says free, it's free
}
```

### Pattern 5: Audit Trail for All Matching Decisions

**What:** Store every match decision (match, no-match, ambiguous) with score, tier, and reasoning.

**When:** Always. Essential for debugging, manual review, and improving thresholds over time.

**Why:** Without an audit trail, when a user sees a bad grouping in the frontend, they have no way to understand why it happened. The audit trail powers the review UI and enables threshold tuning.

## Anti-Patterns to Avoid

### Anti-Pattern 1: Naive Pairwise Comparison Without Blocking

**What:** Comparing every incoming event against every existing event.
**Why bad:** O(n*m) complexity. At 2000 events/week against a growing database, this becomes a performance cliff within months. Even with fast string comparison, 2000 * 50,000 = 100M comparisons is prohibitive.
**Instead:** Use blocking to reduce candidate pairs to O(k*n) where k is block size (typically 5-50).

### Anti-Pattern 2: Single Global Threshold for Match/No-Match

**What:** Using one threshold score to decide all matches.
**Why bad:** Different types of events have different similarity profiles. A music festival with a unique name matches differently from a "Wochenmarkt" (weekly market) that occurs in every town. A single threshold either misses duplicates of generic events or false-merges distinct events with similar names.
**Instead:** Use the tiered approach. The ambiguous zone is where interesting decisions happen, and AI matching can consider context that a score cannot.

### Anti-Pattern 3: Overwriting Instead of Linking

**What:** When a duplicate is found, updating the existing event record in-place.
**Why bad:** Destroys provenance. You can no longer tell which information came from which source. Makes it impossible to "undo" a bad merge or understand data lineage.
**Instead:** Always preserve original source events. Create a separate canonical event record that references its sources.

### Anti-Pattern 4: Calling AI for Every Pair

**What:** Sending all candidate pairs to an LLM for matching.
**Why bad:** At $0.01-0.03 per comparison (typical for a structured prompt), 10,000 pairs/week = $100-300/week. And it is slow -- API latency adds up quickly.
**Instead:** Tier 1 deterministic matching resolves 80-90% of pairs. Only the ambiguous 10-20% go to AI. Expected AI calls: 500-2000/week at this event volume.

### Anti-Pattern 5: Monolithic "One Query" Matching

**What:** Trying to do blocking, matching, and grouping in a single SQL query.
**Why bad:** SQL is not well-suited for fuzzy string matching, weighted scoring, or graph-based clustering. The logic becomes unmaintainable and hard to tune.
**Instead:** Use SQL for blocking (retrieve candidates), Python for matching (compute similarity scores), and a graph library for clustering.

## Database Schema (Logical)

```
canonical_events
  - id (PK)
  - title, description, short_description, highlights
  - location fields (name, city, street, zipcode, lat, lon, geo_confidence)
  - event_dates (jsonb or separate table)
  - categories, is_family_event, is_child_focused
  - admission_free, registration_required, registration_contact
  - created_at, updated_at
  - source_count (denormalized for quick display)
  - needs_review (boolean, flagged by clustering)

source_events
  - id (PK)
  - canonical_event_id (FK -> canonical_events, nullable until matched)
  - original JSON data (jsonb, preserves everything)
  - title, description (extracted for display)
  - source_type (bwb, emt, rks, etc.)
  - batch_file (which JSON file it came from)
  - ingested_at

match_decisions
  - id (PK)
  - source_event_id_a (FK)
  - source_event_id_b (FK)
  - score (float)
  - tier (deterministic / ai)
  - decision (match / no_match / ambiguous)
  - reasoning (text, especially for AI tier)
  - decided_at
  - overridden_by_user (boolean)

manual_overrides
  - id (PK)
  - action (split / merge)
  - source_event_id (for split: which event was removed)
  - from_canonical_id, to_canonical_id
  - reason (user-entered)
  - created_at

blocking_keys (optional, for performance)
  - source_event_id (FK)
  - block_key (indexed)
```

## Suggested Build Order (Dependencies)

The architecture has clear dependency chains that determine build order:

```
Phase 1: Foundation
  Database schema + Persistence layer + Preprocessor
  (Everything depends on having a data model and being able to read/write)

Phase 2: Core Matching Pipeline
  Blocker + Tier 1 Matcher + Clusterer + Canonicalizer
  (Requires: Phase 1. This is the core value of the system.)

Phase 3: File Watcher + End-to-End Pipeline
  Wire up ingestion -> matching -> persistence into a working pipeline
  (Requires: Phases 1-2. Now the system actually processes files.)

Phase 4: API Server
  REST API serving canonical events, source events, match decisions
  (Requires: Phase 1 at minimum. Can start during Phase 2-3.)

Phase 5: Frontend (Browse + Search)
  Event list, detail views, search functionality
  (Requires: Phase 4.)

Phase 6: Tier 2 AI Matching
  LLM integration for ambiguous pairs
  (Requires: Phase 2 Tier 1 working. Build after deterministic matching
   is tuned, so you know what "ambiguous" actually looks like in practice.)

Phase 7: Frontend (Review + Manual Override)
  Review queue, split/merge UI
  (Requires: Phases 4-5 + audit trail from Phase 2.)

Phase 8: Docker + Deployment
  Containerization, docker-compose, production configuration
  (Requires: All above working locally.)
```

**Rationale for this ordering:**

1. **Database first** because everything reads/writes PostgreSQL. You cannot test matching without persisting results.
2. **Core matching before AI** because you need to understand the distribution of scores before setting thresholds for the ambiguous zone. Building AI matching first would be optimizing without data.
3. **API before frontend** because the API contract defines what the frontend can display.
4. **Browse before review** because users need to see events before they can review grouping decisions.
5. **AI matching before review UI** is a judgment call. You could swap Phases 6 and 7. But having AI matching first means the review queue is smaller (fewer ambiguous decisions left unresolved), making the review UI more useful from the start.

## Scalability Considerations

| Concern | At 2K events/week (current) | At 20K events/week | At 200K events/week |
|---------|----------------------------|---------------------|----------------------|
| **Blocking** | In-memory blocking keys | Index blocking keys in PostgreSQL | Dedicated blocking table + batch queries |
| **Matching** | Single-threaded Python | Parallel matching with multiprocessing | Worker queue (Celery/RQ) |
| **AI calls** | Sequential API calls | Batch API calls with concurrency | Need cost/latency optimization |
| **Clustering** | NetworkX in-memory | NetworkX (handles 100K+ nodes fine) | Consider incremental clustering |
| **Database** | Single PostgreSQL | Single PostgreSQL (still fine) | Read replicas, partitioning |
| **Frontend** | Simple SPA | Add pagination, lazy loading | Server-side search (Elasticsearch) |

At 2000 events/week, the architecture is intentionally simple. Single-process Python, single PostgreSQL instance, no message queues, no caching layers. The pipeline processes a batch in seconds to minutes, which is perfectly adequate.

**When to add complexity:** If event volume exceeds 10K/week or the database grows past 500K events, consider adding: (1) persistent blocking key index, (2) parallel matching workers, (3) batch AI API calls.

## Key Architectural Decisions

### Batch vs. Streaming
**Decision:** Batch processing triggered by file arrival.
**Rationale:** Events arrive as JSON files from a batch extraction pipeline. There is no real-time requirement. Batch is simpler, easier to debug, and easier to retry on failure.

### Monolith vs. Microservices
**Decision:** Monolithic Python service with clear module boundaries.
**Rationale:** At 2000 events/week, there is zero need for horizontal scaling of individual components. A monolith is simpler to deploy, debug, and maintain. Docker provides isolation from the host.

### Separate API Server vs. Embedded in Pipeline
**Decision:** Separate process. Pipeline runs on file events; API server runs continuously.
**Rationale:** The pipeline is batch-oriented and should not be blocked by HTTP requests. The API server needs to be always-available for the frontend. Docker Compose makes running two containers trivial.

### Match Decision Storage
**Decision:** Store all match decisions, not just matches.
**Rationale:** "No match" decisions are as important as "match" decisions for debugging and threshold tuning. Disk is cheap; lost debugging information is expensive.

## Sources

- Entity resolution pipeline architecture is well-documented in academic literature (Fellegi-Sunter model, 1969; Christen "Data Matching", 2012) and implemented in open-source libraries: Python `dedupe` (dedupe.io), `recordlinkage`, Splink (UK Ministry of Justice), Zingg.
- Blocking strategies: standard approach documented across all major record linkage frameworks. The multi-key blocking approach is recommended by dedupe.io and Splink documentation.
- Tiered matching pattern: common in production entity resolution systems at companies like Clearbit, ZoomInfo, and data integration vendors.
- Graph-based clustering for transitive closure: standard approach, implemented in NetworkX and used by Splink and dedupe.
- **Confidence note:** Architecture patterns described here are MEDIUM-HIGH confidence. They are well-established and stable patterns from the entity resolution domain. I was unable to verify against live documentation due to web access restrictions, but these patterns have been standard for 10+ years and are unlikely to have changed.
