# Phase 3: Pipeline Integration & Deployment - Research

**Researched:** 2026-02-28
**Domain:** Python async pipeline orchestration, Docker containerization, structured logging
**Confidence:** HIGH

## Summary

Phase 3 bridges the gap between Phase 2's pure-function matching pipeline and a running service. The core challenge is orchestration: when a JSON file arrives, the system must (1) ingest it via the existing FileProcessor, (2) load ALL source events from the database (not just the new file's events), (3) run the matching pipeline across all events, (4) persist canonical events and their source links to the database, and (5) report structured processing statistics.

The Docker infrastructure is straightforward: a multi-stage build using the official uv Docker image for fast dependency installation, docker-compose with PostgreSQL, and an entrypoint script that runs Alembic migrations before the worker starts. The matching strategy should be "full re-match on every file" for now -- the dataset is small enough (~2000 events/week) that this approach works without incremental matching complexity.

**Primary recommendation:** Use watchfiles for async file watching, structlog for JSON-formatted logging via ProcessorFormatter (captures both structlog and stdlib logging), and a simple "clear-and-replace" strategy for canonical events on each pipeline run to avoid complex incremental update logic.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| PIPE-01 | Docker container watches a configured directory for new JSON files | watchfiles `awatch` with custom filter for `.json` `Change.added` events; entrypoint as `python -m event_dedup.worker` |
| PIPE-05 | Structured processing logs report events processed, matches found, new canonicals created, and errors per file | structlog with ProcessorFormatter captures both structlog and stdlib logging; per-file stats dataclass logged as bound context |
| DEPL-01 | All services run as Docker containers (pipeline worker, API server, frontend) | Multi-stage Dockerfile with `ghcr.io/astral-sh/uv:python3.12-bookworm-slim`; separate Dockerfiles per service |
| DEPL-02 | docker-compose.yml defines the full stack including PostgreSQL for development | docker-compose with postgres healthcheck, volume mounts, environment variables; `depends_on: condition: service_healthy` |
| DEPL-03 | Environment-based configuration (database connection, watched directory, AI API keys, thresholds) | Already supported via `pydantic-settings` with `EVENT_DEDUP_` prefix; extend Settings model for new config |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| watchfiles | >=1.1 | Async file watching | Rust-based (Notify crate), async-native `awatch`, by Samuel Colvin (Pydantic author), 1600ms debounce default prevents duplicate events |
| structlog | >=25.5 | Structured JSON logging | ProcessorFormatter captures both structlog AND stdlib logging into unified JSON output; battle-tested since 2013 |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| ghcr.io/astral-sh/uv:python3.12-bookworm-slim | latest stable | Docker base image | Multi-stage build: builder with uv, runtime with python:3.12-slim-bookworm |
| postgres:16-alpine | 16.x | PostgreSQL for docker-compose | Alpine variant for small image size in development |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| watchfiles | watchdog | watchdog is callback-based, requires threading bridge for async; watchfiles is native async |
| watchfiles | Simple polling loop | Polling misses rapid changes, wastes CPU; watchfiles uses OS-level file system events |
| structlog | python-json-logger | python-json-logger only formats stdlib logging; structlog provides bound loggers with context accumulation |
| structlog | stdlib with JSON formatter | No bound context, no processor chain, no automatic timestamp/level injection |

**Installation:**
```bash
uv add watchfiles structlog
```

## Architecture Patterns

### Recommended Project Structure
```
src/event_dedup/
├── worker/
│   ├── __init__.py
│   ├── __main__.py        # Entry point: python -m event_dedup.worker
│   ├── watcher.py          # File watcher using watchfiles awatch
│   ├── orchestrator.py     # Bridges ingestion -> matching -> persistence
│   └── persistence.py      # Writes canonical events + sources to DB
├── logging_config.py        # structlog + stdlib unified configuration
└── ...existing modules...
docker/
├── Dockerfile.worker        # Pipeline worker (multi-stage with uv)
├── Dockerfile.api           # FastAPI skeleton (multi-stage with uv)
├── Dockerfile.frontend      # Nginx placeholder
└── entrypoint.sh            # Alembic migration + app start
docker-compose.yml
.dockerignore
```

