# Technology Stack

**Project:** Event Deduplication Service
**Researched:** 2026-02-27
**Verification note:** WebSearch, WebFetch, and Bash were unavailable during research. Versions are based on training data (through mid-2025). All version numbers should be verified against PyPI/npm before use. Confidence levels reflect this limitation.

---

## Recommended Stack

### Language & Runtime

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Python | 3.12+ | Primary language | Best ecosystem for text processing, NLP, fuzzy matching, and AI/LLM integration. The deduplication domain is overwhelmingly Python-centric. 3.12 brings significant performance improvements (10-15% faster than 3.11). | HIGH |

**Why not Node/TypeScript:** Python's NLP and text-processing ecosystem (rapidfuzz, scikit-learn, sentence-transformers) has no equivalent in JS. The backend is compute-heavy string matching, not I/O-heavy web serving.

**Why not Go/Rust:** Overkill for 2000 events/week. Python with C-extension libraries (rapidfuzz is Cython) provides more than enough performance. Development speed matters more here.

### Backend Framework

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| FastAPI | >=0.115 | HTTP API framework | Async-native, automatic OpenAPI docs, Pydantic integration for data validation, excellent for building REST APIs consumed by frontends. Lightweight enough for an internal service. | HIGH |
| Pydantic | >=2.9 | Data validation & serialization | v2 is 5-50x faster than v1. Perfect for validating JSON event payloads, defining canonical event schemas, and serializing API responses. Used natively by FastAPI. | HIGH |
| Uvicorn | >=0.32 | ASGI server | Standard production server for FastAPI. Lightweight, fast, works well in Docker. | HIGH |

**Why not Django:** Too heavy for a focused service. Django's ORM, admin, auth, migrations system are overhead when you need a lean API. FastAPI is purpose-built for this use case.

**Why not Flask:** Flask lacks native async support, native type validation, and automatic API documentation. FastAPI is the modern successor for API-first services.

### Database & ORM

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| PostgreSQL | 15+ (existing) | Primary database | Already in place. Excellent for full-text search (tsvector), geographic queries (PostGIS), and JSON operations -- all needed for event deduplication. | HIGH |
| SQLAlchemy | >=2.0 | ORM & query builder | v2.0 has modern Python typing, async support, and the most mature PostgreSQL dialect. The "2.0 style" with mapped_column is clean and type-safe. | HIGH |
| asyncpg | >=0.30 | Async PostgreSQL driver | Fastest Python PostgreSQL driver (3-5x faster than psycopg2 for bulk operations). Native async, works with SQLAlchemy async engine. | HIGH |
| Alembic | >=1.14 | Database migrations | Standard migration tool for SQLAlchemy. Handles schema evolution cleanly. | HIGH |

**Why not psycopg2/psycopg3:** asyncpg is significantly faster for the bulk read/write patterns this service needs (loading existing events for comparison, batch-inserting canonical events). psycopg3 is a valid alternative if sync-only is preferred, but asyncpg pairs naturally with FastAPI's async nature.

**Why not raw SQL:** SQLAlchemy provides type safety, migration support, and prevents SQL injection. The ORM overhead is negligible for this workload.

### Text Matching & Deduplication (Core Domain)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| rapidfuzz | >=3.10 | Fuzzy string matching | 10-100x faster than thefuzz/fuzzywuzzy (C++ core via Cython). Provides Levenshtein, Jaro-Winkler, token_sort_ratio, token_set_ratio -- all essential for title deduplication. MIT licensed. | HIGH |
| scikit-learn | >=1.5 | TF-IDF vectorization, clustering | TfidfVectorizer + cosine_similarity for fast batch title comparison. Can pre-filter candidates before detailed fuzzy matching. Well-tested, stable. | HIGH |
| geopy | >=2.4 | Geodesic distance calculation | Calculate distance between event coordinates for geo-proximity matching. Lightweight, no heavy GIS dependency needed. | MEDIUM |

