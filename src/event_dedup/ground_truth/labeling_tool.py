"""Interactive CLI tool for labeling candidate event pairs.

Presents candidate pairs side-by-side and accepts human labels
(same/different) to build a ground truth dataset for evaluation.
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.ground_truth.candidate_generator import CandidatePair
from event_dedup.models.ground_truth import GroundTruthPair
from event_dedup.models.source_event import SourceEvent


def _format_pair_display(
    idx: int,
    total: int,
    candidate: CandidatePair,
    event_a: SourceEvent | None,
    event_b: SourceEvent | None,
) -> str:
    """Format a candidate pair for terminal display.

    Args:
        idx: 1-based pair index.
        total: Total number of pairs.
        candidate: The candidate pair.
        event_a: Full SourceEvent for event A (may be None).
        event_b: Full SourceEvent for event B (may be None).

    Returns:
        Formatted string for terminal display.
    """
    lines = [
        "",
        "=" * 70,
        f"  Pair {idx}/{total}  |  Title similarity: {candidate.title_sim:.2f}",
        "=" * 70,
        "",
        f"  {'EVENT A':30s}  |  {'EVENT B':30s}",
        f"  {'Source: ' + candidate.event_a_source:30s}  |  {'Source: ' + candidate.event_b_source:30s}",
        "-" * 70,
    ]

    # Title
    title_a = candidate.event_a_title or "(no title)"
    title_b = candidate.event_b_title or "(no title)"
    lines.append(f"  Title: {title_a}")
    lines.append(f"  Title: {title_b}")
    lines.append("")

    # City
    city_a = candidate.event_a_city or "(no city)"
    city_b = candidate.event_b_city or "(no city)"
    lines.append(f"  City: {city_a:30s}  |  City: {city_b}")

    # Additional details from full events if available
    if event_a and event_b:
        desc_a = (event_a.short_description or "(none)")[:60]
        desc_b = (event_b.short_description or "(none)")[:60]
        lines.append(f"  Desc: {desc_a}")
        lines.append(f"  Desc: {desc_b}")
        lines.append("")

        loc_a = event_a.location_name or "(none)"
        loc_b = event_b.location_name or "(none)"
        lines.append(f"  Location: {loc_a}")
        lines.append(f"  Location: {loc_b}")

        type_a = event_a.source_type or "(none)"
        type_b = event_b.source_type or "(none)"
        lines.append(f"  Type: {type_a:30s}  |  Type: {type_b}")

    lines.append("")
    lines.append("-" * 70)

    return "\n".join(lines)


async def run_labeling_session(
    session: AsyncSession,
    candidates: list[CandidatePair],
    auto_threshold: float = 0.85,
) -> int:
    """Run an interactive labeling session.

    For each candidate pair, presents a side-by-side comparison and
    accepts a label from the user. Pre-suggests "same" for pairs with
    high title similarity.

    Args:
        session: Async SQLAlchemy session.
        candidates: List of candidate pairs to label.
        auto_threshold: Title similarity threshold above which
            "same" is pre-suggested.

    Returns:
        Number of pairs labeled in this session.
    """
    labeled_count = 0
    total = len(candidates)

    for idx, candidate in enumerate(candidates, 1):
        # Check if pair already labeled
        existing = await session.execute(
            select(GroundTruthPair).where(
                GroundTruthPair.event_id_a == candidate.event_id_a,
                GroundTruthPair.event_id_b == candidate.event_id_b,
            )
        )
        if existing.scalar_one_or_none() is not None:
            continue

        # Load full events for display
        result_a = await session.execute(
            select(SourceEvent).where(SourceEvent.id == candidate.event_id_a)
        )
        event_a = result_a.scalar_one_or_none()

        result_b = await session.execute(
            select(SourceEvent).where(SourceEvent.id == candidate.event_id_b)
        )
        event_b = result_b.scalar_one_or_none()

        # Display pair
        display = _format_pair_display(idx, total, candidate, event_a, event_b)
        print(display)

        # Prompt with pre-suggestion for high similarity
        if candidate.title_sim >= auto_threshold:
            prompt = "  Label [s=same (suggested), d=different, k=skip, q=quit, n=note]: "
        else:
            prompt = "  Label [s=same, d=different, k=skip, q=quit, n=note]: "

        notes = None

        while True:
            user_input = input(prompt).strip().lower()

            if user_input == "n":
                notes = input("  Enter note: ").strip()
                continue

            if user_input == "q":
                print(f"\n  Session ended. Labeled {labeled_count} pairs.")
                return labeled_count

            if user_input == "k":
                break

            if user_input in ("s", ""):
                label = "same"
            elif user_input == "d":
                label = "different"
            else:
                print("  Invalid input. Use s/d/k/q/n.")
                continue

            # Create record
            pair = GroundTruthPair(
                event_id_a=candidate.event_id_a,
                event_id_b=candidate.event_id_b,
                label=label,
                title_similarity=candidate.title_sim,
                notes=notes,
            )
            session.add(pair)
            await session.commit()
            labeled_count += 1
            print(f"  -> Labeled as '{label}'")
            break

    print(f"\n  Session complete. Labeled {labeled_count} pairs total.")
    return labeled_count


async def get_labeling_stats(session: AsyncSession) -> dict:
    """Get statistics about labeled ground truth pairs.

    Args:
        session: Async SQLAlchemy session.

    Returns:
        Dict with total_labeled, same_count, different_count.
    """
    total_result = await session.execute(
        select(func.count(GroundTruthPair.id))
    )
    total_labeled = total_result.scalar() or 0

    same_result = await session.execute(
        select(func.count(GroundTruthPair.id)).where(GroundTruthPair.label == "same")
    )
    same_count = same_result.scalar() or 0

    different_result = await session.execute(
        select(func.count(GroundTruthPair.id)).where(GroundTruthPair.label == "different")
    )
    different_count = different_result.scalar() or 0

    return {
        "total_labeled": total_labeled,
        "same_count": same_count,
        "different_count": different_count,
    }
