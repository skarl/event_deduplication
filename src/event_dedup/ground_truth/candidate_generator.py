"""Generate candidate pairs for ground truth labeling.

Uses blocking keys (date+city and date+geo_grid) to group events,
then generates cross-source pairs with title similarity scores
for human labeling.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from rapidfuzz.fuzz import token_sort_ratio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from event_dedup.models.source_event import SourceEvent


@dataclass
class CandidatePair:
    """A candidate pair of events for labeling."""

    event_id_a: str
    event_id_b: str
    title_sim: float
    event_a_title: str
    event_b_title: str
    event_a_city: str | None
    event_b_city: str | None
    event_a_source: str
    event_b_source: str


def generate_candidates_from_events(
    events: list[dict],
    min_title_sim: float = 0.30,
    hard_negative_ratio: float = 0.20,
    seed: int = 42,
) -> list[CandidatePair]:
    """Generate candidate pairs from a list of event dicts using blocking keys.

    This is a pure function for easy testing. Events are grouped by blocking
    keys, then cross-source pairs are generated within each group.

    Args:
        events: List of dicts with keys: id, title_normalized,
            location_city, location_city_normalized, source_code,
            title, blocking_keys.
        min_title_sim: Minimum title similarity to include as a
            positive candidate (0.0 - 1.0).
        hard_negative_ratio: Fraction of below-threshold pairs to
            include as hard negatives.
        seed: Random seed for reproducible hard negative sampling.

    Returns:
        List of CandidatePair sorted by title_sim descending.
    """
    # Step 1: Build blocking index
    blocking_index: dict[str, list[dict]] = {}
    for event in events:
        for key in event.get("blocking_keys") or []:
            blocking_index.setdefault(key, []).append(event)

    # Step 2: Generate cross-source pairs from blocking groups
    # Use a set of canonical (id_a, id_b) tuples to deduplicate
    seen_pairs: set[tuple[str, str]] = set()
    positive_candidates: list[CandidatePair] = []
    below_threshold: list[CandidatePair] = []

    for _key, group in blocking_index.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                evt_a = group[i]
                evt_b = group[j]

                # Only cross-source pairs
                if evt_a["source_code"] == evt_b["source_code"]:
                    continue

                # Canonical ordering
                id_a, id_b = evt_a["id"], evt_b["id"]
                if id_a > id_b:
                    id_a, id_b = id_b, id_a
                    evt_a, evt_b = evt_b, evt_a

                pair_key = (id_a, id_b)
                if pair_key in seen_pairs:
                    continue
                seen_pairs.add(pair_key)

                # Compute title similarity
                title_norm_a = evt_a.get("title_normalized") or ""
                title_norm_b = evt_b.get("title_normalized") or ""
                title_sim = token_sort_ratio(title_norm_a, title_norm_b) / 100.0

                candidate = CandidatePair(
                    event_id_a=id_a,
                    event_id_b=id_b,
                    title_sim=title_sim,
                    event_a_title=evt_a.get("title") or "",
                    event_b_title=evt_b.get("title") or "",
                    event_a_city=evt_a.get("location_city"),
                    event_b_city=evt_b.get("location_city"),
                    event_a_source=evt_a["source_code"],
                    event_b_source=evt_b["source_code"],
                )

                if title_sim >= min_title_sim:
                    positive_candidates.append(candidate)
                else:
                    below_threshold.append(candidate)

    # Step 3: Sample hard negatives
    rng = random.Random(seed)
    if below_threshold and hard_negative_ratio > 0:
        hard_negative_count = max(1, int(len(below_threshold) * hard_negative_ratio))
        hard_negatives = rng.sample(below_threshold, min(hard_negative_count, len(below_threshold)))
    else:
        hard_negatives = []

    # Step 4: Combine and sort by title_sim descending
    all_candidates = positive_candidates + hard_negatives
    all_candidates.sort(key=lambda c: c.title_sim, reverse=True)

    return all_candidates


async def generate_candidates(
    session: AsyncSession,
    min_title_sim: float = 0.30,
) -> list[CandidatePair]:
    """Generate candidate pairs from the database.

    Queries all SourceEvents and delegates to the pure function
    generate_candidates_from_events.

    Args:
        session: Async SQLAlchemy session.
        min_title_sim: Minimum title similarity threshold.

    Returns:
        List of CandidatePair sorted by title_sim descending.
    """
    result = await session.execute(
        select(SourceEvent).options(selectinload(SourceEvent.dates))
    )
    source_events = result.scalars().all()

    events = [
        {
            "id": evt.id,
            "title": evt.title,
            "title_normalized": evt.title_normalized,
            "location_city": evt.location_city,
            "location_city_normalized": evt.location_city_normalized,
            "source_code": evt.source_code,
            "blocking_keys": evt.blocking_keys,
        }
        for evt in source_events
    ]

    return generate_candidates_from_events(events, min_title_sim=min_title_sim)