### Pattern 1: File Watcher with Filtered awatch

**What:** Watch a directory for new JSON files using `awatch` with a custom filter that only yields `Change.added` events for `.json` files.
**When to use:** Always -- this is the primary entry point for the pipeline worker.

```python
# Source: watchfiles official docs (https://watchfiles.helpmanual.io/api/watch/)
import asyncio
from pathlib import Path
from watchfiles import awatch, Change

def json_added_filter(change: Change, path: str) -> bool:
    """Only react to newly added .json files."""
    return change == Change.added and path.endswith(".json")

async def watch_directory(data_dir: Path, process_callback):
    """Watch data_dir for new JSON files, call process_callback for each."""
    async for changes in awatch(data_dir, watch_filter=json_added_filter):
        for change_type, file_path in changes:
            await process_callback(Path(file_path))
```

### Pattern 2: Pipeline Orchestrator (Ingest -> Match -> Persist)

**What:** After a file is ingested, load ALL source events from DB, run the full matching pipeline, and write canonical events. Uses a "clear-and-replace" strategy for canonical events.
**When to use:** On every new file arrival.

**Why clear-and-replace instead of incremental:**
- The dataset is small (~2000 events/week, ~765 per sample batch)
- `run_full_pipeline` is a pure function operating on all events -- it has no concept of "only match new events"
- Incremental matching (match new events against existing canonicals) would require complex diff logic: which canonicals to keep, which to split, which to merge
- Clear-and-replace gives correct results every time, is simple to implement, and is fast enough at this scale
- A full run of 765 events completes in seconds (blocking + scoring is O(n) due to blocking keys)

```python
# Orchestrator pattern
import structlog
from pathlib import Path
from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.matching.config import MatchingConfig, load_matching_config
from event_dedup.matching.pipeline import run_full_pipeline
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.canonical_event_source import CanonicalEventSource
from event_dedup.models.source_event import SourceEvent

logger = structlog.get_logger()

async def process_new_file(
    file_path: Path,
    file_processor: FileProcessor,
    session_factory: async_sessionmaker,
    matching_config: MatchingConfig,
) -> dict:
    """Full pipeline: ingest file -> load all events -> match -> persist canonicals."""
    log = logger.bind(file=file_path.name)

    # Step 1: Ingest the file (existing code, handles idempotency)
    result = await file_processor.process_file(file_path)
    if result.status != "completed":
        log.info("file_skipped", status=result.status, reason=result.reason)
        return {"status": result.status, "reason": result.reason}

    log.info("file_ingested", event_count=result.event_count)

    # Step 2: Load ALL source events from DB
    async with session_factory() as session:
        events = await _load_all_events_as_dicts(session)

    log.info("events_loaded", total_events=len(events))

    # Step 3: Run matching pipeline (pure function)
    pipeline_result = run_full_pipeline(events, matching_config)

    log.info(
        "matching_complete",
        matches=pipeline_result.match_result.match_count,
        canonical_count=pipeline_result.canonical_count,
        flagged_count=pipeline_result.flagged_count,
    )

    # Step 4: Persist canonical events (clear-and-replace in single transaction)
    async with session_factory() as session, session.begin():
        await _replace_canonical_events(session, pipeline_result.canonical_events, events)

    log.info("pipeline_complete", canonical_events_written=pipeline_result.canonical_count)

    return {
        "status": "completed",
        "events_ingested": result.event_count,
        "total_events": len(events),
        "matches_found": pipeline_result.match_result.match_count,
        "canonicals_created": pipeline_result.canonical_count,
        "flagged_for_review": pipeline_result.flagged_count,
    }
```

### Pattern 3: Loading Source Events as Dicts for the Pipeline

**What:** Convert SQLAlchemy SourceEvent objects to the dict format that `run_full_pipeline` expects.
**When to use:** Before every pipeline run.

This pattern already exists in `evaluation/harness.py::run_multisignal_evaluation` (lines 282-324). Extract it as a reusable function:

