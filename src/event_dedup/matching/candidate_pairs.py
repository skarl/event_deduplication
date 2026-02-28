"""Candidate pair generator using blocking keys.

Generates cross-source event pairs that share at least one blocking key.
Pairs use canonical ordering (id_a < id_b) and are deduplicated across
blocking groups.  Also computes blocking reduction statistics to verify
that blocking is practical at scale.
"""

from __future__ import annotations

from collections import Counter
from dataclasses import dataclass


@dataclass
class CandidatePairStats:
    """Statistics about candidate pair generation.

    Attributes:
        total_events: Number of input events.
        total_possible_pairs: Cross-source pairs without blocking (naive).
        blocked_pairs: Cross-source pairs after blocking.
        reduction_pct: Percentage of pairs eliminated by blocking.
    """

    total_events: int
    total_possible_pairs: int
    blocked_pairs: int
    reduction_pct: float


def generate_candidate_pairs(
    events: list[dict],
) -> tuple[list[tuple[str, str]], CandidatePairStats]:
    """Generate candidate pairs using blocking keys.

    Only cross-source pairs are generated (same ``source_code`` events are
    never compared).  Pairs use canonical ordering (``id_a < id_b``) and
    are deduplicated across blocking groups so that events sharing
    multiple blocking keys produce each pair only once.

    Args:
        events: List of event dicts.  Each must have ``"id"``,
            ``"source_code"``, and ``"blocking_keys"`` fields.

    Returns:
        A tuple of (sorted pair list, blocking statistics).
    """
    # Build blocking index: blocking_key -> list of events that share it
    blocking_index: dict[str, list[dict]] = {}
    for event in events:
        for key in event.get("blocking_keys") or []:
            blocking_index.setdefault(key, []).append(event)

    # Generate cross-source pairs within each block
    seen: set[tuple[str, str]] = set()
    for block_events in blocking_index.values():
        for i in range(len(block_events)):
            for j in range(i + 1, len(block_events)):
                evt_a, evt_b = block_events[i], block_events[j]
                # Skip same-source pairs
                if evt_a["source_code"] == evt_b["source_code"]:
                    continue
                # Canonical ordering: smaller id first
                pair = tuple(sorted([evt_a["id"], evt_b["id"]]))
                seen.add(pair)  # type: ignore[arg-type]

    pairs: list[tuple[str, str]] = sorted(seen)  # type: ignore[arg-type]

    total_possible = _count_cross_source_pairs(events)
    blocked = len(pairs)
    reduction = (1 - blocked / total_possible) * 100 if total_possible > 0 else 0.0

    return pairs, CandidatePairStats(
        total_events=len(events),
        total_possible_pairs=total_possible,
        blocked_pairs=blocked,
        reduction_pct=reduction,
    )


def _count_cross_source_pairs(events: list[dict]) -> int:
    """Count total cross-source pairs without blocking (naive baseline).

    Groups events by ``source_code`` and computes the product of sizes
    for every pair of distinct source groups.
    """
    source_counts = Counter(e["source_code"] for e in events)
    sizes = list(source_counts.values())
    total = 0
    for i in range(len(sizes)):
        for j in range(i + 1, len(sizes)):
            total += sizes[i] * sizes[j]
    return total
