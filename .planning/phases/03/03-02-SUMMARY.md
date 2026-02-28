---
phase: 03-pipeline-integration
plan: 02
subsystem: docker-infrastructure
tags: [docker, compose, fastapi, nginx, dockerfile, entrypoint, uv]
dependency_graph:
  requires: [03-01]
  provides: [docker-compose-stack, fastapi-health-endpoint, docker-build-worker, docker-build-api]
  affects: [deployment, api-server, pipeline-worker]
tech_stack:
  added: [fastapi, uvicorn, httpx]
  patterns: [multi-stage-docker-build, uv-docker-sync, entrypoint-migration, compose-healthcheck]
key_files:
  created:
    - src/event_dedup/api/__init__.py
    - src/event_dedup/api/app.py
    - docker/Dockerfile.worker
    - docker/Dockerfile.api
    - docker/entrypoint.sh
    - docker/nginx-placeholder.html
    - docker-compose.yml
    - .dockerignore
  modified:
    - pyproject.toml
    - uv.lock
decisions:
  - Python-based health check in Dockerfile.api (urllib.request) to avoid installing curl in slim image
  - Generic entrypoint.sh with exec "$@" so both worker and API containers share the same entrypoint
  - httpx added to dev dependencies for FastAPI TestClient support
metrics:
  duration: 2m
  completed: 2026-02-28
  tasks_completed: 2
  tasks_total: 2
  files_created: 8
  files_modified: 2
  total_test_suite: 272
---

# Phase 3 Plan 2: Docker Infrastructure Summary

Docker infrastructure with multi-stage uv-based Dockerfiles for worker and API, shared entrypoint running Alembic migrations, docker-compose orchestrating PostgreSQL/worker/API/frontend with health checks, and a FastAPI skeleton with /health endpoint.

## What Was Built

### FastAPI Skeleton (`api/app.py`, 14 lines)
Minimal FastAPI app with a single `GET /health` endpoint returning `{"status": "ok"}`. This is the skeleton that Phase 4 will expand with real routes for canonical events, match decisions, and review workflows.

### Dockerfile.worker (multi-stage, 40 lines)
Two-stage build: (1) `ghcr.io/astral-sh/uv:python3.12-bookworm-slim` builder installs dependencies with `uv sync --locked`, (2) `python:3.12-slim-bookworm` runtime with libpq5 for psycopg2, non-root `app` user, shared entrypoint for Alembic migrations, CMD runs `python -m event_dedup.worker`.

### Dockerfile.api (multi-stage, 40 lines)
Same two-stage pattern as worker. Health check uses Python urllib (no curl needed in slim image). CMD runs `uvicorn event_dedup.api.app:app --host 0.0.0.0 --port 8000`.

### Entrypoint Script (`docker/entrypoint.sh`, 8 lines)
Shared by both worker and API containers. Runs `alembic -c config/alembic.ini upgrade head` then `exec "$@"` to pass Docker CMD as the application command. The `exec` ensures Docker signals (SIGTERM) reach the application process directly.

### docker-compose.yml (4 services, 58 lines)
- **db**: PostgreSQL 16 Alpine with `pg_isready` health check
- **worker**: Builds from Dockerfile.worker, mounts eventdata and dead_letters volumes, depends on db health
- **api**: Builds from Dockerfile.api, exposes port 8000, depends on db health
- **frontend**: nginx Alpine serving placeholder HTML on port 3000

All configuration via environment variables (EVENT_DEDUP_ prefix + ALEMBIC_DATABASE_URL).

### .dockerignore (13 entries)
Excludes .git, .venv, __pycache__, tests, .planning, .claude, and runtime data directories from Docker build context.

### Dependencies Added
- `fastapi>=0.115` and `uvicorn[standard]>=0.34` to project dependencies
- `httpx>=0.28` to dev dependencies (required by Starlette TestClient)

## Deviations from Plan

### Auto-fixed Issues

**1. [Rule 3 - Blocking] Added httpx to dev dependencies for TestClient**
- **Found during:** Task 1
- **Issue:** FastAPI's TestClient (via Starlette) requires httpx, which was not installed. The verification script failed with `ModuleNotFoundError: No module named 'httpx'`.
- **Fix:** Added `httpx>=0.28` to both `[project.optional-dependencies] dev` and `[dependency-groups] dev` in pyproject.toml.
- **Files modified:** pyproject.toml
- **Commit:** cecbf85

## Verification Results

All verification checks from the plan pass:
- docker-compose.yml parses correctly: PASS (`docker compose config --quiet`)
- FastAPI /health endpoint returns 200 with {"status": "ok"}: PASS
- entrypoint.sh bash syntax valid: PASS (`bash -n`)
- All 6 required files exist: PASS
- Full test suite (272 tests): PASS (0.64s)

## Commits

| Task | Commit  | Description |
|------|---------|-------------|
| 1    | cecbf85 | FastAPI skeleton with /health endpoint, fastapi+uvicorn+httpx deps |
| 2    | 71ab45f | Dockerfiles, entrypoint, docker-compose, nginx placeholder, .dockerignore |

## Requirements Addressed

- **DEPL-01**: All services run as Docker containers (pipeline worker, API server, frontend via nginx)
- **DEPL-02**: docker-compose.yml defines the full stack including PostgreSQL with health checks
- **DEPL-03**: Environment-based configuration via EVENT_DEDUP_ prefix and ALEMBIC_DATABASE_URL

## Self-Check: PASSED

All 8 created files verified present. All 2 task commits verified in git log.
