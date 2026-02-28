"""API routes for manual review operations."""

from __future__ import annotations

import math

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.api.deps import get_db
from event_dedup.api.schemas import (
    AuditLogEntry,
    CanonicalEventSummary,
    DismissRequest,
    MergeRequest,
    MergeResponse,
    PaginatedResponse,
    SplitRequest,
    SplitResponse,
)
from event_dedup.models.audit_log import AuditLog
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.review.operations import merge_canonical_events, split_source_from_canonical

router = APIRouter(prefix="/api/review", tags=["review"])

# Separate router for audit-log (lives at /api/audit-log, not /api/review/audit-log)
audit_router = APIRouter(prefix="/api", tags=["audit"])


@router.post("/split", response_model=SplitResponse)
async def split_source(
    request: SplitRequest,
    db: AsyncSession = Depends(get_db),
) -> SplitResponse:
    """Detach a source event from its canonical and assign to another or create new."""
    result = await split_source_from_canonical(
        session=db,
        canonical_event_id=request.canonical_event_id,
        source_event_id=request.source_event_id,
        target_canonical_id=request.target_canonical_id,
        operator=request.operator,
    )
    return SplitResponse(**result)


@router.post("/merge", response_model=MergeResponse)
async def merge_canonicals(
    request: MergeRequest,
    db: AsyncSession = Depends(get_db),
) -> MergeResponse:
    """Merge two canonical events into one (donor is deleted)."""
    result = await merge_canonical_events(
        session=db,
        source_canonical_id=request.source_canonical_id,
        target_canonical_id=request.target_canonical_id,
        operator=request.operator,
    )
    return MergeResponse(**result)


@router.get("/queue", response_model=PaginatedResponse[CanonicalEventSummary])
async def review_queue(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    min_sources: int = Query(default=1, ge=1),
) -> PaginatedResponse[CanonicalEventSummary]:
    """List canonical events needing review, sorted by uncertainty."""
    stmt = (
        sa.select(CanonicalEvent)
        .where(
            sa.or_(
                CanonicalEvent.needs_review == True,  # noqa: E712
                sa.and_(
                    CanonicalEvent.match_confidence.isnot(None),
                    CanonicalEvent.match_confidence < 0.8,
                    CanonicalEvent.source_count > 1,
                ),
            )
        )
        .where(CanonicalEvent.source_count >= min_sources)
        .order_by(
            CanonicalEvent.needs_review.desc(),
            sa.func.coalesce(CanonicalEvent.match_confidence, 0.0).asc(),
        )
    )

    # Count total
    count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginate
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    events = result.scalars().all()

    items = [CanonicalEventSummary.model_validate(e) for e in events]
    pages = math.ceil(total / size) if total > 0 else 1

    return PaginatedResponse(
        items=items, total=total, page=page, size=size, pages=pages
    )


@router.post("/queue/{event_id}/dismiss")
async def dismiss_from_queue(
    event_id: int,
    request: DismissRequest,
    db: AsyncSession = Depends(get_db),
) -> dict:
    """Clear needs_review flag and log the action."""
    stmt = sa.select(CanonicalEvent).where(CanonicalEvent.id == event_id)
    result = await db.execute(stmt)
    canonical = result.scalar_one_or_none()

    if canonical is None:
        raise HTTPException(status_code=404, detail="Canonical event not found")

    canonical.needs_review = False
    # Mark as manually verified so it no longer appears in low-confidence filter
    old_confidence = canonical.match_confidence
    if canonical.match_confidence is not None and canonical.match_confidence < 0.8:
        canonical.match_confidence = 1.0

    audit = AuditLog(
        action_type="review_dismiss",
        canonical_event_id=event_id,
        operator=request.operator,
        details={
            "reason": request.reason,
            "original_confidence": old_confidence,
        },
    )
    db.add(audit)
    await db.commit()

    return {"status": "dismissed"}


@audit_router.get("/audit-log", response_model=PaginatedResponse[AuditLogEntry])
async def list_audit_log(
    db: AsyncSession = Depends(get_db),
    page: int = Query(default=1, ge=1),
    size: int = Query(default=20, ge=1, le=100),
    canonical_event_id: int | None = None,
    action_type: str | None = None,
) -> PaginatedResponse[AuditLogEntry]:
    """Paginated audit log entries, filterable by canonical_event_id and action_type."""
    stmt = sa.select(AuditLog)

    if canonical_event_id is not None:
        stmt = stmt.where(AuditLog.canonical_event_id == canonical_event_id)
    if action_type is not None:
        stmt = stmt.where(AuditLog.action_type == action_type)

    stmt = stmt.order_by(AuditLog.created_at.desc())

    # Count total
    count_stmt = sa.select(sa.func.count()).select_from(stmt.subquery())
    total = (await db.execute(count_stmt)).scalar_one()

    # Paginate
    stmt = stmt.offset((page - 1) * size).limit(size)
    result = await db.execute(stmt)
    entries = result.scalars().all()

    items = [
        AuditLogEntry(
            id=entry.id,
            action_type=entry.action_type,
            canonical_event_id=entry.canonical_event_id,
            source_event_id=entry.source_event_id,
            operator=entry.operator,
            details=entry.details,
            created_at=entry.created_at.isoformat() if entry.created_at else "",
        )
        for entry in entries
    ]
    pages = math.ceil(total / size) if total > 0 else 1

    return PaginatedResponse(
        items=items, total=total, page=page, size=size, pages=pages
    )
