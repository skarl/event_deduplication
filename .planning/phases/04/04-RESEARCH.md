# Phase 4: API & Browse Frontend - Research

**Researched:** 2026-02-28
**Domain:** FastAPI REST API design, React SPA with Vite, PostgreSQL search/filtering, Nginx reverse proxy
**Confidence:** HIGH

## Summary

Phase 4 turns the existing data (canonical events, source events, match decisions) into a usable browse-and-search interface. The work divides naturally into two layers: (1) a FastAPI REST API that exposes canonical events with filtering, pagination, and source-event drill-down, and (2) a React single-page application served via Nginx that consumes the API.

The API layer builds on the existing FastAPI skeleton (`api/app.py` with `/health` endpoint) and the existing async SQLAlchemy infrastructure (async engine, session factory, Pydantic settings). The core challenge is designing query endpoints that support title search (via PostgreSQL `pg_trgm` trigram similarity or `ILIKE`), filtering by city/date-range/category, pagination, and joining through `canonical_event_sources` to `source_events` and `match_decisions` for the detail/drill-down views.

The frontend is a desktop-first internal tool (mobile responsiveness is explicitly out of scope). React + Vite + TypeScript is the standard choice for this kind of SPA. The UI needs three views: a searchable list, a detail view, and a source-event comparison panel. TanStack Query handles server state/caching, and a lightweight component library like shadcn/ui provides data table, card, and badge components without heavy dependencies.

**Primary recommendation:** Use manual offset pagination with Pydantic response schemas (no fastapi-pagination library -- the pagination is simple enough to hand-write and avoids a dependency). Serve the React build via Nginx (already in docker-compose as the `frontend` service), proxying `/api/` to the FastAPI container. Use `pg_trgm` with a GIN index on `canonical_events.title` for fast title search, and standard SQL `WHERE` clauses with indexes for city/date/category filters.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UI-01 | Searchable paginated list of canonical events with filters for title, city, date range, and category | FastAPI endpoint with query params (`q`, `city`, `date_from`, `date_to`, `category`, `page`, `size`); PostgreSQL `pg_trgm` for title search; React list view with TanStack Query for data fetching |
| UI-02 | Canonical event detail view shows all fields (title, description, highlights, dates, location, categories, flags) | FastAPI `GET /api/canonical-events/{id}` with eager-loaded relationships; React detail page with structured field layout |
| UI-03 | Drill-down from canonical event to all contributing source events with side-by-side comparison | FastAPI endpoint returns source events via `canonical_event_sources` join; React comparison panel showing source events in columns |
| UI-04 | Match confidence indicators show per-source signal scores (title similarity %, geo distance, date match) | `match_decisions` table already stores `title_score`, `geo_score`, `date_score`, `description_score` per pair; API exposes these scores keyed by source event; React renders score badges/bars per source |
</phase_requirements>

## Standard Stack

### Core (Backend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115 | REST API framework | Already installed; async, auto-generates OpenAPI docs, Pydantic integration |
| SQLAlchemy | >=2.0 | Async ORM queries | Already installed; `selectinload` for eager-loading relationships |
| Pydantic | >=2.9 | Response schemas | Already installed; `from_attributes=True` for ORM-to-schema conversion |
| asyncpg | >=0.30 | PostgreSQL async driver | Already installed |
| uvicorn | >=0.34 | ASGI server | Already installed |

### Core (Frontend)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.x | UI framework | Industry standard for SPAs; the roadmap explicitly mentions React |
| Vite | 6.x | Build tool | Instant HMR, zero-config, standard for React SPAs in 2025-2026 |
| TypeScript | 5.x | Type safety | Catches API contract mismatches at compile time |
| TanStack Query | 5.x | Server state management | Automatic caching, pagination support, background refetching |
| React Router | 7.x | Client-side routing | Standard routing for React SPAs; handles list/detail navigation |

