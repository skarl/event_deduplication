"""Title similarity scorer using RapidFuzz.

Uses ``token_sort_ratio`` as the primary signal and blends in
``token_set_ratio`` only when the primary score falls in an
ambiguous range.  Titles are case-folded before comparison so
that ``"WOODWALKERS 2"`` matches ``"Woodwalkers 2"`` and
German ``ß``/``SS`` differences are handled correctly.
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

    When both events have different source types (artikel vs terminliste)
    and ``config.cross_source_type`` is set, uses the cross-source-type
    config for blend parameters.
    """
    if config is None:
        config = TitleConfig()

    title_a = (event_a.get("title") or "").strip()
    title_b = (event_b.get("title") or "").strip()

    if not title_a or not title_b:
        return 0.0

    # Case-fold for case-insensitive comparison (handles ß→ss etc.)
    title_a = title_a.casefold()
    title_b = title_b.casefold()

    # Determine effective config based on source types
    effective_config = config
    st_a = event_a.get("source_type", "")
    st_b = event_b.get("source_type", "")
    if (
        config.cross_source_type is not None
        and st_a != st_b
        and st_a in ("artikel", "terminliste")
        and st_b in ("artikel", "terminliste")
    ):
        effective_config = config.cross_source_type

    primary = fuzz.token_sort_ratio(title_a, title_b) / 100.0

    # Only blend with token_set_ratio in the ambiguous range
    if effective_config.blend_lower <= primary <= effective_config.blend_upper:
        secondary = fuzz.token_set_ratio(title_a, title_b) / 100.0
        return effective_config.primary_weight * primary + effective_config.secondary_weight * secondary

    return primary
