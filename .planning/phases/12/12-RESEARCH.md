# Phase 12: Export Function - Research

**Researched:** 2026-02-28
**Domain:** Data export, JSON serialization, ZIP archive generation, CLI tooling
**Confidence:** HIGH

## Summary

Phase 12 implements an export function that transforms canonical events from the database back into the input JSON format. The export must work through three channels: a shared core module, a FastAPI API endpoint (with ZIP packaging), and a CLI command (writing files to disk). The primary technical challenge is the field mapping between the `CanonicalEvent` database model and the input `EventData` schema, along with file chunking (200 events per file) and conditional ZIP vs. single-JSON responses.

The project already has all necessary dependencies installed -- `FastAPI` for the API endpoint, `sqlalchemy[asyncio]` for database queries, Python stdlib `json`/`zipfile`/`io` for serialization and archiving. No new libraries are needed. The existing `json_loader.py` defines the exact input format (`EventFileData` with `events`, `rejected`, `metadata`), and the `CanonicalEvent` model plus `CanonicalEventDetail` schema define all source fields. The transformation is straightforward field mapping with some nesting (flat `location_*`/`geo_*` fields to nested `location.geo` structure).

**Primary recommendation:** Build a pure `export_service.py` module that handles querying, transformation, and chunking. The API route and CLI command are thin wrappers around this shared service.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EXP-01 | API endpoint to export canonical events as JSON in input format (`{"events": [...], "metadata": {...}}`) | Field mapping from `CanonicalEvent` model to input `EventData` schema; see Architecture Pattern 1 for transformation logic |
| EXP-02 | Export date filter -- optional `created_after` and/or `modified_after` datetime parameters | `CanonicalEvent` has `created_at` and `updated_at` DateTime columns; simple SQLAlchemy `where` clauses |
| EXP-03 | Export output split into files of max 200 events, named `export_{timestamp}_part_{N}.json` | Python list chunking + `json.dumps` per chunk; see Architecture Pattern 2 |
| EXP-04 | Frontend export UI -- page/dialog with date filter and download button. ZIP if multiple files, single JSON if <=200 events | `StreamingResponse` with `application/zip` or `application/json` content type; frontend uses `fetch` + `Blob` for download |
| EXP-05 | CLI export command with same date filters and file splitting, writes to output directory | New `cli` package with `__main__.py` entry point; async CLI using `asyncio.run` + session factory pattern from worker |
</phase_requirements>

## Standard Stack

### Core
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| FastAPI | >=0.115 | API endpoint with `StreamingResponse` | Already in project; native streaming response support |
| SQLAlchemy[asyncio] | >=2.0 | Async DB queries with filters | Already in project; all DB access uses this |
| Python stdlib `json` | 3.12+ | JSON serialization | No external dep needed for JSON output |
| Python stdlib `zipfile` | 3.12+ | ZIP archive creation in memory | No external dep needed; `ZipFile` writes to `BytesIO` |
| Python stdlib `io.BytesIO` | 3.12+ | In-memory buffer for ZIP stream | Standard approach for streaming ZIP responses |
| Python stdlib `argparse` | 3.12+ | CLI argument parsing | Lightweight, no extra dep; project has no CLI framework yet |

### Supporting
| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| `date-fns` | ^4.1.0 | Date formatting in frontend datetime pickers | Already in frontend; use for ISO string formatting |
| `structlog` | >=24.0 | Logging in CLI command | Already in project; consistent logging |

### Alternatives Considered
| Instead of | Could Use | Tradeoff |
|------------|-----------|----------|
| `argparse` | `click` or `typer` | Would add a dependency; argparse is sufficient for 3 options |
| `zipfile` in memory | `zipstream-ng` | Streaming ZIP for very large exports; not needed for 200-event chunks |
| `StreamingResponse` | `FileResponse` with temp file | Temp file cleanup complexity; in-memory is fine for event data sizes |

**Installation:**
No new packages required. All dependencies already present.

## Architecture Patterns