### Supporting (Frontend)
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| Tailwind CSS | 4.x | Utility-first styling | All component styling; avoids CSS files, fast iteration |
| shadcn/ui | latest | UI component library | Data tables, cards, badges, inputs, buttons -- copy-paste components, not a dependency |
| @tanstack/react-table | 8.x | Headless table logic | Powers the canonical events list with sorting, filtering columns |
| date-fns | 4.x | Date formatting/parsing | Display date ranges in German locale, date filter logic |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| Manual pagination | fastapi-pagination library | Library adds a dependency for ~20 lines of pagination code; manual is simpler here |
| shadcn/ui | Material UI / Ant Design | MUI/AntD are heavier bundles; shadcn/ui copies source code so no runtime dependency, better for internal tools |
| TanStack Query | SWR | TanStack Query has better pagination primitives (keepPreviousData, placeholderData) |
| React Router | TanStack Router | TanStack Router has type-safe routing but steeper learning curve; React Router is more established |
| Tailwind CSS | CSS Modules | Tailwind is faster for prototyping internal tools; CSS Modules add more files |

**Installation (Backend):**
```bash
# No new Python packages needed -- FastAPI, SQLAlchemy, Pydantic already installed
# Only need: Alembic migration to add pg_trgm extension + GIN index
```

**Installation (Frontend):**
```bash
npm create vite@latest frontend -- --template react-ts
cd frontend
npm install @tanstack/react-query @tanstack/react-table react-router-dom date-fns
npm install -D tailwindcss @tailwindcss/vite
# shadcn/ui: npx shadcn@latest init, then add components as needed
```

## Architecture Patterns

### Recommended Project Structure
```
src/event_dedup/
├── api/
│   ├── __init__.py
│   ├── app.py               # FastAPI app with lifespan, CORS, router includes
│   ├── deps.py               # Dependency injection (get_session, etc.)
│   ├── schemas.py             # Pydantic response/request schemas
│   └── routes/
│       ├── __init__.py
│       ├── canonical_events.py  # GET /api/canonical-events, GET /api/canonical-events/{id}
│       └── health.py            # GET /health (existing)
├── ...existing modules...

frontend/
├── src/
│   ├── main.tsx               # App entry point
│   ├── App.tsx                # Router setup
│   ├── api/
│   │   └── client.ts          # API client (fetch wrapper, types)
│   ├── components/
│   │   ├── EventList.tsx       # Searchable paginated list (UI-01)
│   │   ├── EventDetail.tsx     # Full detail view (UI-02)
│   │   ├── SourceComparison.tsx # Side-by-side sources (UI-03)
│   │   ├── ConfidenceIndicator.tsx # Score badges/bars (UI-04)
│   │   └── ui/                # shadcn/ui components (table, card, badge, etc.)
│   ├── hooks/
│   │   └── useCanonicalEvents.ts  # TanStack Query hooks
│   └── types/
│       └── index.ts           # TypeScript types matching API schemas
├── index.html
├── vite.config.ts
├── tailwind.config.ts
├── tsconfig.json
└── package.json

docker/
├── Dockerfile.frontend        # Multi-stage: Node build + Nginx serve
├── nginx.conf                 # Reverse proxy: / -> React, /api/ -> FastAPI
└── ...existing files...
```

### Pattern 1: Pydantic Response Schemas with `from_attributes`
**What:** Separate Pydantic models for API responses that map directly from SQLAlchemy ORM objects using `model_config = ConfigDict(from_attributes=True)`.
**When to use:** Every API endpoint that returns database objects.
**Example:**
```python
# Source: FastAPI + Pydantic v2 official pattern
from pydantic import BaseModel, ConfigDict

class CanonicalEventSummary(BaseModel):
    """List view -- lightweight fields only."""
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    location_city: str | None
    dates: list | None
    categories: list | None
    source_count: int
    match_confidence: float | None
    needs_review: bool

class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int
```

