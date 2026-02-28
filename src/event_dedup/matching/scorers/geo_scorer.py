"""Geographic distance scorer using the Haversine formula.

Returns a score in [0, 1] based on how close two events are
geographically.  Missing or low-confidence coordinates return
a neutral score (default 0.5).
"""

from __future__ import annotations

import math

from rapidfuzz import fuzz

from event_dedup.matching.config import GeoConfig


def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    """Compute the great-circle distance between two points in kilometres."""
    R = 6371.0  # Earth radius in km
    dlat = math.radians(lat2 - lat1)
    dlon = math.radians(lon2 - lon1)
    a = (
        math.sin(dlat / 2) ** 2
        + math.cos(math.radians(lat1)) * math.cos(math.radians(lat2)) * math.sin(dlon / 2) ** 2
    )
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))


def _venue_name_factor(
    name_a: str | None, name_b: str | None, config: GeoConfig
) -> float:
    """Compare venue names when events are in close proximity."""
    if not name_a or not name_b:
        return 1.0
    ratio = fuzz.token_sort_ratio(name_a.lower(), name_b.lower()) / 100.0
    if ratio >= 0.5:
        return 1.0
    return config.venue_mismatch_factor


def geo_score(
    event_a: dict, event_b: dict, config: GeoConfig | None = None
) -> float:
    """Compute geographic proximity score between two events.

    Returns a float in [0, 1]:
    - ``config.neutral_score`` if either event is missing coordinates
      or has low geo confidence
    - ``max(0.0, 1.0 - distance / max_distance_km)`` otherwise
    """
    if config is None:
        config = GeoConfig()

    lat_a = event_a.get("geo_latitude")
    lon_a = event_a.get("geo_longitude")
    conf_a = event_a.get("geo_confidence")

    lat_b = event_b.get("geo_latitude")
    lon_b = event_b.get("geo_longitude")
    conf_b = event_b.get("geo_confidence")

    # Missing coordinates -> neutral
    if lat_a is None or lon_a is None or lat_b is None or lon_b is None:
        return config.neutral_score

    # When both events have (near-)identical coordinates, the geocoder
    # placed them at the same spot — skip the confidence gate because
    # consistent results are a strong location signal regardless of
    # individual confidence values.
    coords_identical = abs(lat_a - lat_b) < 1e-6 and abs(lon_a - lon_b) < 1e-6

    # Low confidence -> neutral (unless coordinates match)
    if not coords_identical:
        if conf_a is not None and conf_a < config.min_confidence:
            return config.neutral_score
        if conf_b is not None and conf_b < config.min_confidence:
            return config.neutral_score

    dist = _haversine_km(lat_a, lon_a, lat_b, lon_b)
    score = max(0.0, 1.0 - dist / config.max_distance_km)

    # When events are in close proximity, compare venue names
    if dist < config.venue_match_distance_km:
        venue_f = _venue_name_factor(
            event_a.get("location_name"),
            event_b.get("location_name"),
            config,
        )
        score *= venue_f

    return score
