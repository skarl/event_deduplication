# Event Deduplication Pipeline

Automated deduplication pipeline for regional event data — matches, clusters, and merges duplicate event listings from multiple sources into canonical events.

## Features

- **Multi-signal matching** — scores event pairs on date overlap, geographic proximity, title similarity, and description similarity
- **Configurable thresholds** — auto-merge, auto-reject, or flag ambiguous pairs for review
- **AI-assisted resolution** — optional Gemini 2.5 Flash integration resolves ambiguous pairs with caching and cost tracking
- **Category-aware weights** — scoring weights adjust automatically for event categories like carnival or political assemblies
- **Graph-based clustering** — groups related matches into clusters and synthesizes canonical events
- **File watcher** — continuously ingests JSON event files dropped into a watched directory
- **Review UI** — browse, search, filter, split, merge, and export canonical events through a React frontend
- **Dead-letter handling** — invalid or failed files are archived with error context for debugging

## Architecture

```
  eventdata/            docker compose up
  (JSON files)     ┌─────────────────────────────────────┐
       │           │                                     │
       ▼           │   ┌──────────┐    ┌──────────────┐  │
  ┌─────────┐      │   │ worker   │───▶│ PostgreSQL   │  │
  │ watcher │──────┼──▶│ pipeline │◀──▶│ 16-alpine    │  │
  └─────────┘      │   └──────────┘    │ :5432        │  │
                   │        │          └──────┬───────┘  │
                   │   ambiguous pairs        │          │
                   │        ▼                 │          │
                   │   ┌──────────┐           │          │
                   │   │ Gemini   │           │          │
                   │   │ 2.5 Flash│           │          │
                   │   └──────────┘           │          │
                   │                          │          │
                   │   ┌──────────┐           │          │
                   │   │ FastAPI  │◀──────────┘          │
                   │   │ :8000    │                      │
                   │   └────┬─────┘                      │
                   │        │                            │
                   │   ┌────▼─────┐                      │
                   │   │ React    │                      │
                   │   │ :3000    │                      │
                   │   └──────────┘                      │
                   └─────────────────────────────────────┘
```

**Services:**

| Service    | Image / Build          | Port  | Purpose                                  |
|------------|------------------------|-------|------------------------------------------|
| `db`       | `postgres:16-alpine`   | 5432  | Persistent storage                       |
| `worker`   | `docker/Dockerfile.worker` | —  | File watcher + matching pipeline         |
| `api`      | `docker/Dockerfile.api`    | 8000 | REST API (FastAPI + Uvicorn)             |
| `frontend` | `docker/Dockerfile.frontend` | 3000 | React UI served by Nginx               |

## Quick Start

```bash
# Start all four services
docker compose up -d

# Optionally enable AI-assisted matching
GEMINI_API_KEY=your-key docker compose up -d

# Drop event JSON files into eventdata/ — the worker picks them up automatically
cp my-events.json eventdata/

# Open the UI
open http://localhost:3000
```

The worker watches `eventdata/` for new JSON files, runs the matching pipeline, and writes results to PostgreSQL. The frontend at `http://localhost:3000` lets you browse, review, and export the deduplicated events.

## How It Works

The pipeline processes each new file through these stages:

1. **Ingestion** — validates and persists source events from JSON files (invalid files go to `dead_letters/`)
2. **Blocking** — generates candidate pairs using blocking keys (shared date + city) to avoid O(n^2) comparisons
3. **Scoring** — computes four similarity signals for each candidate pair
4. **Decision** — combines weighted signals into a single score and applies thresholds
5. **AI resolution** (optional) — sends ambiguous pairs to Gemini for a second opinion
6. **Clustering** — builds a match graph and extracts connected components
7. **Synthesis** — creates or updates canonical events by merging fields from cluster members

## Matching Algorithm

Each candidate pair is scored on four signals, then the weighted scores are combined into a single decision:

| Signal        | Weight | Method                                                                 |
|---------------|--------|------------------------------------------------------------------------|
| **Date**      | 0.30   | Jaccard overlap of date sets, scaled by start-time proximity           |
| **Geo**       | 0.25   | Haversine distance (linear decay up to 10 km), venue name check        |
| **Title**     | 0.30   | RapidFuzz `token_sort_ratio` (70%) blended with `token_set_ratio` (30%) |
| **Description** | 0.15 | RapidFuzz `token_sort_ratio`                                           |

**Decision thresholds:**

| Combined score | Decision      |
|----------------|---------------|
| >= 0.75        | **match** (auto-merge)  |
| 0.35 – 0.75   | **ambiguous** (AI or manual review) |
| < 0.35         | **no_match** (auto-reject) |