### Pattern 2: Async Query with Filtering and Pagination
**What:** Build SQLAlchemy select statements dynamically based on query parameters, apply filters conditionally, then paginate with offset/limit.
**When to use:** The canonical events list endpoint.
**Example:**
```python
async def list_canonical_events(
    session: AsyncSession,
    q: str | None = None,
    city: str | None = None,
    date_from: date | None = None,
    date_to: date | None = None,
    category: str | None = None,
    page: int = 1,
    size: int = 20,
) -> tuple[list[CanonicalEvent], int]:
    stmt = select(CanonicalEvent)

    if q:
        # pg_trgm similarity search on title
        stmt = stmt.where(CanonicalEvent.title.ilike(f"%{q}%"))
    if city:
        stmt = stmt.where(CanonicalEvent.location_city.ilike(f"%{city}%"))
    if category:
        # JSON array contains -- PostgreSQL specific
        stmt = stmt.where(
            CanonicalEvent.categories.op("@>")(sa.cast([category], sa.JSON))
        )

    # Count total before pagination
    count_stmt = select(sa.func.count()).select_from(stmt.subquery())
    total = (await session.execute(count_stmt)).scalar_one()

    # Paginate
    stmt = stmt.offset((page - 1) * size).limit(size)
    stmt = stmt.order_by(CanonicalEvent.id)
    result = await session.execute(stmt)

    return result.scalars().all(), total
```

### Pattern 3: Nginx Reverse Proxy for SPA + API
**What:** Nginx serves the React static build at `/` and proxies `/api/` requests to the FastAPI container.
**When to use:** Always -- this is the production serving pattern.
**Example (nginx.conf):**
```nginx
server {
    listen 80;

    # React SPA -- serve static files, fallback to index.html for client routing
    location / {
        root /usr/share/nginx/html;
        try_files $uri $uri/ /index.html;
    }

    # API reverse proxy
    location /api/ {
        proxy_pass http://api:8000/api/;
        proxy_set_header Host $host;
        proxy_set_header X-Real-IP $remote_addr;
    }

    # OpenAPI docs passthrough
    location /docs {
        proxy_pass http://api:8000/docs;
    }
    location /openapi.json {
        proxy_pass http://api:8000/openapi.json;
    }
}
```

### Pattern 4: TanStack Query with Pagination
**What:** React hooks that fetch paginated data from the API, with automatic caching and background refetching.
**When to use:** The canonical events list component.
**Example:**
```typescript
// Source: TanStack Query pagination pattern
import { useQuery, keepPreviousData } from '@tanstack/react-query';

function useCanonicalEvents(filters: EventFilters, page: number) {
  return useQuery({
    queryKey: ['canonical-events', filters, page],
    queryFn: () => fetchCanonicalEvents({ ...filters, page }),
    placeholderData: keepPreviousData,  // Keep old data visible while loading next page
  });
}
```

### Anti-Patterns to Avoid
- **Fetching all events client-side and filtering in JS:** Always filter/paginate server-side. Even 2000 events is too many to send in one response.
- **Using SQLAlchemy lazy loading in async context:** Always use `selectinload()` or `joinedload()` for relationships. Lazy loading triggers synchronous I/O which will error in async.
- **Putting business logic in API routes:** Keep routes thin -- delegate to query functions that can be tested independently.
- **Hardcoding API URLs in frontend:** Use a relative path `/api/` so the Nginx proxy handles routing. No CORS needed.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Server state caching in React | Custom fetch + useState/useEffect | TanStack Query | Handles stale-while-revalidate, deduplication, background refetching, pagination state |
| Data table with sorting/filtering | Custom table component with manual sorting | @tanstack/react-table + shadcn/ui Table | Column definitions, sorting state, filter state, pagination -- all handled |
| Date display formatting | Custom date format functions | date-fns `format()` with `de` locale | German date formats, relative time, range display |
| API type safety | Manual TypeScript type definitions | Generate from OpenAPI spec (optional) | FastAPI auto-generates OpenAPI; can generate TS types from it |
| CSS component library | Custom button/card/input components | shadcn/ui | Copy-paste source, fully customizable, consistent styling |
| Fuzzy text search in PostgreSQL | Application-level string matching | pg_trgm extension + GIN index | Database-level trigram matching is orders of magnitude faster |