### Recommended Project Structure
```
src/event_dedup/
├── export/                   # NEW - export module
│   ├── __init__.py
│   └── service.py            # Core export logic (query, transform, chunk)
├── api/
│   └── routes/
│       └── export.py         # NEW - POST /api/export endpoint
├── cli/                      # NEW - CLI package
│   ├── __init__.py
│   └── __main__.py           # Entry point: python -m event_dedup.cli export
```

### Pattern 1: Canonical-to-Input Transformation
**What:** Map flat `CanonicalEvent` DB columns to the nested input JSON structure.
**When to use:** Core of the export service -- every exported event goes through this.

The input format (from `json_loader.py`) has this structure per event:
```python
{
    "title": str,
    "short_description": str | None,
    "description": str | None,
    "highlights": list[str] | None,
    "event_dates": [{"date": str, "start_time": str | None, "end_time": str | None, "end_date": str | None}],
    "location": {
        "name": str | None,
        "city": str | None,
        "district": str | None,
        "street": str | None,
        "street_no": str | None,  # NOTE: canonical model does NOT have street_no
        "zipcode": str | None,
        "geo": {
            "longitude": float | None,
            "latitude": float | None,
            "confidence": float | None,
        }
    },
    "categories": list[str] | None,
    "is_family_event": bool | None,
    "is_child_focused": bool | None,
    "admission_free": bool | None,
}
```

The `CanonicalEvent` model stores:
- `title`, `short_description`, `description`, `highlights` -- direct copy
- `location_name`, `location_city`, `location_district`, `location_street`, `location_zipcode` -- nest into `location` object
- `geo_latitude`, `geo_longitude`, `geo_confidence` -- nest into `location.geo` object
- `dates` -- JSON column, already in `[{"date": ..., "start_time": ...}]` format; rename to `event_dates`
- `categories`, `is_family_event`, `is_child_focused`, `admission_free` -- direct copy

**Key mapping details:**
- `CanonicalEvent.dates` is stored as JSON list of `{"date", "start_time", "end_time", "end_date"}` dicts -- this maps directly to `event_dates` in the input format
- The `location` nesting must be constructed from flat `location_*` and `geo_*` fields
- Input format has `source_type` and `registration_*` fields that do NOT exist on `CanonicalEvent` -- omit these from export (they are source-level, not canonical-level)
- Input format has `id`, `confidence_score`, `_batch_index`, `_extracted_at` -- these are source-level metadata, omit from export

### Pattern 2: File Chunking with Consistent Naming
**What:** Split list of events into chunks of 200, serialize each chunk as a complete JSON file with metadata.
**When to use:** Both API and CLI use the same chunking logic.

```python
import json
from datetime import datetime, timezone

def chunk_events(events: list[dict], chunk_size: int = 200) -> list[tuple[str, str]]:
    """Split events into named chunks.

    Returns list of (filename, json_content) tuples.
    """
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
    chunks = []

    for i in range(0, len(events), chunk_size):
        part = i // chunk_size + 1
        chunk = events[i : i + chunk_size]
        filename = f"export_{timestamp}_part_{part}.json"
        content = json.dumps({
            "events": chunk,
            "metadata": {
                "exportedAt": datetime.now(timezone.utc).isoformat(),
                "eventCount": len(chunk),
                "part": part,
                "totalParts": -1,  # filled after all chunks known
            }
        }, ensure_ascii=False, indent=2)
        chunks.append((filename, content))

    return chunks
```

### Pattern 3: Conditional ZIP vs. JSON API Response
**What:** Return single JSON if <=200 events, ZIP archive if >200 events.
**When to use:** API endpoint response logic.