**Title veto:** If the title score is below 0.45, the pair is forced to "ambiguous" even when the combined score would otherwise trigger auto-merge. This prevents merging events that happen at the same place and time but are clearly different (e.g., two talks in the same venue).

**Category-aware overrides:** When both events share a category, alternative weights apply:

- *Fasnacht (carnival):* geo raised to 0.30, title lowered to 0.25 — carnival event titles vary wildly between sources
- *Versammlung (assembly):* title raised to 0.40, geo lowered to 0.20 — political events have very consistent titles

**Cross-source blending:** When an *artikel* (newspaper article) is compared to a *terminliste* (calendar listing), the title scorer shifts weight toward `token_set_ratio` (60%) to better handle asymmetric length differences.

## AI-Assisted Matching

When a Gemini API key is configured, ambiguous pairs (combined score 0.65–0.79) are sent to **Gemini 2.5 Flash** for resolution.

- **Structured output** — the model returns `{decision, confidence, reasoning}` via a constrained schema
- **Confidence gate** — AI decisions below 0.6 confidence are discarded (pair stays ambiguous)
- **Caching** — content-hash-based cache prevents re-querying identical pairs
- **Cost tracking** — token usage and estimated cost are logged per batch to `ai_usage_log`
- **Concurrency** — up to 5 concurrent requests (configurable)

The AI prompt is tuned for German regional events with guidance on compound words, regional dialects, and source-type differences.

Enable via environment variable:

```bash
GEMINI_API_KEY=your-key docker compose up -d
```

Or configure at runtime through the Config page in the UI.

## Frontend

The React frontend at `http://localhost:3000` provides:

- **Events** — searchable, filterable list of canonical events with sorting by title, city, date, source count, confidence, or review status
- **Event detail** — source events, match decisions with scores, and field provenance
- **Review queue** — events flagged for manual review, with split/merge/dismiss actions
- **Dashboard** — file processing stats, match distribution, canonical event metrics, and daily trends
- **Config** — live-edit matching weights, thresholds, and AI parameters (persisted to database)
- **Export** — download canonical events as JSON (or ZIP for large sets)

## Input Format

Drop JSON files into `eventdata/`. The worker picks them up automatically.

```json
{
  "events": [
    {
      "id": "src-001",
      "title": "Fasnachtsumzug Offenburg",
      "short_description": "Großer Umzug durch die Innenstadt",
      "description": "Der traditionelle Fasnachtsumzug...",
      "event_dates": [
        {
          "date": "2026-02-14",
          "start_time": "14:00:00",
          "end_time": "17:00:00"
        }
      ],
      "location": {
        "name": "Innenstadt",
        "city": "Offenburg",
        "street": "Hauptstraße",
        "geo": {
          "latitude": 48.4721,
          "longitude": 7.9406,
          "confidence": 0.95
        }
      },
      "source_type": "artikel",
      "categories": ["fasnacht"],
      "is_family_event": true,
      "admission_free": true
    }
  ],
  "metadata": {
    "processedAt": "2026-02-14T10:00:00Z",
    "sourceKey": "newspaper-xyz"
  }
}
```

**Required fields:** `id`, `title`, `event_dates` (with at least one `date`), `source_type`

All other fields are optional and improve matching quality when present.

## Configuration

Matching parameters are defined in `config/matching.yaml` and can be overridden at runtime through the API or the Config page in the UI.

```yaml
scoring:
  date: 0.30
  geo: 0.25
  title: 0.30
  description: 0.15

thresholds:
  high: 0.75
  low: 0.35
  title_veto: 0.45
```

Runtime changes are persisted to the database and take effect on the next pipeline run. See the full [`config/matching.yaml`](config/matching.yaml) for all available parameters.

## API Reference

| Method   | Path                                  | Description                                    |
|----------|---------------------------------------|------------------------------------------------|
| `GET`    | `/health`                             | Health check                                   |
| `GET`    | `/api/canonical-events`               | List canonical events (search, filter, sort, paginate) |
| `GET`    | `/api/canonical-events/{id}`          | Get canonical event detail with sources and match decisions |
| `GET`    | `/api/canonical-events/categories`    | List distinct categories                       |
| `GET`    | `/api/canonical-events/cities`        | List distinct cities                           |
| `GET`    | `/api/review/queue`                   | Review queue sorted by uncertainty             |
| `POST`   | `/api/review/split`                   | Detach a source event from its canonical       |
| `POST`   | `/api/review/merge`                   | Merge two canonical events                     |
| `POST`   | `/api/review/queue/{id}/dismiss`      | Dismiss event from review queue                |
| `GET`    | `/api/audit-log`                      | Audit log of review actions                    |
| `GET`    | `/api/dashboard/stats`                | Processing and matching statistics             |
| `GET`    | `/api/dashboard/processing-history`   | Daily processing time series                   |
| `GET`    | `/api/config`                         | Current matching configuration                 |
| `PATCH`  | `/api/config`                         | Update matching parameters (deep merge)        |
| `POST`   | `/api/export`                         | Export canonical events as JSON or ZIP          |