**Key insight:** The frontend is a read-only browse tool for Phase 4 (write operations come in Phase 6). Keep it simple: fetch, display, paginate. TanStack Query + shadcn/ui eliminates most of the boilerplate.

## Common Pitfalls

### Pitfall 1: Lazy Loading in Async SQLAlchemy
**What goes wrong:** Accessing `canonical_event.sources` triggers a synchronous lazy load, which raises `MissingGreenlet` in async context.
**Why it happens:** SQLAlchemy defaults to lazy loading for relationships. In sync code this works transparently; in async it fails.
**How to avoid:** Always use `selectinload(CanonicalEvent.sources)` in queries. For nested relationships (sources -> source_event), chain: `selectinload(CanonicalEvent.sources).selectinload(CanonicalEventSource.source_event)`.
**Warning signs:** `MissingGreenlet` or `greenlet_spawn` errors at runtime.

### Pitfall 2: N+1 Queries for Source Events
**What goes wrong:** Fetching a canonical event's sources triggers one query per source event, causing O(N) queries.
**Why it happens:** Not eager-loading the `source_event` relationship on `CanonicalEventSource`.
**How to avoid:** Use `selectinload` chains: `selectinload(CanonicalEvent.sources).selectinload(CanonicalEventSource.source_event).selectinload(SourceEvent.dates)`.
**Warning signs:** Slow detail page loads, many SQL queries in logs.

### Pitfall 3: JSON Column Filtering in PostgreSQL
**What goes wrong:** Filtering canonical events by category (stored as JSON array) requires PostgreSQL-specific operators, not Python list operations.
**Why it happens:** The `categories` field is `sa.JSON`, which in PostgreSQL is a JSON column. Standard SQL `WHERE` does not work on JSON arrays.
**How to avoid:** Use PostgreSQL's `@>` (contains) operator: `CanonicalEvent.categories.op("@>")(cast([category], JSON))`. Alternatively, use `func.json_array_elements_text` for more complex queries.
**Warning signs:** Empty results when filtering by category despite data existing.

### Pitfall 4: CORS Issues During Frontend Development
**What goes wrong:** React dev server (Vite on port 5173) cannot reach FastAPI (port 8000) due to CORS.
**Why it happens:** Browser blocks cross-origin requests by default. In production, Nginx proxies everything through one origin, but during development the frontend and API run on different ports.
**How to avoid:** Two options: (a) Add CORS middleware to FastAPI for development only, or (b) configure Vite's proxy to forward `/api/` requests to FastAPI. Option (b) is preferred because it matches the production Nginx proxy pattern.
**Warning signs:** Browser console shows "CORS policy" errors.

### Pitfall 5: React SPA Routing with Nginx
**What goes wrong:** Navigating directly to `/events/42` returns a 404 from Nginx.
**Why it happens:** Nginx tries to find a file at `/events/42` which does not exist. The React Router needs to handle it client-side.
**How to avoid:** The `try_files $uri $uri/ /index.html` directive in nginx.conf falls back to index.html for any path that does not match a static file.
**Warning signs:** Direct URL access or page refresh returns 404.

### Pitfall 6: Match Decision Lookup for UI-04
**What goes wrong:** Displaying per-source signal scores requires finding the right `MatchDecision` rows, but the canonical ordering constraint means `source_event_id_a < source_event_id_b`.
**Why it happens:** Match decisions use canonical ordering. When looking up scores for source event X relative to source event Y, you must query with the IDs in sorted order.
**How to avoid:** When fetching match decisions for a canonical event's source group, query all decisions where both IDs are in the set of source event IDs for that canonical. The `WHERE source_event_id_a IN (:ids) AND source_event_id_b IN (:ids)` pattern works.
**Warning signs:** Missing match scores for some source pairs.