```python
# Source: existing codebase pattern from evaluation/harness.py
async def _load_all_events_as_dicts(session: AsyncSession) -> list[dict]:
    """Load all source events as dicts matching the pipeline's expected format."""
    result = await session.execute(
        select(SourceEvent).options(selectinload(SourceEvent.dates))
    )
    source_events = result.scalars().all()

    return [
        {
            "id": evt.id,
            "title": evt.title,
            "title_normalized": evt.title_normalized,
            "short_description": evt.short_description,
            "short_description_normalized": evt.short_description_normalized,
            "description": evt.description,
            "highlights": evt.highlights,
            "location_name": evt.location_name,
            "location_city": evt.location_city,
            "location_district": evt.location_district,
            "location_street": evt.location_street,
            "location_zipcode": evt.location_zipcode,
            "geo_latitude": evt.geo_latitude,
            "geo_longitude": evt.geo_longitude,
            "geo_confidence": evt.geo_confidence,
            "source_code": evt.source_code,
            "source_type": evt.source_type,
            "blocking_keys": evt.blocking_keys,
            "categories": evt.categories,
            "is_family_event": evt.is_family_event,
            "is_child_focused": evt.is_child_focused,
            "admission_free": evt.admission_free,
            "dates": [
                {
                    "date": str(d.date),
                    "start_time": str(d.start_time) if d.start_time else None,
                    "end_time": str(d.end_time) if d.end_time else None,
                    "end_date": str(d.end_date) if d.end_date else None,
                }
                for d in evt.dates
            ],
        }
        for evt in source_events
    ]
```

### Pattern 4: Canonical Event Persistence (Clear-and-Replace)

**What:** Delete all existing canonical events and their source links, then insert fresh ones from the pipeline result.
**When to use:** On every pipeline run.

```python
async def _replace_canonical_events(
    session: AsyncSession,
    canonical_dicts: list[dict],
    all_event_dicts: list[dict],
) -> None:
    """Replace all canonical events in a single transaction.

    Deletes existing canonicals (cascade deletes sources),
    then inserts new ones with source links.
    """
    # Delete all existing canonical events (CASCADE deletes canonical_event_sources)
    await session.execute(delete(CanonicalEvent))

    events_by_id = {e["id"]: e for e in all_event_dicts}

    for canonical_dict in canonical_dicts:
        # Create CanonicalEvent ORM object from synthesized dict
        canonical = CanonicalEvent(
            title=canonical_dict["title"],
            short_description=canonical_dict.get("short_description"),
            description=canonical_dict.get("description"),
            highlights=canonical_dict.get("highlights"),
            location_name=canonical_dict.get("location_name"),
            location_city=canonical_dict.get("location_city"),
            location_district=canonical_dict.get("location_district"),
            location_street=canonical_dict.get("location_street"),
            location_zipcode=canonical_dict.get("location_zipcode"),
            geo_latitude=canonical_dict.get("geo_latitude"),
            geo_longitude=canonical_dict.get("geo_longitude"),
            geo_confidence=canonical_dict.get("geo_confidence"),
            dates=canonical_dict.get("dates"),
            categories=canonical_dict.get("categories"),
            is_family_event=canonical_dict.get("is_family_event"),
            is_child_focused=canonical_dict.get("is_child_focused"),
            admission_free=canonical_dict.get("admission_free"),
            field_provenance=canonical_dict.get("field_provenance"),
            source_count=canonical_dict.get("source_count", 1),
            match_confidence=canonical_dict.get("match_confidence"),
            needs_review=canonical_dict.get("needs_review", False),
        )
        session.add(canonical)
        await session.flush()  # Get auto-generated ID

        # Create source links using field_provenance to find source event IDs
        # The canonical_dict has source info embedded -- extract source IDs
        # from the provenance and from the original cluster membership
        source_ids = _extract_source_ids(canonical_dict)
        for source_id in source_ids:
            if source_id in events_by_id:  # Validate FK exists
                link = CanonicalEventSource(
                    canonical_event_id=canonical.id,
                    source_event_id=source_id,
                )
                session.add(link)


def _extract_source_ids(canonical_dict: dict) -> set[str]:
    """Extract source event IDs from a canonical dict's provenance."""
    source_ids = set()
    provenance = canonical_dict.get("field_provenance", {})
    for field, source_id in provenance.items():
        if source_id and source_id not in ("union_all_sources", "unknown"):
            source_ids.add(source_id)
    return source_ids
```

