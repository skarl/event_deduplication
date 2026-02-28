# Phase 11: Frontend UX Improvements - Research

**Researched:** 2026-02-28
**Domain:** React/TypeScript frontend with TanStack Query, Tailwind CSS, FastAPI backend
**Confidence:** HIGH

## Summary

Phase 11 adds four UX improvements to the existing event list: chip/tag selectors for category and city filters (UIX-01, UIX-02), column sorting on all columns (UIX-03), and configurable rows-per-page with options 25/50/100/200/ALL (UIX-04).

The frontend stack is React 19, TanStack Query 5, React Router 7, Tailwind CSS 4, and date-fns — no external component library exists. All UI must be hand-built with Tailwind. The existing `EventList.tsx` already renders a 7-column table with title, city, date, categories, sources, confidence, and review status. `SearchFilters.tsx` currently uses plain text inputs for city and category. The `Pagination.tsx` component has no page-size control. `useCanonicalEvents` already accepts a `size` parameter but it defaults to 20 and is never surfaced in the UI.

The backend `GET /api/canonical-events` accepts `q`, `city`, `date_from`, `date_to`, `category`, `page`, and `size`. Two gaps exist: (1) `size` is capped at `le=100` in FastAPI's Query validator — this must be raised or removed for ALL-mode; (2) there are no dedicated endpoints for distinct cities or categories — these must be added. Categories in the dataset are a small, stable set (~16 values) stored as JSON arrays in `canonical_events.categories`. Cities are ~65 values stored in `canonical_events.location_city`.

**Primary recommendation:** Build all new UI as pure Tailwind + React without adding any component library. Add two new backend endpoints for distinct values. Implement chip selectors as controlled multi-value state arrays, sorting via `sort_by`/`sort_dir` URL params, and page size via a `size` URL param.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| UIX-01 | Category filter as chip/tag selector — autocomplete from DB, removable chips | New `/api/canonical-events/categories` endpoint returns distinct values; frontend multi-select state with chip rendering |
| UIX-02 | City filter as chip/tag selector — same behavior as categories | New `/api/canonical-events/cities` endpoint returns distinct values; same chip component pattern |
| UIX-03 | Column sorting on all 7 columns — click header toggles asc/desc | Add `sort_by` + `sort_dir` URL params to frontend state and backend route; `sort_by` maps to SQLAlchemy column attributes |
| UIX-04 | Configurable rows per page: 25, 50, 100, 200, ALL | Add `size` URL param; remove `le=100` cap on backend; render select/buttons in Pagination component |
</phase_requirements>

## Standard Stack

### Core (already in project)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| React | 19.2.0 | UI components | Already in use throughout |
| TanStack Query | 5.90.21 | Server state, caching, loading states | Already used for all data fetching |
| React Router DOM | 7.13.1 | URL params as state for filters/sorting/pagination | Already used in EventList with useSearchParams |
| Tailwind CSS | 4.2.1 | Styling all new UI elements | Already used for all styling |
| date-fns | 4.1.0 | Date formatting | Already used in EventList |
| FastAPI | 0.115+ | New distinct-value endpoints | Already used for all API routes |
| SQLAlchemy | 2.0+ | Sorting queries via column attributes | Already used for all queries |

### No New Dependencies Needed
This phase requires zero new npm packages or Python packages. All functionality is achievable with the existing stack.

## Architecture Patterns

### Recommended File Changes
```
frontend/src/
├── api/
│   └── client.ts              EXTEND: add fetchDistinctCategories, fetchDistinctCities
├── components/
│   ├── EventList.tsx           MODIFY: add sort state/params, pass size to Pagination
│   ├── SearchFilters.tsx       MODIFY: replace city/category text inputs with ChipSelector
│   ├── Pagination.tsx          MODIFY: add page-size selector
│   └── ChipSelector.tsx        NEW: reusable chip/autocomplete component
├── hooks/
│   └── useCanonicalEvents.ts   MODIFY: extend EventFilters to include sort_by/sort_dir
└── types/
    └── index.ts                MODIFY: extend EventFilters type

src/event_dedup/api/routes/
└── canonical_events.py         MODIFY: add /categories and /cities endpoints,
                                         add sort_by/sort_dir params, remove le=100 cap
```

