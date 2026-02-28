"""Export endpoint -- POST /api/export for downloading canonical events as JSON/ZIP."""

from __future__ import annotations

import io
import zipfile
from datetime import datetime, timezone

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.api.deps import get_db
from event_dedup.api.schemas import ExportRequest
from event_dedup.export.service import chunk_events, query_and_export

router = APIRouter(prefix="/api/export", tags=["export"])


@router.post("")
async def export_events(
    request: ExportRequest,
    db: AsyncSession = Depends(get_db),
) -> StreamingResponse:
    """Export canonical events as JSON (single file) or ZIP (multiple chunks).

    Returns ``application/json`` with a single file when <= 200 events, or
    ``application/zip`` containing multiple chunk files when > 200 events.
    """
    # Parse optional datetime filters
    created_after: datetime | None = None
    modified_after: datetime | None = None

    try:
        if request.created_after is not None:
            created_after = datetime.fromisoformat(request.created_after)
            # Assume UTC if naive
            if created_after.tzinfo is None:
                created_after = created_after.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid datetime format for created_after: {request.created_after!r}",
        )

    try:
        if request.modified_after is not None:
            modified_after = datetime.fromisoformat(request.modified_after)
            if modified_after.tzinfo is None:
                modified_after = modified_after.replace(tzinfo=timezone.utc)
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid datetime format for modified_after: {request.modified_after!r}",
        )

    # Query and transform
    events = await query_and_export(db, created_after=created_after, modified_after=modified_after)

    # Build filter metadata for chunk files
    filters = {
        "created_after": request.created_after,
        "modified_after": request.modified_after,
    }

    # Chunk events
    chunks = chunk_events(events, filters=filters)

    if len(chunks) == 1:
        # Single file -- return JSON directly
        filename, content = chunks[0]
        return StreamingResponse(
            iter([content.encode("utf-8")]),
            media_type="application/json",
            headers={"Content-Disposition": f'attachment; filename="{filename}"'},
        )

    # Multiple files -- ZIP archive
    timestamp = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H-%M")
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
