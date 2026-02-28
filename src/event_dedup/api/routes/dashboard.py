"""API routes for the batch processing dashboard."""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from fastapi import APIRouter, Depends, Query
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.api.deps import get_db
from event_dedup.api.schemas import (
    CanonicalStats,
    DashboardStats,
    FileProcessingStats,
    MatchDistribution,
    ProcessingHistoryEntry,
)
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.file_ingestion import FileIngestion
from event_dedup.models.match_decision import MatchDecision

router = APIRouter(prefix="/api/dashboard", tags=["dashboard"])


@router.get("/stats", response_model=DashboardStats)
async def dashboard_stats(
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> DashboardStats:
    """Aggregate file processing stats, match distribution, and canonical summary."""
    cutoff = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(days=days)

    # 1. File processing stats
    file_stmt = sa.select(
        sa.func.count(FileIngestion.id).label("total_files"),
        sa.func.coalesce(sa.func.sum(FileIngestion.event_count), 0).label("total_events"),
        sa.func.count(sa.case((FileIngestion.status == "completed", 1))).label("completed"),
        sa.func.count(sa.case((FileIngestion.status == "error", 1))).label("errors"),
    ).where(FileIngestion.ingested_at >= cutoff)
    file_result = await db.execute(file_stmt)
    file_row = file_result.one()

    files = FileProcessingStats(
        total_files=file_row.total_files,
        total_events=int(file_row.total_events),
        completed=file_row.completed,
        errors=file_row.errors,
    )

    # 2. Match decision distribution (entire dataset, no time filter)
    match_stmt = sa.select(
        MatchDecision.decision,
        sa.func.count(MatchDecision.id).label("cnt"),
    ).group_by(MatchDecision.decision)
    match_result = await db.execute(match_stmt)
    match_rows = match_result.all()

    match_dist = {"match": 0, "no_match": 0, "ambiguous": 0}
    for row in match_rows:
        if row.decision in match_dist:
            match_dist[row.decision] = row.cnt

    matches = MatchDistribution(**match_dist)

    # 3. Canonical stats
    canonical_stmt = sa.select(
        sa.func.count(CanonicalEvent.id).label("total"),
        sa.func.count(sa.case((CanonicalEvent.needs_review == True, 1))).label("needs_review"),  # noqa: E712
        sa.func.avg(CanonicalEvent.match_confidence).label("avg_confidence"),
    )
    canonical_result = await db.execute(canonical_stmt)
    canonical_row = canonical_result.one()

    canonicals = CanonicalStats(
        total=canonical_row.total,
        needs_review=canonical_row.needs_review,
        avg_confidence=round(canonical_row.avg_confidence, 4) if canonical_row.avg_confidence else None,
    )

    return DashboardStats(files=files, matches=matches, canonicals=canonicals)


@router.get("/processing-history", response_model=list[ProcessingHistoryEntry])
async def processing_history(
    db: AsyncSession = Depends(get_db),
    days: int = Query(default=30, ge=1, le=365),
) -> list[ProcessingHistoryEntry]:
    """Daily time-series data for processing trends."""
    cutoff = dt.datetime.now(dt.UTC).replace(tzinfo=None) - dt.timedelta(days=days)

    date_col = sa.func.date(FileIngestion.ingested_at).label("date")
    stmt = (
        sa.select(
            date_col,
            sa.func.count(FileIngestion.id).label("files_processed"),
            sa.func.coalesce(sa.func.sum(FileIngestion.event_count), 0).label("events_ingested"),
            sa.func.count(sa.case((FileIngestion.status == "error", 1))).label("errors"),
        )
        .where(FileIngestion.ingested_at >= cutoff)
        .group_by(date_col)
        .order_by(date_col)
    )

    result = await db.execute(stmt)
    rows = result.all()

    return [
        ProcessingHistoryEntry(
            date=str(row.date),
            files_processed=row.files_processed,
            events_ingested=int(row.events_ingested),
            errors=row.errors,
        )
        for row in rows
    ]
