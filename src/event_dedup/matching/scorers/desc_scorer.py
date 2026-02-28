"""Description similarity scorer using RapidFuzz.

A simpler scorer than title -- uses ``token_sort_ratio`` directly
with graceful handling of missing descriptions.
"""

from __future__ import annotations

from rapidfuzz import fuzz


def description_score(event_a: dict, event_b: dict) -> float:
    """Compute description similarity between two events.

    Returns a float in [0, 1]:
    - 0.5 if both descriptions are missing (neutral)
    - 0.4 if only one description is missing
    - ``token_sort_ratio / 100`` otherwise
    """
    desc_a = (event_a.get("description") or event_a.get("short_description") or "").strip()
    desc_b = (event_b.get("description") or event_b.get("short_description") or "").strip()

    if not desc_a and not desc_b:
        return 0.5

    if not desc_a or not desc_b:
        return 0.4

    return fuzz.token_sort_ratio(desc_a, desc_b) / 100.0