**Important note about source ID extraction:** The synthesizer's `field_provenance` only records which source contributed each *field* -- it does not record all source event IDs in the cluster. The pipeline orchestrator must track cluster membership separately. The `run_full_pipeline` result has `cluster_result.clusters` (and `flagged_clusters`) which are `set[str]` of event IDs. The canonical events list is parallel to the clusters list. Use this for source links:

```python
# Better approach: correlate canonical_events with clusters
all_clusters = list(pipeline_result.cluster_result.clusters) + list(
    pipeline_result.cluster_result.flagged_clusters
)
for canonical_dict, cluster in zip(pipeline_result.canonical_events, all_clusters):
    # cluster is a set[str] of source event IDs
    for source_id in cluster:
        link = CanonicalEventSource(
            canonical_event_id=canonical.id,
            source_event_id=source_id,
        )
        session.add(link)
```

### Pattern 5: structlog Configuration for Unified JSON Logging

**What:** Configure structlog so BOTH `structlog.get_logger()` calls AND existing `logging.getLogger(__name__)` calls produce JSON output.
**When to use:** At worker startup.

```python
# Source: structlog 25.5.0 docs (https://www.structlog.org/en/stable/standard-library.html)
import logging
import sys
import structlog

def configure_logging(json_output: bool = True, log_level: str = "INFO") -> None:
    """Configure unified logging: both structlog and stdlib produce JSON."""
    shared_processors = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        renderer = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # Configure structlog
    structlog.configure(
        processors=shared_processors + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib logging to use structlog's ProcessorFormatter
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root_logger = logging.getLogger()
    root_logger.handlers.clear()
    root_logger.addHandler(handler)
    root_logger.setLevel(getattr(logging, log_level.upper()))
```

### Anti-Patterns to Avoid

- **Incremental matching for small datasets:** Do not try to match only new events against existing canonicals at this scale. The complexity of tracking which canonicals need updating, handling cluster merges when a new event bridges two previously separate clusters, and managing version conflicts far outweighs the cost of re-running the full pipeline on ~2000 events.

- **Separate logging configurations:** Do not configure structlog and stdlib logging independently. Use ProcessorFormatter to capture both into one stream, or you get inconsistent log formats.

- **Moving processed files:** Do not move files after processing. The FileProcessor already handles idempotency via file hash checking. Moving files would break the watch-and-process model and complicate debugging. Leave processed files in place; the hash check skips them on restart.

- **Running Alembic inside the Python app:** Do not call Alembic programmatically from within the worker process. Use the entrypoint script pattern instead -- this keeps migration concerns separate from application logic and makes debugging migration failures easier.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| File system watching | Polling loop with `os.listdir` | watchfiles `awatch` | OS-level events are instant; polling wastes CPU and misses rapid changes |
| JSON log formatting | Custom `logging.Formatter` | structlog `ProcessorFormatter` | Handles escaping, timestamp formatting, exception serialization, context binding |
| Docker dependency install | `pip install` in Dockerfile | `uv sync --locked` with cache mounts | 10-100x faster; respects lockfile exactly; layer caching works properly |
| DB migration on startup | Manual SQL or Python migration scripts | Alembic `upgrade head` in entrypoint | Alembic handles migration ordering, idempotency, and rollback |
| Process health checking | Custom HTTP health endpoint in worker | Docker `HEALTHCHECK` with process check | Worker has no HTTP server; checking if the process is alive is sufficient |

**Key insight:** This phase is primarily an integration exercise, not a library-building exercise. Every component either exists (FileProcessor, matching pipeline, synthesizer) or has a well-established library solution. The only truly new code is the orchestrator that ties them together and the persistence layer for canonical events.

## Common Pitfalls