```python
from fastapi.responses import StreamingResponse
import zipfile
import io

async def export_endpoint(...):
    events = await query_and_transform(...)
    chunks = chunk_events(events)

    if len(chunks) == 1:
        # Single file -- return JSON directly
        filename, content = chunks[0]
        return StreamingResponse(
            iter([content.encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )
    else:
        # Multiple files -- ZIP archive
        buffer = io.BytesIO()
        with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
            for filename, content in chunks:
                zf.writestr(filename, content)
        buffer.seek(0)

        zip_filename = f"export_{timestamp}.zip"
        return StreamingResponse(
            buffer,
            media_type="application/zip",
            headers={"Content-Disposition": f'attachment; filename="{zip_filename}"'},
        )
```

### Pattern 4: Async CLI with Database Access
**What:** CLI command that reuses the async session infrastructure from the worker.
**When to use:** The `uv run python -m event_dedup.cli export` command.

The worker module (`worker/__main__.py`) already demonstrates the pattern:
1. `get_settings()` for database URL
2. `get_session_factory()` for async sessions
3. `asyncio.run(main())` as entry point

The CLI should follow the same pattern but with `argparse` for options:
```python
# src/event_dedup/cli/__main__.py
import argparse
import asyncio

async def main():
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command")

    export_parser = subparsers.add_parser("export")
    export_parser.add_argument("--created-after", type=str, default=None)
    export_parser.add_argument("--modified-after", type=str, default=None)
    export_parser.add_argument("--output-dir", type=str, default="./export")

    args = parser.parse_args()
    # ... call export service, write files to disk

asyncio.run(main())
```

### Pattern 5: Frontend Download via Blob
**What:** Trigger file download from API response in the browser.
**When to use:** Frontend export page/dialog.

```typescript
async function downloadExport(params: ExportParams) {
    const res = await fetch('/api/export', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(params),
    });

    const contentType = res.headers.get('Content-Type') || '';
    const disposition = res.headers.get('Content-Disposition') || '';
    const filename = disposition.match(/filename="(.+)"/)?.[1] || 'export.json';

    const blob = await res.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = filename;
    a.click();
    URL.revokeObjectURL(url);
}
```

### Anti-Patterns to Avoid
- **Loading all events into memory at once without pagination:** For very large datasets, this could cause memory issues. However, given the project handles ~2000 events/week, full load is acceptable. Add a note in code for future optimization if needed.
- **Hardcoding the chunk size:** Make 200 a constant or parameter, not a magic number scattered through code.
- **Using temp files for the API ZIP response:** In-memory `BytesIO` is cleaner and avoids temp file cleanup.
- **Coupling export logic to API framework:** The core export service should be framework-agnostic (pure async functions), with API/CLI as thin wrappers.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| ZIP archive creation | Custom byte-level ZIP handling | `zipfile.ZipFile` with `BytesIO` | ZIP format has CRC, compression, headers -- stdlib handles it correctly |
| JSON serialization | Manual string concatenation | `json.dumps` with `ensure_ascii=False, indent=2` | Correct Unicode handling, consistent formatting |
| Date/time parsing | Manual string parsing | `datetime.fromisoformat()` | Handles ISO 8601 variants correctly |
| File download in browser | Custom XHR/blob handling | `fetch` + `Blob` + `URL.createObjectURL` | Standard browser API pattern |
| Datetime picker in React | Custom date input component | HTML native `<input type="datetime-local">` | Simple, no extra dependency, sufficient for this use case |

**Key insight:** This phase's complexity is in the field mapping and plumbing, not in any algorithmic challenge. Every individual piece (JSON serialization, ZIP creation, streaming responses, CLI argument parsing) is well-solved by stdlib/existing deps.

## Common Pitfalls

### Pitfall 1: Dates JSON Field Format Mismatch
**What goes wrong:** The `CanonicalEvent.dates` JSON column stores date dicts with keys `date`, `start_time`, `end_time`, `end_date`. The input format uses `event_dates` as the key name. If you forget to rename the key, the output won't match the input format.
**Why it happens:** The canonical model was designed for internal use, not for round-tripping.
**How to avoid:** Explicitly map `dates` -> `event_dates` in the transformation function. Write a test that validates the output against the `EventFileData` Pydantic model from `json_loader.py`.
**Warning signs:** Output JSON has `"dates"` instead of `"event_dates"`.