## Code Examples

Verified patterns from official sources and project conventions:

### FastAPI Dependency Injection for DB Session
```python
# Source: project convention from db/session.py
from fastapi import Depends
from sqlalchemy.ext.asyncio import AsyncSession
from event_dedup.db.session import get_session_factory

async def get_db() -> AsyncGenerator[AsyncSession, None]:
    factory = get_session_factory()
    async with factory() as session:
        yield session

# Usage in route
@router.get("/canonical-events")
async def list_events(
    db: AsyncSession = Depends(get_db),
    q: str | None = None,
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
):
    ...
```

### Eager Loading with Relationship Chains
```python
# Source: SQLAlchemy 2.0 selectinload pattern
from sqlalchemy.orm import selectinload

stmt = (
    select(CanonicalEvent)
    .where(CanonicalEvent.id == event_id)
    .options(
        selectinload(CanonicalEvent.sources)
        .selectinload(CanonicalEventSource.source_event)
        .selectinload(SourceEvent.dates)
    )
)
result = await session.execute(stmt)
canonical = result.scalar_one_or_none()
```

### PostgreSQL pg_trgm Extension Migration
```python
# Alembic migration to enable pg_trgm and add GIN index
def upgrade() -> None:
    op.execute("CREATE EXTENSION IF NOT EXISTS pg_trgm")
    op.create_index(
        "ix_canonical_events_title_trgm",
        "canonical_events",
        ["title"],
        postgresql_using="gin",
        postgresql_ops={"title": "gin_trgm_ops"},
    )

def downgrade() -> None:
    op.drop_index("ix_canonical_events_title_trgm")
    op.execute("DROP EXTENSION IF EXISTS pg_trgm")
```

### Vite Proxy Configuration for Development
```typescript
// vite.config.ts
import { defineConfig } from 'vite';
import react from '@vitejs/plugin-react';
import tailwindcss from '@tailwindcss/vite';

export default defineConfig({
  plugins: [react(), tailwindcss()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
    },
  },
});
```

### Multi-Stage Dockerfile for React Frontend
```dockerfile
# Stage 1: Build React app
FROM node:22-alpine AS builder
WORKDIR /app
COPY frontend/package*.json ./
RUN npm ci
COPY frontend/ .
RUN npm run build

# Stage 2: Serve with Nginx
FROM nginx:alpine
COPY docker/nginx.conf /etc/nginx/conf.d/default.conf
COPY --from=builder /app/dist /usr/share/nginx/html
EXPOSE 80
```