**Why rapidfuzz over thefuzz/fuzzywuzzy:** rapidfuzz is a drop-in replacement that is dramatically faster (written in C++), actively maintained, MIT licensed (thefuzz is GPL), and has superior Unicode handling -- critical for German event titles with umlauts. Performance matters when comparing each incoming event against potentially thousands of existing events.

**Why scikit-learn over dedicated NLP:** For title similarity at this scale (2000 events/week), TF-IDF + cosine similarity is the right level of sophistication. It is fast, deterministic, and well-understood. Sentence transformers (BERT-based embeddings) are overkill for the deterministic tier and should only be considered if TF-IDF proves insufficient.

**Why not dedupe library:** The `dedupe` library is designed for record linkage with active learning, which is more complex than needed. This project has well-defined matching signals (date + location + title) that map cleanly to a custom tiered pipeline. Building the matching logic explicitly gives full control over the tiers.

### AI-Assisted Matching (Ambiguous Cases)

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| litellm | >=1.50 | LLM API abstraction | Unified interface to call OpenAI, Anthropic, or local models. Switch providers without code changes. Essential for cost control -- can route to cheaper models for simple comparisons. | MEDIUM |
| openai (SDK) | >=1.55 | Direct OpenAI API client | If using OpenAI models only, the official SDK is simpler than litellm. Use structured outputs (response_format) for reliable JSON responses from the LLM. | MEDIUM |

**Recommendation:** Start with the `openai` SDK directly targeting `gpt-4o-mini` for ambiguous case resolution. It is cheap (~$0.15/1M input tokens), fast, and excellent at semantic comparison tasks. Only add litellm if you need multi-provider support later.

**Prompt pattern for deduplication:** Send the LLM two event summaries and ask "Are these the same real-world event? Respond with JSON: {same_event: boolean, confidence: float, reasoning: string}". Use structured outputs to enforce the schema.

**Cost estimate:** At 2000 events/week with ~10-15% ambiguous (200-300 LLM calls), using gpt-4o-mini at ~500 tokens/call: roughly $0.02-0.05/week. Well within budget.

**Why not local models:** For 200-300 calls/week, API costs are trivial (<$3/month). Running a local model adds Docker complexity, GPU requirements, and maintenance burden that is not justified at this scale.

**Why not sentence-transformers/embeddings:** Embedding similarity is good for candidate retrieval but poor at semantic event matching ("Primel-Aktion" vs "Primeln am Marktplatz" requires understanding, not vector distance). LLMs handle the nuanced cases that embeddings miss. Use TF-IDF for the fast tier and LLMs for the smart tier.

### File Watching & Background Processing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| watchfiles | >=1.0 | Directory file watcher | Rust-based (fast, reliable), async-native, works well on Linux/macOS/Docker. Detects new JSON files dropped into the watch directory. | HIGH |
| asyncio | stdlib | Async orchestration | Python's built-in async framework. No need for Celery or external task queues at this scale. | HIGH |

**Why not watchdog:** watchfiles is newer, faster (Rust core), has better async support, and simpler API. watchdog is the older alternative but has known issues with Docker volume mounts.

**Why not Celery/RQ/Dramatiq:** 2000 events/week does not justify a message queue. An async file watcher + in-process pipeline is simpler, has fewer moving parts, and is easier to debug. If scale grows 100x, revisit.

### Frontend

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| React | 19 | UI framework | Dominant ecosystem, excellent component libraries, strong TypeScript support. For an internal tool with table views, search, and drill-down, React's ecosystem (TanStack Table, etc.) is unmatched. | HIGH |
| TypeScript | >=5.6 | Type safety | Non-negotiable for any frontend in 2025+. Catches bugs at compile time, improves DX with autocompletion. | HIGH |
| Vite | >=6.0 | Build tool & dev server | Fast HMR, simple config, standard for React projects. Replaces webpack/CRA entirely. | HIGH |
| TanStack Table | >=8.20 | Data table component | Headless, highly customizable table library. Perfect for the event browsing/searching UI. Handles sorting, filtering, pagination out of the box. | HIGH |
| TanStack Query | >=5.62 | Server state management | Handles API data fetching, caching, and synchronization. Eliminates manual loading/error state management. Essential for the search and review UI. | HIGH |
| Tailwind CSS | >=4.0 | Styling | Utility-first CSS. Fast to build internal tools with. No design system needed for an internal tool -- Tailwind's defaults are good enough. | HIGH |

