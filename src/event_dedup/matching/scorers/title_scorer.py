"""Title similarity scorer using RapidFuzz.

Uses ``token_sort_ratio`` as the primary signal and blends in
``token_set_ratio`` only when the primary score falls in an
ambiguous range.
"""

from __future__ import annotations

from rapidfuzz import fuzz

from event_dedup.matching.config import TitleConfig


def title_score(
    event_a: dict, event_b: dict, config: TitleConfig | None = None
) -> float:
    """Compute title similarity between two events.

    Returns a float in [0, 1]:
    - 0.0 if either title is missing or empty
    - Blended token_sort_ratio / token_set_ratio otherwise
    """
    if config is None:
        config = TitleConfig()

    title_a = (event_a.get("title") or "").strip()
    title_b = (event_b.get("title") or "").strip()

    if not title_a or not title_b:
        return 0.0

    primary = fuzz.token_sort_ratio(title_a, title_b) / 100.0

    # Only blend with token_set_ratio in the ambiguous range
    if config.blend_lower <= primary <= config.blend_upper:
        secondary = fuzz.token_set_ratio(title_a, title_b) / 100.0
        return config.primary_weight * primary + config.secondary_weight * secondary

    return primary