### Pattern 1: URL Params as Single Source of Truth
**What:** All filter, sort, and pagination state lives in `useSearchParams`. No local state for these values in `EventList`.
**When to use:** This is the existing pattern — continue it for all new state (sort_by, sort_dir, size, categories, cities).
**Example:**
```typescript
// EventList.tsx — extend existing parseFiltersFromParams
function parseFiltersFromParams(params: URLSearchParams): EventFilters {
  return {
    q: params.get('q') ?? undefined,
    cities: params.getAll('city'),        // multi-value: ?city=Freiburg&city=Offenburg
    categories: params.getAll('category'), // multi-value: ?category=musik&category=fest
    date_from: params.get('date_from') ?? undefined,
    date_to: params.get('date_to') ?? undefined,
    sort_by: (params.get('sort_by') ?? 'title') as SortColumn,
    sort_dir: (params.get('sort_dir') ?? 'asc') as SortDir,
    size: Number(params.get('size') ?? '25'),
  };
}

function filtersToParams(filters: EventFilters, page: number): URLSearchParams {
  const params = new URLSearchParams();
  if (filters.q) params.set('q', filters.q);
  filters.cities?.forEach(c => params.append('city', c));
  filters.categories?.forEach(c => params.append('category', c));
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.sort_by && filters.sort_by !== 'title') params.set('sort_by', filters.sort_by);
  if (filters.sort_dir && filters.sort_dir !== 'asc') params.set('sort_dir', filters.sort_dir);
  if (filters.size && filters.size !== 25) params.set('size', String(filters.size));
  if (page > 1) params.set('page', String(page));
  return params;
}
```

### Pattern 2: ChipSelector Component
**What:** A self-contained component that shows an input with dropdown suggestions and renders selected values as removable chips.
**When to use:** For both category filter (UIX-01) and city filter (UIX-02).

**State model:**
- `selected: string[]` — currently selected values (controlled, parent owns this)
- `inputValue: string` — current autocomplete input text (local state)
- `isOpen: boolean` — dropdown visibility (local state)
- `options: string[]` — full list fetched from API once (passed as prop or fetched internally)

**Example:**
```typescript
// frontend/src/components/ChipSelector.tsx
interface ChipSelectorProps {
  label: string;
  options: string[];           // all available values from API
  selected: string[];          // currently selected
  onChange: (values: string[]) => void;
  placeholder?: string;
}

export function ChipSelector({ label, options, selected, onChange, placeholder }: ChipSelectorProps) {
  const [inputValue, setInputValue] = useState('');
  const [isOpen, setIsOpen] = useState(false);

  const filtered = options.filter(
    o => o.toLowerCase().includes(inputValue.toLowerCase()) && !selected.includes(o)
  );

  const addItem = (item: string) => {
    onChange([...selected, item]);
    setInputValue('');
    setIsOpen(false);
  };

  const removeItem = (item: string) => {
    onChange(selected.filter(s => s !== item));
  };

  return (
    <div className="relative">
      <label className="block text-xs font-medium text-gray-600 mb-1">{label}</label>
      {/* Chip display row */}
      <div className="flex flex-wrap gap-1 mb-1">
        {selected.map(item => (
          <span key={item} className="inline-flex items-center gap-1 bg-blue-100 text-blue-800 text-xs px-2 py-0.5 rounded">
            {item}
            <button type="button" onClick={() => removeItem(item)} className="hover:text-blue-600">
              &times;
            </button>
          </span>
        ))}
      </div>
      {/* Input */}
      <input
        type="text"
        value={inputValue}
        onChange={e => { setInputValue(e.target.value); setIsOpen(true); }}
        onFocus={() => setIsOpen(true)}
        onBlur={() => setTimeout(() => setIsOpen(false), 150)}
        placeholder={placeholder ?? `Add ${label.toLowerCase()}...`}
        className="w-full px-3 py-1.5 border border-gray-300 rounded text-sm focus:outline-none focus:ring-1 focus:ring-blue-500"
      />
      {/* Dropdown */}
      {isOpen && filtered.length > 0 && (
        <ul className="absolute z-10 mt-1 w-full bg-white border border-gray-200 rounded shadow-lg max-h-48 overflow-auto">
          {filtered.map(item => (
            <li
              key={item}
              onMouseDown={() => addItem(item)}
              className="px-3 py-1.5 text-sm hover:bg-blue-50 cursor-pointer"
            >
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
```

### Pattern 3: Sortable Column Headers
**What:** Column headers render as buttons. Clicking a header sets `sort_by` to that column and toggles `sort_dir` between `asc` and `desc`. Active column shows a sort indicator (▲/▼).
**When to use:** For UIX-03 on all 7 columns.