### Pitfall 2: Missing Fields in Export vs. Input
**What goes wrong:** The input format has fields that don't exist on `CanonicalEvent` (`source_type`, `registration_required`, `registration_contact`, `confidence_score`, `id`, `_batch_index`, `_extracted_at`). Including them as null or trying to access them causes errors or confusion.
**Why it happens:** Canonical events are synthesized from multiple sources -- source-level fields don't map 1:1.
**How to avoid:** Only export fields that exist on `CanonicalEvent`. The output will be a valid subset of the input format. Document which fields are omitted and why.
**Warning signs:** KeyError on source-level fields, or null-heavy output.

### Pitfall 3: Timezone-Naive Datetime Comparisons
**What goes wrong:** `created_at` and `updated_at` on `CanonicalEvent` use `server_default=sa.text("CURRENT_TIMESTAMP")` which is timezone-naive in SQLite (test DB) but may be timezone-aware in PostgreSQL. Filter comparison with timezone-aware user input fails.
**Why it happens:** SQLite and PostgreSQL handle timestamps differently.
**How to avoid:** Accept datetime strings as ISO format, parse to naive datetime, and compare without timezone. Document that all times are assumed UTC.
**Warning signs:** Filters returning no results or wrong results in tests vs. production.

### Pitfall 4: Content-Disposition Header for ZIP Download
**What goes wrong:** Browser doesn't trigger download or uses wrong filename.
**Why it happens:** Missing or malformed `Content-Disposition: attachment; filename="..."` header.
**How to avoid:** Always set the header on streaming responses. Test in the browser, not just with curl.
**Warning signs:** Browser opens JSON in tab instead of downloading, or ZIP file has no extension.

### Pitfall 5: Empty Export Edge Case
**What goes wrong:** Export with date filters that match zero events returns an error or empty ZIP.
**Why it happens:** No events match the filter criteria.
**How to avoid:** Return a single JSON file with `{"events": [], "metadata": {...}}` when no events match. Never return an empty ZIP.
**Warning signs:** HTTP 500 or empty response body.

## Code Examples

### Canonical-to-Input Event Transformation
```python
def canonical_to_input_format(canonical: CanonicalEvent) -> dict:
    """Transform a CanonicalEvent ORM object to input JSON format."""
    event: dict = {
        "title": canonical.title,
    }

    # Optional text fields
    if canonical.short_description:
        event["short_description"] = canonical.short_description
    if canonical.description:
        event["description"] = canonical.description
    if canonical.highlights:
        event["highlights"] = canonical.highlights

    # Dates: rename "dates" -> "event_dates"
    event["event_dates"] = canonical.dates or []

    # Location: reconstruct nested structure
    location: dict = {}
    if canonical.location_name:
        location["name"] = canonical.location_name
    if canonical.location_city:
        location["city"] = canonical.location_city
    if canonical.location_district:
        location["district"] = canonical.location_district
    if canonical.location_street:
        location["street"] = canonical.location_street
    if canonical.location_zipcode:
        location["zipcode"] = canonical.location_zipcode

    # Geo: nested within location
    if canonical.geo_latitude is not None and canonical.geo_longitude is not None:
        geo = {
            "longitude": canonical.geo_longitude,
            "latitude": canonical.geo_latitude,
        }
        if canonical.geo_confidence is not None:
            geo["confidence"] = canonical.geo_confidence
        location["geo"] = geo

    if location:
        event["location"] = location

    # Categories and flags
    if canonical.categories:
        event["categories"] = canonical.categories
    if canonical.is_family_event is not None:
        event["is_family_event"] = canonical.is_family_event
    if canonical.is_child_focused is not None:
        event["is_child_focused"] = canonical.is_child_focused
    if canonical.admission_free is not None:
        event["admission_free"] = canonical.admission_free

    return event
```