### Pitfall 1: Matching Only New Events Against Existing Canonicals
**What goes wrong:** Developer tries to avoid re-running the full pipeline by matching only newly ingested events against existing canonical events. This misses transitive matches: event A (old file) and event C (new file) might not match directly, but both match event B (another old file), so they should be in the same cluster.
**Why it happens:** Premature optimization for a dataset that's small enough for full re-matching.
**How to avoid:** Use the clear-and-replace strategy. Load ALL events, run `run_full_pipeline`, replace all canonicals. At ~2000 events/week with blocking (>95% pair reduction), this runs in seconds.
**Warning signs:** Code that tries to "diff" canonical events or "merge" new clusters with old ones.

### Pitfall 2: Source Event ID Extraction from Canonical Dicts
**What goes wrong:** Developer uses `field_provenance` to determine which source events belong to a canonical event. The provenance only tracks which source contributed each *field value* -- not all cluster members. A 5-source cluster might only have 3-4 unique provenance entries.
**Why it happens:** The synthesizer dict doesn't include an explicit `source_event_ids` list.
**How to avoid:** Use `pipeline_result.cluster_result.clusters` and `pipeline_result.cluster_result.flagged_clusters` to get the actual cluster membership. The canonical events list is generated in the same order as clusters + flagged_clusters.
**Warning signs:** Canonical events with fewer source links than expected.

### Pitfall 3: Race Condition on Rapid File Drops
**What goes wrong:** Multiple JSON files dropped simultaneously trigger parallel processing, leading to concurrent DB writes and inconsistent canonical event state.
**Why it happens:** `awatch` yields a *set* of changes -- multiple files can arrive in one batch.
**How to avoid:** Process all files in a batch sequentially within a single `awatch` yield. After all ingestions, run matching ONCE for the whole batch. This is both correct and more efficient than per-file matching.
**Warning signs:** Database deadlocks or constraint violations during canonical event writes.

### Pitfall 4: Alembic Migration Timeout in Docker
**What goes wrong:** The Alembic migration command in the entrypoint runs before PostgreSQL is ready, fails, and the container exits.
**Why it happens:** Docker Compose `depends_on` (without health check) only waits for container start, not service readiness.
**How to avoid:** Use `depends_on: db: condition: service_healthy` with a `pg_isready` health check on the PostgreSQL container. Add a retry loop in the entrypoint script as a safety net.
**Warning signs:** Container restart loops with "connection refused" errors.

### Pitfall 5: Existing stdlib Logging Calls Go Unformatted
**What goes wrong:** The existing codebase uses `logging.getLogger(__name__)` throughout (e.g., `file_processor.py`). If structlog is configured only for its own loggers, these existing calls produce plain-text output while structlog calls produce JSON.
**Why it happens:** Two separate logging systems outputting to the same stream.
**How to avoid:** Use structlog's `ProcessorFormatter` on the root logging handler. This intercepts ALL logging output (both structlog and stdlib) and formats it uniformly. The `foreign_pre_chain` parameter processes stdlib log records through the same chain as structlog events.
**Warning signs:** Mixed log formats (some JSON, some plain text) in container output.

## Code Examples

### Worker Entry Point (`__main__.py`)

```python
# src/event_dedup/worker/__main__.py
import asyncio
import signal
import structlog
from pathlib import Path

from event_dedup.config.settings import get_settings
from event_dedup.db.session import get_session_factory
from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.matching.config import load_matching_config
from event_dedup.worker.watcher import watch_and_process

logger = structlog.get_logger()

async def main():
    settings = get_settings()
    session_factory = get_session_factory()
    matching_config = load_matching_config(Path("config/matching.yaml"))

    file_processor = FileProcessor(
        session_factory=session_factory,
        dead_letter_dir=settings.dead_letter_dir,
    )

    data_dir = settings.event_data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    logger.info("worker_starting", watch_dir=str(data_dir))

    # Process any existing unprocessed files on startup
    await process_existing_files(data_dir, file_processor, session_factory, matching_config)

    # Then watch for new files
    await watch_and_process(data_dir, file_processor, session_factory, matching_config)

if __name__ == "__main__":
    # Configure logging first
    from event_dedup.logging_config import configure_logging
    configure_logging()
    asyncio.run(main())
```

