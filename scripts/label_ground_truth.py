"""Run the ground truth labeling session.

Sets up a persistent SQLite database, ingests all event files,
generates candidate pairs, and launches the interactive labeling CLI.

Usage:
    uv run python scripts/label_ground_truth.py [--db ground_truth.db] [--min-sim 0.30] [--auto-threshold 0.85]

The database persists between runs — you can quit and resume later.
Already-labeled pairs are automatically skipped.
"""

import argparse
import asyncio
import sys
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from event_dedup.ground_truth.candidate_generator import generate_candidates
from event_dedup.ground_truth.labeling_tool import get_labeling_stats, run_labeling_session
from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.models.base import Base


async def setup_db(db_path: str) -> async_sessionmaker[AsyncSession]:
    """Create engine and tables, return session factory."""
    engine = create_async_engine(f"sqlite+aiosqlite:///{db_path}")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)


async def ingest_all_events(
    session_factory: async_sessionmaker[AsyncSession],
    eventdata_dir: Path,
) -> int:
    """Ingest all JSON files. Skips already-processed files."""
    processor = FileProcessor(session_factory, dead_letter_dir=Path("/tmp/dead_letters"))
    files = sorted(eventdata_dir.glob("*.json"))

    total = 0
    new = 0
    for f in files:
        result = await processor.process_file(f)
        if result.status == "completed":
            new += result.event_count
        total += result.event_count if result.status == "completed" else 0

    return new


async def main() -> None:
    parser = argparse.ArgumentParser(description="Ground truth labeling tool")
    parser.add_argument("--db", default="ground_truth.db", help="SQLite database path")
    parser.add_argument("--min-sim", type=float, default=0.30, help="Min title similarity for candidates")
    parser.add_argument("--auto-threshold", type=float, default=0.85, help="Auto-suggest 'same' above this")
    parser.add_argument("--eventdata", default="eventdata", help="Event data directory")
    parser.add_argument("--stats-only", action="store_true", help="Show stats and exit")
    args = parser.parse_args()

    db_path = args.db
    is_new = not Path(db_path).exists()

    print(f"\n  Database: {db_path} ({'new' if is_new else 'existing'})")
    session_factory = await setup_db(db_path)

    # Ingest events
    eventdata_dir = Path(args.eventdata)
    print(f"  Ingesting events from {eventdata_dir}...")
    new_events = await ingest_all_events(session_factory, eventdata_dir)
    if new_events > 0:
        print(f"  Ingested {new_events} new events")
    else:
        print("  All events already ingested")

    # Show current stats
    async with session_factory() as session:
        stats = await get_labeling_stats(session)
    print(f"\n  Current labels: {stats['total_labeled']} total "
          f"({stats['same_count']} same, {stats['different_count']} different)")

    if args.stats_only:
        return

    # Generate candidates
    print(f"  Generating candidates (min_sim={args.min_sim})...")
    async with session_factory() as session:
        candidates = await generate_candidates(session, min_title_sim=args.min_sim)

    high = sum(1 for c in candidates if c.title_sim >= args.auto_threshold)
    mid = sum(1 for c in candidates if args.min_sim <= c.title_sim < args.auto_threshold)
    low = sum(1 for c in candidates if c.title_sim < args.min_sim)

    print(f"  Candidates: {len(candidates)} total")
    print(f"    High (>={args.auto_threshold}, auto-suggest): {high}")
    print(f"    Medium ({args.min_sim}-{args.auto_threshold}):          {mid}")
    print(f"    Low (hard negatives):              {low}")
    print()
    print("  Controls: s=same, d=different, k=skip, q=quit, n=add note")
    print("  High-similarity pairs: just press Enter to accept 'same'")
    print("  Progress is saved after each label — quit anytime with 'q'")
    print()

    # Run labeling session
    async with session_factory() as session:
        labeled = await run_labeling_session(
            session, candidates, auto_threshold=args.auto_threshold
        )

    # Final stats
    async with session_factory() as session:
        stats = await get_labeling_stats(session)
    print(f"\n  Final: {stats['total_labeled']} labeled "
          f"({stats['same_count']} same, {stats['different_count']} different)")


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\n  Interrupted. Progress was saved.")
        sys.exit(0)