### Database Query with Date Filters
```python
import sqlalchemy as sa
from datetime import datetime

async def query_canonical_events(
    session: AsyncSession,
    created_after: datetime | None = None,
    modified_after: datetime | None = None,
) -> list[CanonicalEvent]:
    stmt = sa.select(CanonicalEvent)

    if created_after:
        stmt = stmt.where(CanonicalEvent.created_at >= created_after)
    if modified_after:
        stmt = stmt.where(CanonicalEvent.updated_at >= modified_after)

    stmt = stmt.order_by(CanonicalEvent.id)
    result = await session.execute(stmt)
    return list(result.scalars().all())
```

### Export Metadata Structure
```python
{
    "events": [...],
    "metadata": {
        "exportedAt": "2026-02-28T16:00:00Z",
        "eventCount": 150,
        "part": 1,
        "totalParts": 1,
        "filters": {
            "created_after": "2026-02-28T16:00:00" or null,
            "modified_after": null,
        }
    }
}
```

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| `FileResponse` with temp files | `StreamingResponse` with `BytesIO` | FastAPI >=0.95 | No temp file cleanup needed |
| `datetime.strptime` for parsing | `datetime.fromisoformat` | Python 3.11+ | Simpler, handles more ISO formats |
| `<input type="date">` + separate time | `<input type="datetime-local">` | HTML5 / evergreen browsers | Single picker for date+time, native support |

**Deprecated/outdated:**
- None relevant -- all patterns used are current and stable.

## Open Questions

1. **Should exported events include an `id` field?**
   - What we know: Input events have `id` (e.g., `"pdf-9d58bea1-1-6"`) but these are source-level IDs. Canonical events have integer auto-increment IDs.
   - What's unclear: Should the export include the canonical event's integer ID for traceability, or omit it entirely since the purpose is to match the input format?
   - Recommendation: Omit the ID to stay true to the "input format" requirement. The metadata timestamp and part number provide sufficient traceability.

2. **Should the `metadata` block mirror the input `metadata` structure?**
   - What we know: Input files have `metadata` with `processedAt`, `sourceKey`, `totalExtracted`, etc. These are ingestion-specific.
   - What's unclear: Should export metadata use the same field names or export-specific ones?
   - Recommendation: Use export-specific metadata (`exportedAt`, `eventCount`, `part`, `totalParts`, `filters`) since this is an export operation, not a re-ingestion.

3. **POST vs. GET for the export endpoint?**
   - What we know: Roadmap specifies `POST /api/export`. GET would be more RESTful for a read-only operation.
   - What's unclear: Whether the choice was deliberate (to allow body parameters) or arbitrary.
   - Recommendation: Use POST as specified. It avoids URL length limits for filter parameters and matches the roadmap.

## Sources

### Primary (HIGH confidence)
- Codebase analysis: `src/event_dedup/models/canonical_event.py` -- CanonicalEvent model with all field definitions
- Codebase analysis: `src/event_dedup/ingestion/json_loader.py` -- EventData/EventFileData models defining the input format
- Codebase analysis: `src/event_dedup/api/app.py` + `routes/canonical_events.py` -- existing API patterns
- Codebase analysis: `src/event_dedup/worker/__main__.py` -- async CLI entry point pattern
- Codebase analysis: `eventdata/bwb_11.02.2026_*.json` -- real input file examples
- Codebase analysis: `src/event_dedup/canonical/synthesizer.py` -- canonical event field structure

### Secondary (MEDIUM confidence)
- Python stdlib docs: `zipfile.ZipFile`, `io.BytesIO` -- well-known stable APIs
- FastAPI docs: `StreamingResponse` -- verified from training data, stable API since FastAPI 0.60+

### Tertiary (LOW confidence)
- None

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - All libraries already in the project; no new dependencies needed
- Architecture: HIGH - All patterns verified against existing codebase conventions; field mapping is deterministic from model inspection
- Pitfalls: HIGH - Identified from direct codebase analysis (datetime handling, field mismatches); no speculation

**Research date:** 2026-02-28
**Valid until:** 2026-03-30 (stable -- no fast-moving dependencies)