## CLI

```bash
# Export canonical events to JSON files
python -m event_dedup.cli export --output-dir ./export

# Export only recently created events
python -m event_dedup.cli export \
  --created-after 2026-02-01T00:00 \
  --output-dir ./recent
```

## Development Setup

**Prerequisites:** Python 3.12+, Node 22+, PostgreSQL 16, [uv](https://docs.astral.sh/uv/)

```bash
# Install Python dependencies
uv sync

# Install dev dependencies
uv sync --group dev

# Run database migrations
alembic upgrade head

# Start the worker
python -m event_dedup.worker

# Start the API server
uvicorn event_dedup.api.app:app --host 0.0.0.0 --port 8000

# Start the frontend dev server (separate terminal)
cd frontend && npm ci && npm run dev
```

**Running tests:**

```bash
# All tests
pytest

# With coverage
pytest --cov=src/event_dedup tests/

# Specific test file
pytest tests/test_scorers.py
```

**Linting:**

```bash
ruff check src/ tests/
ruff format src/ tests/
```

## Environment Variables

All variables use the `EVENT_DEDUP_` prefix.

| Variable                | Default                          | Description                        |
|-------------------------|----------------------------------|------------------------------------|
| `EVENT_DEDUP_DATABASE_URL`      | `postgresql+asyncpg://postgres:postgres@localhost:5432/event_dedup` | Async database URL |
| `EVENT_DEDUP_DATABASE_URL_SYNC` | `postgresql+psycopg2://postgres:postgres@localhost:5432/event_dedup` | Sync database URL (Alembic) |
| `EVENT_DEDUP_EVENT_DATA_DIR`    | `./eventdata`                    | Directory watched for JSON files   |
| `EVENT_DEDUP_DEAD_LETTER_DIR`   | `./dead_letters`                 | Archive for failed files           |
| `EVENT_DEDUP_MATCHING_CONFIG_PATH` | `config/matching.yaml`        | Path to matching config            |
| `EVENT_DEDUP_GEMINI_API_KEY`    | *(empty)*                        | Gemini API key for AI matching     |
| `EVENT_DEDUP_ENCRYPTION_KEY`    | *(empty)*                        | Fernet key for API key encryption  |
| `EVENT_DEDUP_LOG_JSON`          | `true`                           | Enable structured JSON logging     |
| `EVENT_DEDUP_LOG_LEVEL`         | `INFO`                           | Log level (DEBUG, INFO, WARNING)   |

## Project Structure

```
event-deduplication/
├── config/
│   └── matching.yaml              # Matching parameters
├── docker/
│   ├── Dockerfile.api
│   ├── Dockerfile.worker
│   ├── Dockerfile.frontend
│   └── nginx.conf
├── eventdata/                     # Input: drop JSON files here
├── dead_letters/                  # Failed file archive
├── frontend/                      # React + Vite + Tailwind
│   └── src/
│       ├── components/
│       ├── hooks/
│       └── types/
├── src/event_dedup/
│   ├── api/                       # FastAPI routes
│   │   └── routes/
│   ├── matching/                  # Scoring pipeline
│   │   ├── pipeline.py            # Orchestrator
│   │   ├── combiner.py            # Score combination + decisions
│   │   ├── candidate_pairs.py     # Blocking keys
│   │   └── scorers/               # Date, geo, title, description
│   ├── ai_matching/               # Gemini integration
│   │   ├── resolver.py            # Ambiguous pair resolution
│   │   ├── cache.py               # Content-hash cache
│   │   └── cost_tracker.py        # Token + cost logging
│   ├── canonical/                 # Event synthesis
│   ├── clustering/                # Graph clustering
│   ├── ingestion/                 # JSON file loading
│   ├── preprocessing/             # Text normalization
│   ├── models/                    # SQLAlchemy ORM models
│   ├── review/                    # Split/merge operations
│   ├── export/                    # JSON/ZIP export
│   └── cli/                       # Command-line interface
├── tests/                         # pytest suite
├── docker-compose.yml
└── pyproject.toml
```
