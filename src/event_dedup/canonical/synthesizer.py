"""Canonical event synthesis from clustered source events.

Selects the best field value from each source event in a cluster
using configurable field strategies, and tracks which source event
contributed each field (provenance).  All functions are pure -- no
database access.
"""

from __future__ import annotations

from collections import Counter

from event_dedup.matching.config import CanonicalConfig


def synthesize_canonical(
    source_events: list[dict],
    config: CanonicalConfig | None = None,
) -> dict:
    """Create a canonical event from a cluster of source events.

    Applies field selection strategies to choose the best value for
    each field, and records provenance (which source event contributed
    each field).

    Args:
        source_events: List of source event dicts from a single cluster.
            Must have at least one event.
        config: Configuration for field strategies.  Defaults to
            ``CanonicalConfig()`` if not provided.

    Returns:
        A dict representing the canonical event with all merged fields,
        ``field_provenance``, and ``source_count``.
    """
    if not source_events:
        raise ValueError("source_events must contain at least one event")

    if config is None:
        config = CanonicalConfig()

    result: dict = {}
    provenance: dict[str, str] = {}

    # --- Title (longest non-generic) ---
    title_val, title_src = _select_longest_non_generic(
        source_events, "title", min_length=10
    )
    result["title"] = title_val
    provenance["title"] = title_src

    # --- Short description (longest) ---
    sd_val, sd_src = _select_longest(source_events, "short_description")
    result["short_description"] = sd_val
    provenance["short_description"] = sd_src

    # --- Description (longest) ---
    desc_val, desc_src = _select_longest(source_events, "description")
    result["description"] = desc_val
    provenance["description"] = desc_src

    # --- Highlights (union) ---
    hl_val, hl_prov = _select_union_lists(source_events, "highlights")
    result["highlights"] = hl_val
    provenance["highlights"] = hl_prov

    # --- Location fields ---
    for field in ("location_name", "location_district", "location_street", "location_zipcode"):
        val, src = _select_most_complete(source_events, field)
        result[field] = val
        provenance[field] = src

    # --- Location city (most frequent) ---
    city_val, city_src = _select_most_frequent(source_events, "location_city")
    result["location_city"] = city_val
    provenance["location_city"] = city_src

    # --- Geo (highest confidence) ---
    geo_dict, geo_src = _select_best_geo(source_events)
    result["geo_latitude"] = geo_dict.get("geo_latitude")
    result["geo_longitude"] = geo_dict.get("geo_longitude")
    result["geo_confidence"] = geo_dict.get("geo_confidence")
    provenance["geo"] = geo_src

    # --- Dates (union, deduplicated) ---
    result["dates"] = _union_dates(source_events)
    provenance["dates"] = "union_all_sources"

    # --- Categories (union) ---
    cat_val, cat_prov = _select_union_lists(source_events, "categories")
    result["categories"] = cat_val
    provenance["categories"] = cat_prov

    # --- Boolean fields (any_true) ---
    for field in ("is_family_event", "is_child_focused", "admission_free"):
        val = any(e.get(field) for e in source_events)
        result[field] = val
        # Provenance: first event with True, else first event
        prov_src = source_events[0].get("id", "unknown")
        for e in source_events:
            if e.get(field):
                prov_src = e.get("id", "unknown")
                break
        provenance[field] = prov_src

    result["field_provenance"] = provenance
    result["source_count"] = len(source_events)

    return result


# ---------------------------------------------------------------------------
# Field selection helpers (all pure functions)
# ---------------------------------------------------------------------------


def _select_longest(
    events: list[dict], field: str
) -> tuple[str | None, str]:
    """Select the longest non-empty string value for *field*.

    Returns:
        Tuple of (value, source_event_id).  If all values are None or
        empty, returns (None, first_event_id).
    """
    best_val: str | None = None
    best_len = -1
    best_src = events[0].get("id", "unknown")

    for e in events:
        val = e.get(field)
        if val and len(val) > best_len:
            best_val = val
            best_len = len(val)
            best_src = e.get("id", "unknown")

    return best_val, best_src


