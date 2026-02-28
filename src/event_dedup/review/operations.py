"""Review operations: split and merge canonical events."""

from __future__ import annotations

import datetime as dt

import sqlalchemy as sa
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from event_dedup.canonical.helpers import source_event_to_dict, update_canonical_from_dict
from event_dedup.canonical.synthesizer import synthesize_canonical
from event_dedup.models.audit_log import AuditLog
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.canonical_event_source import CanonicalEventSource
from event_dedup.models.source_event import SourceEvent


async def split_source_from_canonical(
    session: AsyncSession,
    canonical_event_id: int,
    source_event_id: str,
    target_canonical_id: int | None = None,
    operator: str = "anonymous",
) -> dict:
    """Detach a source event from its canonical and optionally assign to another.

    If target_canonical_id is None, a new canonical event is created from the
    detached source. If target_canonical_id is given, the source is linked to
    that existing canonical instead.

    All work is done within a single transaction.

    Returns:
        Dict with original_canonical_id, new_canonical_id (if created),
        target_canonical_id (if assigned), original_deleted (bool).
    """
    async with session.begin():
        # 1. Find and delete the link
        link_stmt = sa.select(CanonicalEventSource).where(
            CanonicalEventSource.canonical_event_id == canonical_event_id,
            CanonicalEventSource.source_event_id == source_event_id,
        )
        link_result = await session.execute(link_stmt)
        link = link_result.scalar_one_or_none()
        if link is None:
            raise HTTPException(
                status_code=404,
                detail=f"Source {source_event_id} not linked to canonical {canonical_event_id}",
            )
        await session.delete(link)
        await session.flush()

        # 2. Query remaining links for the original canonical
        remaining_stmt = (
            sa.select(CanonicalEventSource)
            .where(CanonicalEventSource.canonical_event_id == canonical_event_id)
            .options(
                selectinload(CanonicalEventSource.source_event).selectinload(SourceEvent.dates)
            )
        )
        remaining_result = await session.execute(remaining_stmt)
        remaining_links = remaining_result.scalars().all()

        original_deleted = False

        # 3. If zero remaining links: delete the original canonical
        if len(remaining_links) == 0:
            # Explicitly delete child rows first (SQLite CASCADE workaround)
            await session.execute(
                sa.delete(CanonicalEventSource).where(
                    CanonicalEventSource.canonical_event_id == canonical_event_id
                )
            )
            # Use SQL DELETE (not ORM session.delete) to avoid cascade conflicts
            await session.execute(
                sa.delete(CanonicalEvent).where(
                    CanonicalEvent.id == canonical_event_id
                )
            )
            original_deleted = True

        # 4. If 1+ remaining links: re-synthesize
        else:
            source_dicts = [source_event_to_dict(lnk.source_event) for lnk in remaining_links]
            synth = synthesize_canonical(source_dicts)
            original_canonical_stmt = sa.select(CanonicalEvent).where(
                CanonicalEvent.id == canonical_event_id
            )
            original_canonical_result = await session.execute(original_canonical_stmt)
            original_canonical = original_canonical_result.scalar_one()
            update_canonical_from_dict(original_canonical, synth)
            original_canonical.needs_review = False

        # 5. Handle the detached source event
        new_canonical_id = None
        result_target_id = None

        if target_canonical_id is not None:
            # Assign to existing canonical
            target_stmt = sa.select(CanonicalEvent).where(
                CanonicalEvent.id == target_canonical_id
            )
            target_result = await session.execute(target_stmt)
            target = target_result.scalar_one_or_none()
            if target is None:
                raise HTTPException(
                    status_code=404,
                    detail=f"Target canonical {target_canonical_id} not found",
                )

            # Check if link already exists (skip if so)
            existing_link_stmt = sa.select(CanonicalEventSource).where(
                CanonicalEventSource.canonical_event_id == target_canonical_id,
                CanonicalEventSource.source_event_id == source_event_id,
            )
            existing_link_result = await session.execute(existing_link_stmt)
            if existing_link_result.scalar_one_or_none() is None:
                new_link = CanonicalEventSource(
                    canonical_event_id=target_canonical_id,
                    source_event_id=source_event_id,
                )
                session.add(new_link)
                await session.flush()

            # Re-synthesize target from all its sources
            target_sources_stmt = (
                sa.select(CanonicalEventSource)
                .where(CanonicalEventSource.canonical_event_id == target_canonical_id)
                .options(
                    selectinload(CanonicalEventSource.source_event).selectinload(SourceEvent.dates)
                )
            )
            target_sources_result = await session.execute(target_sources_stmt)
            target_links = target_sources_result.scalars().all()
            target_dicts = [source_event_to_dict(lnk.source_event) for lnk in target_links]
            target_synth = synthesize_canonical(target_dicts)
            update_canonical_from_dict(target, target_synth)
            target.needs_review = False

            result_target_id = target_canonical_id

        else:
            # Create new canonical from the detached source
            source_stmt = (
                sa.select(SourceEvent)
                .where(SourceEvent.id == source_event_id)
                .options(selectinload(SourceEvent.dates))
            )
            source_result = await session.execute(source_stmt)
            source_event = source_result.scalar_one()

            source_dict = source_event_to_dict(source_event)
            synth = synthesize_canonical([source_dict])

            new_canonical = CanonicalEvent(
                title=synth["title"],
                short_description=synth.get("short_description"),
                description=synth.get("description"),
                highlights=synth.get("highlights"),
                location_name=synth.get("location_name"),
                location_city=synth.get("location_city"),
                location_district=synth.get("location_district"),
                location_street=synth.get("location_street"),
                location_zipcode=synth.get("location_zipcode"),
                geo_latitude=synth.get("geo_latitude"),
                geo_longitude=synth.get("geo_longitude"),
                geo_confidence=synth.get("geo_confidence"),
                dates=synth.get("dates"),
                first_date=dt.date.fromisoformat(synth["first_date"]) if synth.get("first_date") else None,
                last_date=dt.date.fromisoformat(synth["last_date"]) if synth.get("last_date") else None,
                categories=synth.get("categories"),
                is_family_event=synth.get("is_family_event"),
                is_child_focused=synth.get("is_child_focused"),
                admission_free=synth.get("admission_free"),
                field_provenance=synth.get("field_provenance"),
                source_count=synth.get("source_count", 1),
                match_confidence=None,
                needs_review=False,
            )
            session.add(new_canonical)
            await session.flush()

            new_link = CanonicalEventSource(
                canonical_event_id=new_canonical.id,
                source_event_id=source_event_id,
            )
            session.add(new_link)

            new_canonical_id = new_canonical.id

        # 6. Create AuditLog entry
        audit_details = {
            "target_canonical_id": result_target_id,
            "original_deleted": original_deleted,
        }
        if new_canonical_id is not None:
            audit_details["new_canonical_id"] = new_canonical_id

        audit = AuditLog(
            action_type="split",
            canonical_event_id=canonical_event_id if not original_deleted else new_canonical_id,
            source_event_id=source_event_id,
            operator=operator,
            details=audit_details,
        )
        session.add(audit)

    # 7. Return result
    return {
        "original_canonical_id": canonical_event_id,
        "new_canonical_id": new_canonical_id,
        "target_canonical_id": result_target_id,
        "original_deleted": original_deleted,
    }