**Column-to-field mapping:**
| Column header | sort_by value | SQLAlchemy column |
|--------------|---------------|-------------------|
| Title | `title` | `CanonicalEvent.title` |
| City | `city` | `CanonicalEvent.location_city` |
| Date | `date` | `CanonicalEvent.first_date` |
| Categories | `categories` | `CanonicalEvent.categories` (JSON cast to string) |
| Sources | `source_count` | `CanonicalEvent.source_count` |
| Confidence | `confidence` | `CanonicalEvent.match_confidence` |
| Review | `review` | `CanonicalEvent.needs_review` |

**Example:**
```typescript
// In EventList.tsx thead
function SortableHeader({
  label, column, currentSort, currentDir, onSort
}: { label: string; column: SortColumn; currentSort: SortColumn; currentDir: SortDir; onSort: (col: SortColumn) => void }) {
  const isActive = column === currentSort;
  return (
    <th
      className="px-4 py-3 cursor-pointer select-none hover:bg-gray-100"
      onClick={() => onSort(column)}
    >
      <span className="flex items-center gap-1">
        {label}
        {isActive ? (currentDir === 'asc' ? ' ▲' : ' ▼') : ' ↕'}
      </span>
    </th>
  );
}
```

### Pattern 4: Page-Size Selector in Pagination
**What:** Render a `<select>` (or button group) in the Pagination component allowing 25/50/100/200/ALL.
**When to use:** For UIX-04, in Pagination.tsx alongside existing prev/next navigation.
**ALL behavior:** `size=0` or `size=999999` signals "no limit". Backend returns all events in one page.

**Example:**
```typescript
// Pagination.tsx additions
const PAGE_SIZE_OPTIONS = [25, 50, 100, 200, 0] as const; // 0 = ALL
const PAGE_SIZE_LABELS: Record<number, string> = { 0: 'ALL', 25: '25', 50: '50', 100: '100', 200: '200' };

// In render:
<div className="flex items-center gap-2">
  <span className="text-xs text-gray-500">Rows:</span>
  <select
    value={size}
    onChange={e => onSizeChange(Number(e.target.value))}
    className="text-sm border border-gray-300 rounded px-2 py-1"
  >
    {PAGE_SIZE_OPTIONS.map(opt => (
      <option key={opt} value={opt}>{PAGE_SIZE_LABELS[opt]}</option>
    ))}
  </select>
</div>
```

### Anti-Patterns to Avoid
- **Adding a component library (Radix, Headless UI, etc.):** No new npm packages for this phase. Build from Tailwind primitives.
- **Fetching distinct values on every filter change:** Fetch categories and cities once with `staleTime: 300_000` (5 min). They change only when new data is processed.
- **Storing sort/size state in React state instead of URL params:** Breaks browser back button and page refresh. All state must be in `useSearchParams`.
- **Sending `category=` as a comma-separated string:** Use repeated query params (`?category=a&category=b`). The backend must use `Query(default=[])` for list params.
- **Keeping `le=100` on size:** This silently caps the "200" and "ALL" options. Remove the upper bound or set it very high (e.g., 10000).

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Dropdown with keyboard nav | Custom keyboard handler | Simple click + onBlur with setTimeout(150ms) | Sufficient for this operator tool; keyboard nav adds 100+ lines |
| Debounced autocomplete | Custom debounce | No debounce needed — options list is fetched once and filtered client-side | Dataset is small (16 categories, 65 cities) |
| Sort indicators | SVG icons | Unicode characters ▲ ▼ ↕ inline in JSX | Zero dependencies, clear enough for operator tool |
| URL serialization | Custom serializer | `URLSearchParams.getAll()` + `params.append()` | Built-in browser API, already used in the project |
| Async query for large "ALL" result | Custom streaming | Single fetch, increase FastAPI size limit to 10000 | Max ~2000 events expected; fits in memory |

**Key insight:** The dataset is small (operator tool, not public). Simplicity wins over sophistication.

## Common Pitfalls

### Pitfall 1: `onBlur` closes dropdown before `onMouseDown` fires
**What goes wrong:** User clicks a suggestion in the dropdown but the input's `onBlur` fires first, closing the dropdown before the click registers.
**Why it happens:** `blur` fires before `click`/`mousedown` in browser event order.
**How to avoid:** Use `onMouseDown` on dropdown items (not `onClick`), and use `setTimeout(() => setIsOpen(false), 150)` in `onBlur`. `mousedown` fires before `blur`.
**Warning signs:** Clicking suggestions appears to do nothing.

