"""Candidate pair generator using blocking keys.

Generates event pairs that share at least one blocking key, including
same-source pairs.  Pairs use canonical ordering (id_a < id_b) and are
deduplicated across blocking groups.  Also computes blocking reduction
statistics to verify that blocking is practical at scale.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class CandidatePairStats:
    """Statistics about candidate pair generation.

    Attributes:
        total_events: Number of input events.
        total_possible_pairs: All unique pairs without blocking (naive).
        blocked_pairs: Pairs after blocking.
        reduction_pct: Percentage of pairs eliminated by blocking.
    """

    total_events: int
    total_possible_pairs: int  # All unique pairs without blocking (naive).
    blocked_pairs: int
    reduction_pct: float


def generate_candidate_pairs(
    events: list[dict],
) -> tuple[list[tuple[str, str]], CandidatePairStats]:
    """Generate candidate pairs using blocking keys.

    Both cross-source and same-source pairs are generated.  Pairs use
    canonical ordering (``id_a < id_b``) and are deduplicated across
    blocking groups so that events sharing multiple blocking keys produce
    each pair only once.

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

    # Generate all pairs within each block (including same-source)
    seen: set[tuple[str, str]] = set()
    for block_events in blocking_index.values():
        for i in range(len(block_events)):
            for j in range(i + 1, len(block_events)):
                evt_a, evt_b = block_events[i], block_events[j]
                # Canonical ordering: smaller id first
                pair = tuple(sorted([evt_a["id"], evt_b["id"]]))
                seen.add(pair)  # type: ignore[arg-type]

    pairs: list[tuple[str, str]] = sorted(seen)  # type: ignore[arg-type]

    n = len(events)
    total_possible = n * (n - 1) // 2
    blocked = len(pairs)
    reduction = (1 - blocked / total_possible) * 100 if total_possible > 0 else 0.0

    return pairs, CandidatePairStats(
        total_events=n,
        total_possible_pairs=total_possible,
        blocked_pairs=blocked,
        reduction_pct=reduction,
    )
