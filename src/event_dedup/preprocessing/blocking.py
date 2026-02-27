"""Blocking key generation for candidate pair reduction.

Generates date+city and date+geo_grid blocking keys that group
potentially duplicate events for comparison. Events that share no
blocking keys are never compared, dramatically reducing the O(n^2)
comparison space.
"""

from datetime import date

# Geo confidence threshold -- events below this are not trusted for geo blocking
GEO_CONFIDENCE_THRESHOLD = 0.85

# Geo grid cell dimensions (in degrees) -- ~10km cells in the Breisgau region
GEO_GRID_LAT = 0.09
GEO_GRID_LON = 0.13

# Bounding box for the Breisgau/Schwarzwald region
# Coordinates outside this box are treated as outliers (e.g., Darmstadt geocoding errors)
BOUNDING_BOX = {
    "lat_min": 47.5,
    "lat_max": 48.5,
    "lon_min": 7.3,
    "lon_max": 8.5,
}


def geo_grid_key(lat: float, lon: float) -> str:
    """Compute a grid cell key for the given coordinates.

    Snaps coordinates to a grid defined by GEO_GRID_LAT x GEO_GRID_LON cells.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.

    Returns:
        String like "48.15|7.80" identifying the grid cell.
    """
    cell_lat = round(lat / GEO_GRID_LAT) * GEO_GRID_LAT
    cell_lon = round(lon / GEO_GRID_LON) * GEO_GRID_LON
    return f"{cell_lat:.2f}|{cell_lon:.2f}"


def is_valid_geo(lat: float, lon: float, confidence: float) -> bool:
    """Check whether geo coordinates are trusted for blocking.

    Coordinates must have sufficient confidence AND fall within the
    Breisgau bounding box. This filters out geocoding errors like
    events mapped to Darmstadt or other distant locations.

    Args:
        lat: Latitude in decimal degrees.
        lon: Longitude in decimal degrees.
        confidence: Geocoding confidence score (0-1).

    Returns:
        True if coordinates are trusted for blocking key generation.
    """
    if confidence < GEO_CONFIDENCE_THRESHOLD:
        return False

    return (
        BOUNDING_BOX["lat_min"] <= lat <= BOUNDING_BOX["lat_max"]
        and BOUNDING_BOX["lon_min"] <= lon <= BOUNDING_BOX["lon_max"]
    )


def generate_blocking_keys(
    dates: list[date],
    city_normalized: str | None,
    lat: float | None,
    lon: float | None,
    geo_confidence: float | None,
) -> list[str]:
    """Generate blocking keys for an event based on its dates and location.

    For each event date, generates:
    - A date+city key (dc|) if a normalized city is available
    - A date+geo_grid key (dg|) if valid geo coordinates are available

    Args:
        dates: List of event dates.
        city_normalized: Normalized city name (may be None or empty).
        lat: Latitude (may be None).
        lon: Longitude (may be None).
        geo_confidence: Geocoding confidence (may be None).

    Returns:
        Deduplicated list of blocking key strings.
    """
    keys: list[str] = []

    has_valid_geo = (
        lat is not None
        and lon is not None
        and geo_confidence is not None
        and is_valid_geo(lat, lon, geo_confidence)
    )

    for d in dates:
        date_iso = d.isoformat()

        # Date + city blocking key
        if city_normalized:
            keys.append(f"dc|{date_iso}|{city_normalized}")

        # Date + geo grid blocking key
        if has_valid_geo:
            assert lat is not None and lon is not None  # for type checker
            keys.append(f"dg|{date_iso}|{geo_grid_key(lat, lon)}")

    # Deduplicate while preserving order
    seen: set[str] = set()
    unique_keys: list[str] = []
    for key in keys:
        if key not in seen:
            seen.add(key)
            unique_keys.append(key)

    return unique_keys