### TanStack Query Provider Setup
```typescript
// Source: TanStack Query official docs
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      staleTime: 30_000,       // 30 seconds before refetch
      retry: 1,
    },
  },
});

function App() {
  return (
    <QueryClientProvider client={queryClient}>
      <RouterProvider router={router} />
    </QueryClientProvider>
  );
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| Create React App | Vite + React | 2023+ | CRA is deprecated; Vite is 10-20x faster HMR |
| REST + manual fetch/useEffect | TanStack Query v5 | 2023+ | Eliminates boilerplate for caching, pagination, loading states |
| Bootstrap/jQuery UI tables | @tanstack/react-table + headless UI | 2022+ | Headless approach gives full styling control with TailwindCSS |
| Full CSS frameworks (Material UI) | shadcn/ui (copy-paste components) | 2023+ | No runtime dependency, full customization, smaller bundles |
| CORS configuration for SPA | Nginx reverse proxy | Always | No CORS needed when frontend and API share origin |
| Synchronous SQLAlchemy | Async SQLAlchemy 2.0 + asyncpg | 2023+ | Non-blocking DB queries in FastAPI async handlers |

**Deprecated/outdated:**
- Create React App: deprecated by React team, use Vite or a framework
- `fastapi.encoders.jsonable_encoder` for response serialization: Pydantic v2 `model_validate` + `from_attributes` is cleaner
- Class-based views in FastAPI: function-based route handlers with `Depends()` is the standard pattern

## Open Questions

1. **pg_trgm vs ILIKE for title search**
   - What we know: `pg_trgm` with GIN index provides fast similarity-based search. Simple `ILIKE '%term%'` works too but cannot use B-tree indexes (requires sequential scan). The REQUIREMENTS.md says "PostgreSQL pg_trgm handles this volume trivially."
   - What's unclear: Whether the title search needs fuzzy/typo-tolerant matching (pg_trgm) or just substring matching (ILIKE). At ~2000 events, even sequential scan ILIKE is fast enough.
   - Recommendation: Add `pg_trgm` extension and GIN index in an Alembic migration. Use `ILIKE` for the initial search implementation (simpler query). The index supports both `ILIKE` and similarity queries, so we can switch to fuzzy matching later without schema changes.

2. **Date range filtering on JSON column**
   - What we know: `canonical_events.dates` is a JSON column containing an array of date objects. Filtering by date range requires extracting dates from JSON.
   - What's unclear: Whether to filter on the JSON dates column or add a denormalized `first_date`/`last_date` column for efficient range queries.
   - Recommendation: Add `first_date` and `last_date` columns to `canonical_events` (populated during synthesis). These are cheaper to index and query than JSON extraction. The Alembic migration for Phase 4 can add these columns, and the synthesizer can populate them.

3. **Match decision scores for UI-04**
   - What we know: `match_decisions` stores pairwise scores between source events. For a canonical event with N sources, there are up to N*(N-1)/2 pair scores.
   - What's unclear: How to present these pairwise scores in the UI. Each source event could show its average score, or scores could be shown per-pair.
   - Recommendation: Display per-pair scores in the source comparison view. For each source event in the group, show its individual signal scores against the "anchor" (first/primary) source, plus its combined score. The API should return all match decisions for the source event group.

## Sources

### Primary (HIGH confidence)
- Project codebase: `src/event_dedup/models/` -- SQLAlchemy models define the exact schema
- Project codebase: `src/event_dedup/api/app.py` -- existing FastAPI skeleton
- Project codebase: `docker-compose.yml` -- existing Docker infrastructure with nginx placeholder
- Project codebase: `src/event_dedup/db/session.py` -- async session factory pattern
- Project codebase: `src/event_dedup/worker/persistence.py` -- query patterns for source events
- [PostgreSQL pg_trgm documentation](https://www.postgresql.org/docs/current/pgtrgm.html) -- trigram index types and operators
- [FastAPI official docs - SQL databases](https://fastapi.tiangolo.com/tutorial/sql-databases/) -- Pydantic + SQLAlchemy integration
- [TanStack Query pagination docs](https://tanstack.com/query/latest/docs/framework/react/examples/pagination) -- keepPreviousData pattern

### Secondary (MEDIUM confidence)
- [Vite + React recommended stack 2025](https://www.joaovinezof.com/blog/react-2025-building-modern-apps-with-vite) -- confirmed Vite as standard React build tool
- [shadcn/ui data table](https://ui.shadcn.com/docs/components/radix/data-table) -- TanStack Table integration pattern
- [FastAPI + React + Nginx Docker pattern](https://github.com/Happily-Coding/FastapiReactNginxDocker) -- reference architecture for the three-container setup

### Tertiary (LOW confidence)
- None -- all critical claims verified with primary or secondary sources

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - FastAPI, SQLAlchemy, React, Vite are all already decided or industry standard; versions verified against pyproject.toml and current releases
- Architecture: HIGH - Nginx reverse proxy pattern is well-established; project already has the Docker infrastructure; API follows existing codebase patterns
- Pitfalls: HIGH - Async SQLAlchemy lazy loading, N+1 queries, JSON filtering, CORS, SPA routing are all well-documented issues with known solutions

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable domain, 30-day validity)
