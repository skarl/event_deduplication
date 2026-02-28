# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** Accurate event deduplication -- the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.
**Current focus:** Phase 5: AI-Assisted Matching -- IN PROGRESS

## Current Position

Phase: 5 of 7 (AI-Assisted Matching) -- IN PROGRESS
Plan: 1 of 2 in current phase (05-01 complete, 05-02 planned)
Status: Plan 05-01 (AI Matching Infrastructure) complete. Ready for 05-02.
Last activity: 2026-02-28 -- Plan 05-01 executed (2 tasks, 19 tests, 3m)

Progress: [███████░░░] 64%

## Performance Metrics

**Velocity:**
- Total plans completed: 13
- Average duration: 4.0m
- Total execution time: 0.87 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 4/4 | 20m | 5m |
| 2 | 4/4 | 17m | 4.3m |
| 3 | 2/2 | 7m | 3.5m |
| 4 | 2/2 | 13m | 6.5m |
| 5 | 1/2 | 3m | 3m |

**Recent Trend:**
- Last 5 plans: 03-01 (5m), 03-02 (2m), 04-01 (8m), 04-02 (5m), 05-01 (3m)
- Trend: steady

*Updated after each plan completion*

## Accumulated Context

### Decisions

Decisions are logged in PROJECT.md Key Decisions table.
Recent decisions affecting current work:

- [01-01]: Use JSON type instead of JSONB/ARRAY for SQLite test compatibility
- [01-01]: Use sa.text("CURRENT_TIMESTAMP") for server defaults (PG + SQLite compatible)
- [01-01]: Use hatchling build backend with src layout
- [01-01]: Added sqlalchemy[asyncio] extra for greenlet dependency
- [01-01]: Alembic env.py supports ALEMBIC_DATABASE_URL env override
- [Roadmap]: Use Gemini Flash (not GPT-4o-mini) for AI-assisted matching in Phase 5
- [Roadmap]: Ground truth dataset creation merged with foundation phase (both are prerequisites with no dependencies)
- [Roadmap]: Docker deployment merged with pipeline integration (both deliver "the system runs as a service")
- [01-02]: Unicode NFC before umlaut expansion for composed+decomposed form handling
- [01-02]: Prefixes.yaml uses original German forms (real umlauts), matching before normalization
- [01-02]: FileProcessor loads configs at init, not per-file
- [01-03]: Hard negative sampling skips when ratio=0.0 (no forced minimum of 1)
- [01-03]: Evaluation harness uses pure function extraction for all blocking/pairing logic
- [01-03]: Check constraints use SQLAlchemy CheckConstraint for SQLite+PG compatibility
- [01-04]: Auto-generate ground truth instead of manual labeling (project goal is automation)
- [01-04]: Conservative multi-signal heuristics: title_sim>=0.90+same_city for "same", title_sim<0.40 for "different"
- [01-04]: Ambiguous pairs (0.40-0.90 with mixed signals) excluded from ground truth for reliability
- [02-01]: Scorers are pure functions taking dict args for testability and decoupling from ORM
- [02-01]: MatchDecision uses canonical ordering constraint (id_a < id_b) matching GroundTruthPair pattern
- [02-02]: Candidate pairs deduplicated via set across blocking groups
- [02-02]: Cross-source enforcement at pair generation level, not pipeline level
- [02-02]: Pipeline is a pure function (no DB access) taking event dicts and MatchingConfig
- [02-02]: get_match_pairs() provides the interface for Plan 02-03 clustering
- [02-03]: Singletons (unmatched events) included in clusters list as size-1 sets for downstream uniformity
- [02-03]: Flagged clusters separated from valid clusters -- both tracked in ClusterResult for review workflows
- [02-03]: Date spread limit of >3 distinct dates catches unrelated events bridged by false positives
- [02-03]: Coherence checks short-circuit: size -> similarity -> date spread (cheapest first)
- [02-04]: Lazy imports in pipeline.py to break circular dependency (pipeline -> clustering -> pipeline)
- [02-04]: TYPE_CHECKING guard for ClusterResult type annotation in PipelineResult dataclass
- [02-04]: Provenance uses "union_all_sources" for list/date fields since multiple sources contribute
- [02-04]: Boolean provenance tracks first source with True value
- [03-01]: Explicit CanonicalEventSource delete before CanonicalEvent delete for SQLite CASCADE compatibility
- [03-01]: Source links derived from cluster membership (not field_provenance) for completeness
- [03-01]: Separate transactions for file ingestion and canonical persistence (clear-and-replace rebuilds all)
- [03-02]: Python-based health check in Dockerfile.api (urllib.request) to avoid installing curl in slim image
- [03-02]: Generic entrypoint.sh with exec "$@" so both worker and API containers share the same entrypoint
- [03-02]: httpx added to dev dependencies for FastAPI TestClient support
- [04-01]: BeforeValidator for date/time to string coercion in EventDateSchema
- [04-01]: Category filtering uses ILIKE on cast(JSON, String) for SQLite+PG compatibility
- [04-02]: Vite React-TS with @tailwindcss/vite plugin (no PostCSS config needed)
- [04-02]: TanStack Query with keepPreviousData for smooth pagination
- [04-02]: URL search params for filter/page state (enables browser back/forward)
- [04-02]: Hand-crafted Tailwind components instead of component library (minimal deps)
- [04-02]: Multi-stage Docker build (Node 22 build + Nginx alpine serve)
- [05-01]: google-genai SDK (unified, not deprecated google-generativeai) for Gemini API access
- [05-01]: Content-hash cache uses SHA-256 of matching-relevant fields only, with canonical ID ordering
- [05-01]: Cache staleness detection by model name comparison (auto-invalidates on model upgrade)
- [05-01]: AIMatchingConfig defaults to enabled=False for safe rollout
- [05-01]: Gemini 2.5 Flash pricing for cost estimation (0.30/1M input, 2.50/1M output)

### Ground Truth Dataset

Generated: 1181 labeled pairs (248 same, 933 different, 157 ambiguous skipped)
Database: ground_truth.db (SQLite, loadable by evaluation harness)
Regenerate: `uv run python scripts/generate_ground_truth.py`

Baseline evaluation (title-only matching):
- Best F1: 1.00 at threshold 0.70 (but this is expected since ground truth uses 0.90 threshold)
- Phase 2 multi-signal matching will be measured against this ground truth

### Pending Todos

None yet.

### Blockers/Concerns

None yet.

## Session Continuity

Last session: 2026-02-28
Stopped at: Completed 05-01-PLAN.md
Resume file: N/A
Next action: Execute Plan 05-02 (pipeline integration)