### Pitfall 2: `le=100` cap silently truncates large page sizes
**What goes wrong:** User selects "200" or "ALL" but backend returns only 100 rows with HTTP 200.
**Why it happens:** FastAPI `Query(le=100)` silently caps at 100.
**How to avoid:** Change to `Query(default=25, ge=1, le=10000)` in `canonical_events.py`. For ALL mode, pass `size=10000` or a sentinel value.
**Warning signs:** Selecting 200 rows shows identical count to 100 rows.

### Pitfall 3: Multiple `?category=` params not read as list
**What goes wrong:** Backend receives only the last `category=` param when multiple are sent.
**Why it happens:** FastAPI requires `Query(default=[])` with `List[str]` type hint to collect repeated params.
**How to avoid:** Change `category: str | None = None` to `categories: list[str] = Query(default=[])` in the route. Apply same for `city`.
**Warning signs:** Selecting two categories shows results for only one.

### Pitfall 4: Sorting on NULL columns (location_city, match_confidence)
**What goes wrong:** NULLs sort inconsistently across databases, or cause errors.
**Why it happens:** SQLite and PostgreSQL handle NULL ordering differently by default.
**How to avoid:** Use `.nullslast()` for descending, `.nullsfirst()` for ascending:
```python
if sort_dir == 'desc':
    stmt = stmt.order_by(sa.nullslast(sort_col.desc()))
else:
    stmt = stmt.order_by(sa.nullsfirst(sort_col.asc()))
```
**Warning signs:** NULL-city events jump between first/last position when sorting by city.

### Pitfall 5: Sorting on JSON `categories` column
**What goes wrong:** Sorting by categories on a JSON column may not produce useful alphabetical order since it sorts the JSON representation.
**Why it happens:** `CanonicalEvent.categories` is `sa.JSON`, not a plain string.
**How to avoid:** Cast to string for sorting: `sa.cast(CanonicalEvent.categories, sa.String)`. This gives lexicographic ordering of the JSON array, which is "good enough" for UI sorting.
**Warning signs:** Category sort produces unexpected ordering.

### Pitfall 6: Chip selector not applying immediately
**What goes wrong:** User adds a chip but the list doesn't refetch until they click "Search".
**Why it happens:** The current SearchFilters uses a form submit pattern (manual `handleSubmit`).
**How to avoid:** Chips should apply immediately on selection (call `onFiltersChange` directly when a chip is added or removed), bypassing the form submit. The text input (title/q) and date fields can still use form submit. This is a UX split: chip changes are immediate, text search requires Enter/button.
**Warning signs:** Users wonder why selecting a category chip doesn't update the list.

### Pitfall 7: Page resets when changing page size
**What goes wrong:** User is on page 5 with 25 rows, switches to 100 rows — page 5 may now be out of range.
**Why it happens:** Page number not reset when size changes.
**How to avoid:** Always reset to page 1 when page size changes. The `onSizeChange` handler must call `setSearchParams(filtersToParams(filters, 1))` after updating size.

## Code Examples

### Backend: New Distinct-Value Endpoints
```python
# In src/event_dedup/api/routes/canonical_events.py

@router.get("/categories", response_model=list[str])
async def list_distinct_categories(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return all distinct category values across canonical events."""
    # categories is a JSON array column — unnest via JSON functions
    # For SQLite compatibility: fetch all non-null categories, flatten in Python
    stmt = sa.select(CanonicalEvent.categories).where(
        CanonicalEvent.categories.is_not(None)
    )
    result = await db.execute(stmt)
    all_cats: set[str] = set()
    for (cats,) in result:
        if isinstance(cats, list):
            all_cats.update(cats)
    return sorted(all_cats)


@router.get("/cities", response_model=list[str])
async def list_distinct_cities(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return all distinct city values across canonical events."""
    stmt = (
        sa.select(CanonicalEvent.location_city)
        .where(CanonicalEvent.location_city.is_not(None))
        .distinct()
        .order_by(CanonicalEvent.location_city)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result]
```

