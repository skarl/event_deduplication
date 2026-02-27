"""Auto-generate a ground truth dataset using conservative multi-signal heuristics.

Ingests all event files, generates candidate pairs, auto-labels them
using strict heuristics, and persists results to a SQLite database.
No manual intervention required.

Usage:
    uv run python scripts/generate_ground_truth.py [--db ground_truth.db] [--eventdata eventdata]

The database is reusable by the evaluation harness.
"""

import argparse
import asyncio
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import selectinload

from event_dedup.ground_truth.auto_labeler import auto_label_candidates
from event_dedup.ground_truth.candidate_generator import generate_candidates_from_events
from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.models.base import Base
from event_dedup.models.ground_truth import GroundTruthPair
from event_dedup.models.source_event import SourceEvent


async def setup_db(db_path: str) -> async_sessionmaker[AsyncSession]:
    """Create engine and tables, return session factory."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def ingest_events(
    session_factory: async_sessionmaker[AsyncSession],
    eventdata_dir: Path,
) -> int:
    """Ingest all JSON files. Returns count of newly ingested events."""
    processor = FileProcessor(session_factory, dead_letter_dir=Path("/tmp/dead_letters"))
    new_count = 0
    for f in sorted(eventdata_dir.glob("*.json")):
        result = await processor.process_file(f)
        if result.status == "completed":
            new_count += result.event_count
    return new_count


async def load_events(session: AsyncSession) -> list[dict]:
    """Load all events as dicts for the candidate generator and auto-labeler."""
    result = await session.execute(
        select(SourceEvent).options(selectinload(SourceEvent.dates))
    )
    events = result.scalars().all()
    return [
        {
            "id": e.id,
            "title": e.title,
            "title_normalized": e.title_normalized,
            "short_description": e.short_description,
            "short_description_normalized": e.short_description_normalized,
            "location_city": e.location_city,
            "location_city_normalized": e.location_city_normalized,
            "location_name": e.location_name,
            "location_name_normalized": e.location_name_normalized,
            "source_code": e.source_code,
            "blocking_keys": e.blocking_keys,
            "geo_latitude": e.geo_latitude,
            "geo_longitude": e.geo_longitude,
            "geo_confidence": e.geo_confidence,
        }
        for e in events
    ]


async def main() -> None:
    parser = argparse.ArgumentParser(description="Auto-generate ground truth dataset")
    parser.add_argument("--db", default="ground_truth.db", help="SQLite database path")
    parser.add_argument("--eventdata", default="eventdata", help="Event data directory")
    parser.add_argument("--min-sim", type=float, default=0.0, help="Min title similarity for candidates (0.0 = all pairs)")
    args = parser.parse_args()

    db_path = args.db
    is_new = not Path(db_path).exists()
    print(f"\n{'='*60}")
    print(f"  Ground Truth Auto-Generator")
    print(f"{'='*60}")
    print(f"\n  Database: {db_path} ({'new' if is_new else 'existing'})")

    session_factory = await setup_db(db_path)

    # Step 1: Ingest events
    eventdata_dir = Path(args.eventdata)
    print(f"  Ingesting events from {eventdata_dir}...")
    new_count = await ingest_events(session_factory, eventdata_dir)
    if new_count > 0:
        print(f"  Ingested {new_count} new events")
    else:
        print("  All events already ingested")

    # Step 2: Load events and generate candidates
    print(f"  Generating candidate pairs...")
    async with session_factory() as session:
        event_dicts = await load_events(session)
    print(f"  Loaded {len(event_dicts)} events")

    candidates = generate_candidates_from_events(
        event_dicts, min_title_sim=args.min_sim, hard_negative_ratio=1.0
    )
    print(f"  Generated {len(candidates)} candidate pairs")

    # Step 3: Auto-label
    events_by_id = {e["id"]: e for e in event_dicts}
    result = auto_label_candidates(candidates, events_by_id)

    print(f"\n  {'─'*50}")
    print(f"  Auto-labeling results:")
    print(f"  {'─'*50}")
    print(f"  Total labeled:      {result.total}")
    print(f"    Same:             {result.same_count}")
    print(f"    Different:        {result.different_count}")
    print(f"  Skipped (ambiguous): {result.skipped_ambiguous}")

    # Breakdown by confidence
    high_same = sum(1 for d in result.labeled if d.label == "same" and d.confidence == "high")
    med_same = sum(1 for d in result.labeled if d.label == "same" and d.confidence == "medium")
    high_diff = sum(1 for d in result.labeled if d.label == "different" and d.confidence == "high")
    print(f"\n  Confidence breakdown:")
    print(f"    Same (high):      {high_same}  (title>=0.90 + same city)")
    print(f"    Same (medium):    {med_same}  (title>=0.70 + same city + desc>=0.80)")
    print(f"    Different (high): {high_diff}  (title<0.40 or diff city+title<0.70)")

    # Step 4: Persist to database
    print(f"\n  Persisting to database...")
    async with session_factory() as session:
        # Check for existing labels to avoid duplicates
        existing = await session.execute(select(GroundTruthPair))
        existing_pairs = {
            (r.event_id_a, r.event_id_b) for r in existing.scalars().all()
        }

        new_labels = 0
        for decision in result.labeled:
            pair_key = (decision.event_id_a, decision.event_id_b)
            if pair_key in existing_pairs:
                continue

            pair = GroundTruthPair(
                event_id_a=decision.event_id_a,
                event_id_b=decision.event_id_b,
                label=decision.label,
                title_similarity=decision.title_sim,
                notes=f"auto:{decision.confidence}:{decision.reason}",
            )
            session.add(pair)
            new_labels += 1

        await session.commit()
        print(f"  Persisted {new_labels} new labels ({result.total - new_labels} already existed)")

    # Step 5: Show sample of labeled pairs
    print(f"\n  {'─'*50}")
    print(f"  Sample 'same' pairs (top 5):")
    print(f"  {'─'*50}")
    same_decisions = [d for d in result.labeled if d.label == "same"]
    for d in same_decisions[:5]:
        a = events_by_id[d.event_id_a]
        b = events_by_id[d.event_id_b]
        print(f"  [{d.confidence}] sim={d.title_sim:.2f} | {a['source_code']}/{b['source_code']}")
        print(f"    A: {a['title'][:60]}")
        print(f"    B: {b['title'][:60]}")

    print(f"\n  Sample 'different' pairs (5 from middle):")
    print(f"  {'─'*50}")
    diff_decisions = [d for d in result.labeled if d.label == "different"]
    mid = len(diff_decisions) // 2
    for d in diff_decisions[mid : mid + 5]:
        a = events_by_id.get(d.event_id_a, {})
        b = events_by_id.get(d.event_id_b, {})
        print(f"  [{d.confidence}] sim={d.title_sim:.2f} | {a.get('source_code', '?')}/{b.get('source_code', '?')}")
        print(f"    A: {a.get('title', '?')[:60]}")
        print(f"    B: {b.get('title', '?')[:60]}")

    print(f"\n{'='*60}")
    print(f"  Ground truth ready: {result.total} labeled pairs")
    print(f"  Database: {db_path}")
    print(f"{'='*60}\n")


if __name__ == "__main__":
    asyncio.run(main())