**Why React over Vue/Svelte:** For an internal data-heavy tool, React's ecosystem advantage is decisive. TanStack Table, TanStack Query, and the breadth of component libraries make React the pragmatic choice. Vue and Svelte are fine frameworks but have smaller ecosystems for data-table-heavy UIs.

**Why not Next.js/Remix:** This is a single-page internal tool, not a public website. No need for SSR, SEO, or server components. A plain Vite + React SPA is simpler, faster to build, and easier to serve from the FastAPI backend (or a simple nginx container).

**Why not htmx/server-rendered HTML:** The manual review UI (drag-and-drop event grouping, split/merge operations) benefits from React's component model and state management. Pure server rendering would make the review interactions awkward.

### Testing

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| pytest | >=8.3 | Python test framework | Standard, extensible, excellent async support with pytest-asyncio. | HIGH |
| pytest-asyncio | >=0.24 | Async test support | Required for testing async FastAPI endpoints and database operations. | HIGH |
| httpx | >=0.28 | HTTP client / test client | FastAPI's recommended test client (via `AsyncClient`). Also useful as a production HTTP client for LLM API calls. | HIGH |
| Vitest | >=2.1 | Frontend test framework | Vite-native, fast, Jest-compatible API. Standard for Vite + React projects. | HIGH |

### Infrastructure & Tooling

| Technology | Version | Purpose | Why | Confidence |
|------------|---------|---------|-----|------------|
| Docker | latest | Containerization | Required per project constraints. Multi-stage builds for Python (slim) and frontend (nginx). | HIGH |
| Docker Compose | v2 | Local orchestration | Defines the service stack: API server, file watcher, frontend, PostgreSQL (for dev). | HIGH |
| uv | >=0.5 | Python package manager | 10-100x faster than pip. Handles virtual environments, dependency resolution, and lockfiles. The modern standard for Python projects in 2025+. | HIGH |
| Ruff | >=0.8 | Linter & formatter | Replaces flake8, black, isort, and pylint. Written in Rust, extremely fast. Single tool for all Python code quality. | HIGH |
| pre-commit | >=4.0 | Git hook management | Runs ruff, type checks, and tests before commits. | MEDIUM |
| mypy | >=1.13 | Static type checking | Catches type errors in the matching pipeline where correctness matters most. | MEDIUM |

**Why uv over pip/poetry/pipenv:** uv is dramatically faster, handles everything pip does plus lockfiles and virtual environments, and is rapidly becoming the community standard. Poetry is slower and more opinionated. pip lacks lockfile support natively.

**Why Ruff over separate tools:** One tool replaces four (black + isort + flake8 + pylint). Faster than any of them individually. Configuration in pyproject.toml. No reason to use the separate tools anymore.

---

## Alternatives Considered

| Category | Recommended | Alternative | Why Not |
|----------|-------------|-------------|---------|
| Language | Python 3.12+ | TypeScript/Node | Poor NLP/fuzzy matching ecosystem |
| Language | Python 3.12+ | Go | Slower development, no fuzzy matching libs |
| Backend | FastAPI | Django | Too heavy, ORM/admin overhead unnecessary |
| Backend | FastAPI | Flask | No native async, no auto-validation |
| ORM | SQLAlchemy 2.0 | Django ORM | Tied to Django framework |
| ORM | SQLAlchemy 2.0 | Tortoise ORM | Less mature, smaller ecosystem |
| Fuzzy matching | rapidfuzz | thefuzz/fuzzywuzzy | 10-100x slower, GPL licensed |
| Fuzzy matching | rapidfuzz | dedupe | Over-engineered for known matching signals |
| AI matching | gpt-4o-mini via openai SDK | Local LLM (Ollama) | Unjustified complexity for 200 calls/week |
| AI matching | gpt-4o-mini via openai SDK | sentence-transformers | Poor at semantic event matching |
| File watcher | watchfiles | watchdog | Slower, worse Docker support |
| Task queue | asyncio (in-process) | Celery | Massive overkill for 2000 events/week |
| Frontend | React + Vite | Next.js | SSR unnecessary for internal SPA |
| Frontend | React + Vite | htmx | Review UI needs rich interactivity |
| Frontend | React + Vite | Vue/Svelte | Smaller data-table ecosystem |
| Styling | Tailwind CSS | CSS Modules | Slower to build internal tools |
| Styling | Tailwind CSS | shadcn/ui | Good option to add later, not required initially |
| Package mgr | uv | pip/poetry | Dramatically slower, fewer features |