### Backend: Updated list_canonical_events with Sort + Multi-Filter + Size
```python
@router.get("", response_model=PaginatedResponse[CanonicalEventSummary])
async def list_canonical_events(
    db: AsyncSession = Depends(get_db),
    q: str | None = None,
    city: list[str] = Query(default=[]),
    date_from: dt.date | None = None,
    date_to: dt.date | None = None,
    category: list[str] = Query(default=[]),
    sort_by: str = Query(default="title"),
    sort_dir: str = Query(default="asc"),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=25, ge=1, le=10000),
) -> PaginatedResponse[CanonicalEventSummary]:
    stmt = sa.select(CanonicalEvent)

    if q:
        stmt = stmt.where(CanonicalEvent.title.ilike(f"%{q}%"))
    if city:
        # OR across cities: match any selected city
        stmt = stmt.where(
            sa.or_(*[CanonicalEvent.location_city.ilike(f"%{c}%") for c in city])
        )
    if date_from:
        stmt = stmt.where(CanonicalEvent.first_date >= date_from)
    if date_to:
        stmt = stmt.where(CanonicalEvent.last_date <= date_to)
    if category:
        # AND across categories: event must have ALL selected categories
        for cat in category:
            stmt = stmt.where(
                sa.cast(CanonicalEvent.categories, sa.String).ilike(f"%{cat}%")
            )

    # Sorting
    sort_col_map = {
        "title": CanonicalEvent.title,
        "city": CanonicalEvent.location_city,
        "date": CanonicalEvent.first_date,
        "categories": sa.cast(CanonicalEvent.categories, sa.String),
        "source_count": CanonicalEvent.source_count,
        "confidence": CanonicalEvent.match_confidence,
        "review": CanonicalEvent.needs_review,
    }
    sort_col = sort_col_map.get(sort_by, CanonicalEvent.title)
    if sort_dir == "desc":
        stmt = stmt.order_by(sa.nullslast(sort_col.desc()))
    else:
        stmt = stmt.order_by(sa.nullsfirst(sort_col.asc()))

    # Count total
    count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginate
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    events = result.scalars().all()

    items = [CanonicalEventSummary.model_validate(e) for e in events]
    pages = math.ceil(total / size) if total > 0 else 1

    return PaginatedResponse(items=items, total=total, page=page, size=size, pages=pages)
```

### Frontend: Extended EventFilters Type
```typescript
// types/index.ts — update EventFilters
export type SortColumn = 'title' | 'city' | 'date' | 'categories' | 'source_count' | 'confidence' | 'review';
export type SortDir = 'asc' | 'desc';

export interface EventFilters {
  q?: string;
  cities?: string[];     // was: city?: string
  categories?: string[]; // was: category?: string
  date_from?: string;
  date_to?: string;
  sort_by?: SortColumn;
  sort_dir?: SortDir;
}
```

### Frontend: Fetching Distinct Values
```typescript
// api/client.ts additions
export async function fetchDistinctCategories(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/canonical-events/categories`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}