def _select_longest_non_generic(
    events: list[dict], field: str, min_length: int = 10
) -> tuple[str, str]:
    """Select the longest value that is at least *min_length* characters.

    If no value meets the minimum length, falls back to the longest
    value regardless.

    Returns:
        Tuple of (value, source_event_id).
    """
    # Collect values >= min_length
    long_candidates: list[tuple[str, str]] = []
    all_candidates: list[tuple[str, str]] = []

    for e in events:
        val = e.get(field)
        if val:
            src = e.get("id", "unknown")
            all_candidates.append((val, src))
            if len(val) >= min_length:
                long_candidates.append((val, src))

    # Prefer long candidates; fall back to all
    pool = long_candidates if long_candidates else all_candidates
    if not pool:
        # All None/empty -- return empty string from first event
        return "", events[0].get("id", "unknown")

    # Pick longest in the pool
    best = max(pool, key=lambda x: len(x[0]))
    return best[0], best[1]


def _select_union_lists(
    events: list[dict], field: str
) -> tuple[list, str]:
    """Union all list values for *field*, preserving order and deduplicating.

    Returns:
        Tuple of (deduplicated_list, "union_all_sources").
    """
    seen: set = set()
    result: list = []

    for e in events:
        items = e.get(field)
        if items and isinstance(items, list):
            for item in items:
                hashable = str(item) if not isinstance(item, (str, int, float, bool)) else item
                if hashable not in seen:
                    seen.add(hashable)
                    result.append(item)

    return result, "union_all_sources"


def _select_most_complete(
    events: list[dict], field: str
) -> tuple[str | None, str]:
    """Select the most complete (longest non-empty) string value.

    Semantically identical to ``_select_longest`` but named for clarity
    when used with location fields.
    """
    return _select_longest(events, field)


def _select_most_frequent(
    events: list[dict], field: str
) -> tuple[str | None, str]:
    """Select the most common non-empty value for *field*.

    Ties are broken by first occurrence.

    Returns:
        Tuple of (value, source_event_id_of_first_occurrence).
    """
    counter: Counter[str] = Counter()
    first_src: dict[str, str] = {}

    for e in events:
        val = e.get(field)
        if val:
            counter[val] += 1
            if val not in first_src:
                first_src[val] = e.get("id", "unknown")

    if not counter:
        return None, events[0].get("id", "unknown")

    most_common_val = counter.most_common(1)[0][0]
    return most_common_val, first_src[most_common_val]


def _select_best_geo(
    events: list[dict],
) -> tuple[dict, str]:
    """Select the event with the highest ``geo_confidence``.

    Only considers events where both latitude and longitude are present.

    Returns:
        Tuple of (geo_dict, source_event_id).  If no event has valid
        geo data, returns a dict with None values and the first event's ID.
    """
    best_conf: float = -1.0
    best_geo: dict = {
        "geo_latitude": None,
        "geo_longitude": None,
        "geo_confidence": None,
    }
    best_src = events[0].get("id", "unknown")

    for e in events:
        lat = e.get("geo_latitude")
        lon = e.get("geo_longitude")
        conf = e.get("geo_confidence")
        if lat is not None and lon is not None and conf is not None:
            if conf > best_conf:
                best_conf = conf
                best_geo = {
                    "geo_latitude": lat,
                    "geo_longitude": lon,
                    "geo_confidence": conf,
                }
                best_src = e.get("id", "unknown")

    return best_geo, best_src


def _union_dates(events: list[dict]) -> list[dict]:
    """Collect all unique dates from all events.

    Deduplicates by the tuple (date, start_time, end_time, end_date).

    Returns:
        List of unique date dicts.
    """
    seen: set[tuple] = set()
    result: list[dict] = []

    for e in events:
        dates = e.get("dates")
        if not dates:
            continue
        for d in dates:
            key = (
                d.get("date"),
                d.get("start_time"),
                d.get("end_time"),
                d.get("end_date"),
            )
            if key not in seen:
                seen.add(key)
                result.append(d)

    return result
