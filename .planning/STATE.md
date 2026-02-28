# Project State

## Project Reference

See: .planning/PROJECT.md (updated 2026-02-27)

**Core value:** Accurate event deduplication -- the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.
**Current focus:** Phase 2: Core Matching Pipeline -- IN PROGRESS

## Current Position

Phase: 2 of 7 (Core Matching Pipeline) -- IN PROGRESS
Plan: 3 of 4 in current phase (02-01, 02-02, 02-03 complete)
Status: Graph-based clustering with coherence validation complete. Next: 02-04 (canonical event synthesis)
Last activity: 2026-02-28 -- Completed 02-03 (graph clustering + coherence)

Progress: [████░░░░░░] 30%

## Performance Metrics

**Velocity:**
- Total plans completed: 7
- Average duration: 4m
- Total execution time: 0.43 hours

**By Phase:**

| Phase | Plans | Total | Avg/Plan |
|-------|-------|-------|----------|
| 1 | 4/4 | 20m | 5m |
| 2 | 3/4 | 11m | 3.7m |

**Recent Trend:**
- Last 5 plans: 01-04 (5m), 02-01 (5m), 02-02 (4m), 02-03 (2m)
- Trend: accelerating

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
Stopped at: Completed 02-03-PLAN.md (graph clustering + coherence validation)
Resume file: .planning/phases/02/02-04-PLAN.md
Next action: Execute 02-04 (canonical event synthesis + enrichment)
