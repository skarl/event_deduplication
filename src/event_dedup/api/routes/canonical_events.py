"""REST API endpoints for canonical events."""

from __future__ import annotations

import datetime as dt
import math

import sqlalchemy as sa
from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from event_dedup.api.deps import get_db
from event_dedup.api.schemas import (
    CanonicalEventDetail,
    CanonicalEventSummary,
    MatchDecisionSchema,
    PaginatedResponse,
    SourceEventDetail,
)
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.canonical_event_source import CanonicalEventSource
from event_dedup.models.match_decision import MatchDecision
from event_dedup.models.source_event import SourceEvent

router = APIRouter(prefix="/api/canonical-events", tags=["canonical-events"])


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
    """List canonical events with search, filtering, and pagination."""
    stmt = sa.select(CanonicalEvent)

    if q:
        stmt = stmt.where(CanonicalEvent.title.ilike(f"%{q}%"))
    if city:
        # OR semantics: event must match ANY selected city (ilike for case-insensitive)
        stmt = stmt.where(
            sa.or_(*[CanonicalEvent.location_city.ilike(f"%{c}%") for c in city])
        )
    if date_from:
        stmt = stmt.where(CanonicalEvent.first_date >= date_from)
    if date_to:
        stmt = stmt.where(CanonicalEvent.last_date <= date_to)
    if category:
        # AND semantics: event must have ALL selected categories
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

    # Count total (after filters + order)
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


@router.get("/categories", response_model=list[str])
async def list_distinct_categories(
    db: AsyncSession = Depends(get_db),
) -> list[str]:
    """Return all distinct category values across all canonical events."""
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
    """Return all distinct city values across all canonical events."""
    stmt = (
        sa.select(CanonicalEvent.location_city)
        .where(CanonicalEvent.location_city.is_not(None))
        .distinct()
        .order_by(CanonicalEvent.location_city)
    )
    result = await db.execute(stmt)
    return [row[0] for row in result]


@router.get("/{event_id}", response_model=CanonicalEventDetail)
async def get_canonical_event(
    event_id: int,
    db: AsyncSession = Depends(get_db),
) -> CanonicalEventDetail:
    """Get canonical event detail with source events and match decisions."""
    stmt = (
        sa.select(CanonicalEvent)
        .where(CanonicalEvent.id == event_id)
        .options(
            selectinload(CanonicalEvent.sources)
            .selectinload(CanonicalEventSource.source_event)
            .selectinload(SourceEvent.dates)
        )
    )
    result = await db.execute(stmt)
    canonical = result.scalar_one_or_none()

    if canonical is None:
        raise HTTPException(status_code=404, detail="Canonical event not found")

    # Collect source event IDs
    source_ids = [s.source_event_id for s in canonical.sources]

    # Query match decisions for this source group
    match_decisions: list = []
    if len(source_ids) >= 2:
        md_stmt = sa.select(MatchDecision).where(
            MatchDecision.source_event_id_a.in_(source_ids),
            MatchDecision.source_event_id_b.in_(source_ids),
        )
        md_result = await db.execute(md_stmt)
        match_decisions = md_result.scalars().all()

    # Build response -- construct base fields from ORM, then add nested objects
    # We can't use model_validate directly because canonical.sources are
    # CanonicalEventSource objects, not SourceEventDetail objects.
    base_data = {
        c.key: getattr(canonical, c.key)
        for c in CanonicalEvent.__table__.columns
    }
    base_data["sources"] = [
        SourceEventDetail.model_validate(ces.source_event)
        for ces in canonical.sources
    ]
    base_data["match_decisions"] = [
        MatchDecisionSchema.model_validate(md) for md in match_decisions
    ]

    return CanonicalEventDetail.model_validate(base_data)