export async function fetchDistinctCities(): Promise<string[]> {
  const res = await fetch(`${API_BASE}/canonical-events/cities`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
```

```typescript
// hooks/useCanonicalEvents.ts additions
export function useDistinctCategories() {
  return useQuery({
    queryKey: ['distinct-categories'],
    queryFn: fetchDistinctCategories,
    staleTime: 300_000, // 5 minutes — changes only when new events are ingested
  });
}

export function useDistinctCities() {
  return useQuery({
    queryKey: ['distinct-cities'],
    queryFn: fetchDistinctCities,
    staleTime: 300_000,
  });
}
```

### Frontend: Updated fetchCanonicalEvents
```typescript
// api/client.ts — update fetchCanonicalEvents signature
export async function fetchCanonicalEvents(
  filters: EventFilters,
  page: number = 1,
  size: number = 25,
): Promise<PaginatedResponse<CanonicalEventSummary>> {
  const params = new URLSearchParams();
  params.set('page', String(page));
  params.set('size', String(size));
  if (filters.q) params.set('q', filters.q);
  filters.cities?.forEach(c => params.append('city', c));
  filters.categories?.forEach(c => params.append('category', c));
  if (filters.date_from) params.set('date_from', filters.date_from);
  if (filters.date_to) params.set('date_to', filters.date_to);
  if (filters.sort_by) params.set('sort_by', filters.sort_by);
  if (filters.sort_dir) params.set('sort_dir', filters.sort_dir);

  const res = await fetch(`${API_BASE}/canonical-events?${params}`);
  if (!res.ok) throw new Error(`API error: ${res.status}`);
  return res.json();
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| City filter: free text input | City filter: chip selector from distinct DB values | Phase 11 | Operators pick valid cities, no typos |
| Category filter: free text input | Category filter: chip selector from distinct DB values | Phase 11 | Operators pick valid categories |
| Sort: always by title ascending | Sort: user-selectable column + direction | Phase 11 | Operators can find events by date, city, confidence |
| Page size: hardcoded 20 rows | Page size: 25/50/100/200/ALL | Phase 11 | Operators can view more events at once |

**Breaking changes from old filter API:**
- `city` and `category` params change from single-value to multi-value (repeated params). The old single `?city=Freiburg` still works because `list[str]` in FastAPI accepts a single value.
- Default page size changes from 20 to 25. This is cosmetic — no data is lost.

## Open Questions

1. **Multi-category filter semantics: AND vs OR**
   - What we know: The current single-category filter uses ILIKE substring match on the JSON array as a string. If two categories are selected, should events match ALL selected categories, or ANY?
   - What's unclear: The requirement doesn't specify.
   - Recommendation: Use AND (event must have ALL selected categories). This is more useful for narrowing results. Easy to change if operators prefer OR. Implemented as chained `.where()` clauses.

2. **"ALL" page size implementation**
   - What we know: FastAPI needs a numeric value. The dataset is small enough (~2000 events max) to return all in one request.
   - What's unclear: Best sentinel value.
   - Recommendation: Use `size=10000` as the "ALL" sentinel. Display as "ALL" in the UI dropdown (`value=0` → send `size=10000` to API). This avoids backend changes for a special "no limit" mode.

3. **Route ordering: /categories before /{event_id}**
   - What we know: FastAPI resolves routes in order. `/categories` must be registered BEFORE `/{event_id}` in the router to avoid being matched as `event_id="categories"`.
   - What's unclear: Whether this causes test regressions.
   - Recommendation: Register `/categories` and `/cities` at the top of the router, before the `/{event_id}` route. Verify existing test `test_detail_canonical_event` still passes.

## Validation Architecture

> Skipped — `workflow.nyquist_validation` is not present in config.json (workflow only has research, plan_check, verifier).

## Sources

### Primary (HIGH confidence)
- `/Users/svenkarl/workspaces/event-deduplication/frontend/src/components/EventList.tsx` — Full current event list implementation
- `/Users/svenkarl/workspaces/event-deduplication/frontend/src/components/SearchFilters.tsx` — Current filter UI (text inputs)
- `/Users/svenkarl/workspaces/event-deduplication/frontend/src/components/Pagination.tsx` — Current pagination (no size control)
- `/Users/svenkarl/workspaces/event-deduplication/frontend/src/hooks/useCanonicalEvents.ts` — TanStack Query hook (size param exists but unused in UI)
- `/Users/svenkarl/workspaces/event-deduplication/frontend/src/api/client.ts` — API client (fetchCanonicalEvents sends size)
- `/Users/svenkarl/workspaces/event-deduplication/frontend/src/types/index.ts` — EventFilters type (single city/category strings)
- `/Users/svenkarl/workspaces/event-deduplication/src/event_dedup/api/routes/canonical_events.py` — Backend route (le=100 cap, single-value filters, title-only sort)
- `/Users/svenkarl/workspaces/event-deduplication/src/event_dedup/models/canonical_event.py` — CanonicalEvent model (all sortable columns confirmed)
- `/Users/svenkarl/workspaces/event-deduplication/frontend/package.json` — Confirmed: no component library in dependencies
- Domain knowledge: ~16 distinct categories, ~65 distinct cities from eventdata JSON files
- `/Users/svenkarl/workspaces/event-deduplication/tests/conftest.py` and `test_api.py` — Test patterns for backend route tests

### Secondary (MEDIUM confidence)
- FastAPI `Query(default=[])` with `list[str]` for repeated params — standard FastAPI pattern for multi-value query parameters
- SQLAlchemy `nullslast()` / `nullsfirst()` — documented in SQLAlchemy 2.0 ordering API
- `onBlur` + `setTimeout(150ms)` for dropdown — widely used pattern for click-before-blur issue in React

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH — All libraries confirmed in package.json and pyproject.toml
- Current component structure: HIGH — Read all relevant source files directly
- Backend changes needed: HIGH — Confirmed by reading canonical_events.py source
- Chip selector pattern: HIGH — Standard React controlled component pattern, no library needed
- Sorting implementation: HIGH — SQLAlchemy column attribute map is straightforward
- Pitfalls: HIGH — Identified from direct code analysis (le=100 cap, onBlur issue, route ordering)

**Research date:** 2026-02-28
**Valid until:** 2026-03-28 (stable internal project, no external dependency changes expected)