### Entrypoint Script for Docker

```bash
#!/bin/bash
set -e

echo "Running database migrations..."
cd /app
alembic -c config/alembic.ini upgrade head

echo "Starting worker..."
exec python -m event_dedup.worker "$@"
```

**Key:** The `exec` replaces the shell process with the Python process, so Docker signals (SIGTERM) reach the worker directly.

### Multi-Stage Dockerfile for Worker

```dockerfile
# docker/Dockerfile.worker
FROM ghcr.io/astral-sh/uv:python3.12-bookworm-slim AS builder

ENV UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    UV_NO_DEV=1 \
    UV_PYTHON_DOWNLOADS=0

WORKDIR /app

# Install dependencies first (cached unless lock changes)
RUN --mount=type=cache,target=/root/.cache/uv \
    --mount=type=bind,source=uv.lock,target=uv.lock \
    --mount=type=bind,source=pyproject.toml,target=pyproject.toml \
    uv sync --locked --no-install-project --no-editable

# Copy source and install project
COPY . /app
RUN --mount=type=cache,target=/root/.cache/uv \
    uv sync --locked --no-editable

# --- Runtime stage ---
FROM python:3.12-slim-bookworm

RUN groupadd --system --gid 999 app \
    && useradd --system --gid 999 --uid 999 --create-home app

COPY --from=builder --chown=app:app /app /app

ENV PATH="/app/.venv/bin:$PATH"

# Alembic needs config and migration files
# (already copied with /app)

WORKDIR /app

# Health check: verify the worker process is running
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD pgrep -f "python -m event_dedup.worker" || exit 1

COPY docker/entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

USER app

ENTRYPOINT ["/entrypoint.sh"]
```

### docker-compose.yml

```yaml
services:
  db:
    image: postgres:16-alpine
    environment:
      POSTGRES_DB: event_dedup
      POSTGRES_USER: postgres
      POSTGRES_PASSWORD: postgres
    volumes:
      - pgdata:/var/lib/postgresql/data
    ports:
      - "5432:5432"
    healthcheck:
      test: ["CMD-SHELL", "pg_isready -U postgres -d event_dedup"]
      interval: 5s
      timeout: 5s
      retries: 5

  worker:
    build:
      context: .
      dockerfile: docker/Dockerfile.worker
    environment:
      EVENT_DEDUP_DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/event_dedup
      EVENT_DEDUP_DATABASE_URL_SYNC: postgresql+psycopg2://postgres:postgres@db:5432/event_dedup
      EVENT_DEDUP_EVENT_DATA_DIR: /data/events
      EVENT_DEDUP_DEAD_LETTER_DIR: /data/dead_letters
      ALEMBIC_DATABASE_URL: postgresql+psycopg2://postgres:postgres@db:5432/event_dedup
    volumes:
      - ./eventdata:/data/events
      - ./dead_letters:/data/dead_letters
    depends_on:
      db:
        condition: service_healthy

  api:
    build:
      context: .
      dockerfile: docker/Dockerfile.api
    environment:
      EVENT_DEDUP_DATABASE_URL: postgresql+asyncpg://postgres:postgres@db:5432/event_dedup
    ports:
      - "8000:8000"
    depends_on:
      db:
        condition: service_healthy

  frontend:
    image: nginx:alpine
    ports:
      - "3000:80"
    volumes:
      - ./docker/nginx-placeholder.html:/usr/share/nginx/html/index.html:ro

volumes:
  pgdata:
```

### .dockerignore

```
.git
.venv
__pycache__
*.pyc
.planning
.agents
.claude
tests
*.egg-info
.ruff_cache
.pytest_cache
.mypy_cache
dead_letters
eventdata
```

### Alembic Environment Variable Override

