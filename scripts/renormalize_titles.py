"""Re-normalize all source event titles with synonym replacement.

Run after adding or updating synonym groups to update existing
title_normalized and short_description_normalized values in the database.

Usage:
    uv run python scripts/renormalize_titles.py [--db DATABASE_URL]
"""

import argparse
import asyncio
import os
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from event_dedup.models.base import Base
from event_dedup.models.source_event import SourceEvent
from event_dedup.preprocessing.normalizer import normalize_text
from event_dedup.preprocessing.prefix_stripper import load_prefix_config, strip_prefixes
from event_dedup.preprocessing.synonyms import load_synonym_map

BATCH_SIZE = 100


async def renormalize(db_url: str) -> None:
    """Re-normalize all source event titles."""
    engine = create_async_engine(db_url)

    # Load configs
    config_dir = Path(__file__).resolve().parents[1] / "src" / "event_dedup" / "config"
    prefix_config = load_prefix_config(config_dir / "prefixes.yaml")
    synonym_map = load_synonym_map(config_dir / "synonyms.yaml")

    print(f"Loaded {len(synonym_map)} synonym mappings")

    session_factory = async_sessionmaker(engine, expire_on_commit=False)

    async with session_factory() as session:
        result = await session.execute(select(SourceEvent))
        events = result.scalars().all()
        print(f"Found {len(events)} source events to re-normalize")

        updated = 0
        for i, evt in enumerate(events):
            stripped_title = strip_prefixes(evt.title, prefix_config)
            new_title_norm = normalize_text(stripped_title, synonym_map=synonym_map)
            new_desc_norm = (
                normalize_text(evt.short_description, synonym_map=synonym_map)
                if evt.short_description
                else None
            )

            changed = False
            if evt.title_normalized != new_title_norm:
                evt.title_normalized = new_title_norm
                changed = True
            if evt.short_description_normalized != new_desc_norm:
                evt.short_description_normalized = new_desc_norm
                changed = True

            if changed:
                updated += 1

            # Commit in batches
            if (i + 1) % BATCH_SIZE == 0:
                await session.commit()
                print(f"  Processed {i + 1}/{len(events)} ({updated} updated)")

        await session.commit()
        print(f"Done. Updated {updated}/{len(events)} events.")

    await engine.dispose()


def main() -> None:
    parser = argparse.ArgumentParser(description="Re-normalize source event titles with synonyms")
    parser.add_argument(
        "--db",
        default=os.environ.get("DATABASE_URL", "sqlite+aiosqlite:///events.db"),
        help="Database URL (default: DATABASE_URL env var or sqlite+aiosqlite:///events.db)",
    )
    args = parser.parse_args()
    asyncio.run(renormalize(args.db))


if __name__ == "__main__":
    main()