async def merge_canonical_events(
    session: AsyncSession,
    source_canonical_id: int,
    target_canonical_id: int,
    operator: str = "anonymous",
) -> dict:
    """Merge two canonical events, keeping the target and deleting the source (donor).

    All source links from the donor are moved to the target. The target is
    re-synthesized from all combined sources. Duplicate source links are skipped.

    All work is done within a single transaction.

    Returns:
        Dict with surviving_canonical_id, deleted_canonical_id, new_source_count.
    """
    if source_canonical_id == target_canonical_id:
        raise HTTPException(
            status_code=400,
            detail="Cannot merge a canonical event with itself",
        )

    async with session.begin():
        # 1. Load both canonical events
        source_ce_stmt = sa.select(CanonicalEvent).where(
            CanonicalEvent.id == source_canonical_id
        )
        source_ce_result = await session.execute(source_ce_stmt)
        source_ce = source_ce_result.scalar_one_or_none()
        if source_ce is None:
            raise HTTPException(
                status_code=404,
                detail=f"Source canonical {source_canonical_id} not found",
            )

        target_ce_stmt = sa.select(CanonicalEvent).where(
            CanonicalEvent.id == target_canonical_id
        )
        target_ce_result = await session.execute(target_ce_stmt)
        target_ce = target_ce_result.scalar_one_or_none()
        if target_ce is None:
            raise HTTPException(
                status_code=404,
                detail=f"Target canonical {target_canonical_id} not found",
            )

        # 2. Get all links from donor
        donor_links_stmt = sa.select(CanonicalEventSource).where(
            CanonicalEventSource.canonical_event_id == source_canonical_id
        )
        donor_links_result = await session.execute(donor_links_stmt)
        donor_links = donor_links_result.scalars().all()

        # 3. Get existing source_event_ids on target (to detect duplicates)
        target_links_stmt = sa.select(CanonicalEventSource.source_event_id).where(
            CanonicalEventSource.canonical_event_id == target_canonical_id
        )
        target_links_result = await session.execute(target_links_stmt)
        existing_target_ids = {row[0] for row in target_links_result}

        # 4. Move links from donor to target (skip duplicates)
        sources_moved = 0
        for donor_link in donor_links:
            if donor_link.source_event_id not in existing_target_ids:
                new_link = CanonicalEventSource(
                    canonical_event_id=target_canonical_id,
                    source_event_id=donor_link.source_event_id,
                )
                session.add(new_link)
                sources_moved += 1
            # Delete the donor link
            await session.delete(donor_link)

        await session.flush()

        # 5. Delete the donor canonical (explicit child delete for SQLite)
        await session.execute(
            sa.delete(CanonicalEventSource).where(
                CanonicalEventSource.canonical_event_id == source_canonical_id
            )
        )
        await session.delete(source_ce)
        await session.flush()

        # 6. Re-synthesize target from all its sources
        target_sources_stmt = (
            sa.select(CanonicalEventSource)
            .where(CanonicalEventSource.canonical_event_id == target_canonical_id)
            .options(
                selectinload(CanonicalEventSource.source_event).selectinload(SourceEvent.dates)
            )
        )
        target_sources_result = await session.execute(target_sources_stmt)
        target_links_all = target_sources_result.scalars().all()
        target_dicts = [source_event_to_dict(lnk.source_event) for lnk in target_links_all]
        target_synth = synthesize_canonical(target_dicts)
        update_canonical_from_dict(target_ce, target_synth)
        target_ce.needs_review = False

        new_source_count = len(target_links_all)

        # 7. Create AuditLog entry
        audit = AuditLog(
            action_type="merge",
            canonical_event_id=target_canonical_id,
            operator=operator,
            details={
                "deleted_canonical_id": source_canonical_id,
                "sources_moved": sources_moved,
                "new_source_count": new_source_count,
            },
        )
        session.add(audit)

    # 8. Return result
    return {
        "surviving_canonical_id": target_canonical_id,
        "deleted_canonical_id": source_canonical_id,
        "new_source_count": new_source_count,
    }