---

## PostgreSQL Extensions (Leverage Existing DB)

| Extension | Purpose | Why |
|-----------|---------|-----|
| pg_trgm | Trigram similarity for fuzzy text search | `similarity()` and `%` operator for fast in-DB title matching. Can pre-filter candidates before Python-side detailed matching. |
| PostGIS | Geographic queries | `ST_DDistance` for proximity matching on event coordinates. Already has geo data with confidence scores. |
| unaccent | Unicode normalization | Normalize German umlauts and accented characters for consistent matching. |

These are PostgreSQL extensions, not Python packages. Enable them with `CREATE EXTENSION IF NOT EXISTS`. pg_trgm and unaccent are part of PostgreSQL's contrib modules (included in standard installs). PostGIS may need separate installation in Docker.

---

## Installation

### Python Backend

```bash
# Initialize project with uv
uv init event-deduplication
cd event-deduplication

# Core dependencies
uv add fastapi uvicorn pydantic sqlalchemy asyncpg alembic
uv add rapidfuzz scikit-learn geopy
uv add watchfiles httpx
uv add openai  # For AI-assisted matching

# Dev dependencies
uv add --dev pytest pytest-asyncio mypy ruff pre-commit
```

### Frontend

```bash
# Create Vite + React + TypeScript project
npm create vite@latest frontend -- --template react-ts
cd frontend

# Core dependencies
npm install @tanstack/react-table @tanstack/react-query

# Styling
npm install tailwindcss @tailwindcss/vite

# Dev dependencies
npm install -D vitest @testing-library/react @testing-library/jest-dom
```

### Docker Base Images

```dockerfile
# Python service
FROM python:3.12-slim AS base

# Frontend (build stage)
FROM node:22-alpine AS frontend-build

# Frontend (serve stage)
FROM nginx:alpine AS frontend
```

---

## Architecture Implications

This stack naturally splits into these containers:

1. **API Server** (FastAPI + Uvicorn): Serves the REST API for the frontend, handles manual review operations
2. **Worker** (Python + watchfiles): Watches for new JSON files, runs the deduplication pipeline, writes to PostgreSQL
3. **Frontend** (nginx serving static React build): Serves the SPA, proxies API calls to the API server
4. **PostgreSQL** (dev only, existing in production): Database

The API server and worker share the same Python codebase but run different entrypoints. This avoids duplicating the matching logic.

---

## Version Confidence Note

All versions listed are based on training data through mid-2025. The recommended minimum versions (`>=X.Y`) are conservative -- actual latest versions in February 2026 are likely higher. Before starting development:

1. Run `uv add <package>` without version pins to get the latest
2. Run `npm install <package>` without version pins to get the latest
3. Pin versions in lockfiles after initial install

The library choices themselves (rapidfuzz, FastAPI, SQLAlchemy, React, etc.) are stable recommendations unlikely to have changed. These are all mature, actively maintained projects with strong communities.

---

## Sources

- Training data (through mid-2025) -- versions are MEDIUM confidence, library choices are HIGH confidence
- Project constraints from PROJECT.md (PostgreSQL, Docker, JSON input, 2000 events/week)
- Direct experience with the Python text-processing and FastAPI ecosystems