The existing `config/alembic/env.py` already supports `ALEMBIC_DATABASE_URL` environment variable override (lines 42-45). This is exactly what the Docker entrypoint needs -- no changes required to Alembic configuration.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| watchdog (callback-based) | watchfiles (async-native, Rust) | 2022+ | Native async support; no threading bridge needed |
| python-json-logger | structlog ProcessorFormatter | Stable since structlog 21+ | Unified stdlib + structlog formatting; bound context |
| `pip install` in Docker | `uv sync --locked` with cache mounts | 2024+ | 10-100x faster Docker builds; exact lockfile resolution |
| `COPY --from=ghcr.io/astral-sh/uv:latest` | Pin uv version in Dockerfile | 2025+ | Reproducible builds; avoid surprise uv updates |
| `depends_on` (no condition) | `depends_on: condition: service_healthy` | Docker Compose v2+ | Actual service readiness, not just container start |

**Deprecated/outdated:**
- `watchgod`: Predecessor to `watchfiles`, same author, replaced entirely
- Docker Compose v3 `depends_on` without conditions: v3 removed conditions; Docker Compose v2 (Go rewrite) restored them

## Open Questions

1. **Startup processing of existing files**
   - What we know: When the worker starts, there may be unprocessed JSON files already in the watched directory (from before the worker was running).
   - What's unclear: Should the worker scan for and process these on startup, or only watch for new arrivals?
   - Recommendation: Process existing files on startup. Scan the directory, filter for `.json` files, pass each through the pipeline. The idempotency check (file hash) prevents reprocessing. This makes the worker resilient to restarts.

2. **Match decisions persistence**
   - What we know: The `match_decisions` table exists (Phase 2 model). The pipeline produces `MatchDecisionRecord` objects with all pairwise scores.
   - What's unclear: Should match decisions be persisted during pipeline runs? They are useful for Phase 6 (manual review) but add write volume.
   - Recommendation: Persist match decisions as part of the clear-and-replace transaction. Delete old match decisions, insert new ones. This data is needed for the review queue (Phase 6) and for debugging matching behavior. The volume is manageable (~5000 pairs for 765 events after blocking).

3. **Graceful shutdown**
   - What we know: Docker sends SIGTERM before SIGKILL. The worker should stop watching and finish any in-progress file.
   - What's unclear: Best pattern for signal handling with `awatch`.
   - Recommendation: Use `asyncio.Event` as `stop_event` parameter to `awatch`. Set it on SIGTERM. The current file processing will complete, then the watch loop exits cleanly.

## Sources

### Primary (HIGH confidence)
- watchfiles official docs (https://watchfiles.helpmanual.io/) - awatch API, filter system, Change enum
- structlog 25.5.0 docs (https://www.structlog.org/en/stable/standard-library.html) - ProcessorFormatter, stdlib integration
- uv Docker integration guide (https://docs.astral.sh/uv/guides/integration/docker/) - multi-stage Dockerfile patterns
- astral-sh/uv-docker-example multistage.Dockerfile (https://github.com/astral-sh/uv-docker-example/blob/main/multistage.Dockerfile) - complete working example
- Existing codebase: `evaluation/harness.py` lines 282-324 - proven pattern for loading SourceEvents as dicts

### Secondary (MEDIUM confidence)
- hynek.me Docker uv article (https://hynek.me/articles/docker-uv/) - production patterns, non-root user
- Docker Compose health check docs (https://docs.docker.com/compose/how-tos/startup-order/) - depends_on conditions
- Existing codebase: `config/alembic/env.py` - ALEMBIC_DATABASE_URL override already implemented

### Tertiary (LOW confidence)
- Alembic entrypoint script pattern - assembled from multiple blog posts; verify entrypoint.sh works with the specific project layout

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - watchfiles and structlog are well-documented, actively maintained, and verified against official docs
- Architecture: HIGH - the clear-and-replace pattern is simple and the existing codebase already demonstrates the event-loading pattern in harness.py
- Docker patterns: HIGH - verified against official uv Docker examples and Astral documentation
- Pitfalls: HIGH - derived from direct analysis of the codebase's data flow (field_provenance gaps, concurrent writes)
- Alembic entrypoint: MEDIUM - common pattern but not verified against this specific project layout

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable domain, 30-day validity)
