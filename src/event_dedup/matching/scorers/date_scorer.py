"""Date overlap scorer.

Computes a similarity score based on the Jaccard overlap of date sets
and the proximity of start times on shared dates.
"""

from __future__ import annotations

from datetime import date, datetime, timedelta

from event_dedup.matching.config import DateConfig


def _expand_date_range(entry: dict) -> list[str]:
    """Expand a date entry into a list of ISO date strings.

    Handles both single dates (``{"date": "2026-03-01"}``) and ranges
    (``{"start_date": "2026-03-01", "end_date": "2026-03-03"}``).
    """
    if "start_date" in entry and "end_date" in entry:
        try:
            start = date.fromisoformat(entry["start_date"])
            end = date.fromisoformat(entry["end_date"])
        except (ValueError, TypeError):
            return []
        days = []
        current = start
        while current <= end:
            days.append(current.isoformat())
            current += timedelta(days=1)
        return days
    elif "date" in entry:
        return [entry["date"]]
    return []


def _extract_dates(event: dict) -> set[str]:
    """Extract the set of unique date strings from an event dict."""
    raw = event.get("dates") or event.get("event_dates") or []
    result: set[str] = set()
    for entry in raw:
        if isinstance(entry, dict):
            result.update(_expand_date_range(entry))
        elif isinstance(entry, str):
            result.add(entry)
    return result


def _extract_times(event: dict) -> dict[str, str | None]:
    """Build a mapping from date string to start_time for each date entry."""
    raw = event.get("dates") or event.get("event_dates") or []
    times: dict[str, str | None] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        dates_for_entry = _expand_date_range(entry)
        start_time = entry.get("start_time")
        for d in dates_for_entry:
            if d not in times:
                times[d] = start_time
    return times


def _time_proximity_factor(
    time_a: str | None, time_b: str | None, config: DateConfig
) -> float:
    """Compute a time proximity factor in [0, 1].

    If either time is missing, returns 1.0 (benefit of the doubt).
    """
    if not time_a or not time_b:
        return 1.0
    try:
        ta = datetime.strptime(time_a, "%H:%M")
        tb = datetime.strptime(time_b, "%H:%M")
    except ValueError:
        return 1.0
    diff_minutes = abs((ta - tb).total_seconds()) / 60.0
    if diff_minutes <= config.time_tolerance_minutes:
        return 1.0
    if diff_minutes <= config.time_close_minutes:
        return config.close_factor
    if diff_minutes <= config.time_gap_penalty_hours * 60:
        return config.far_factor
    return config.time_gap_penalty_factor


def date_score(
    event_a: dict, event_b: dict, config: DateConfig | None = None
) -> float:
    """Compute date similarity between two events.

    Returns a float in [0, 1]:
    - 0.0 if no date overlap at all
    - Jaccard coefficient * time proximity factor otherwise
    - 0.0 if either event has no dates
    """
    if config is None:
        config = DateConfig()

    dates_a = _extract_dates(event_a)
    dates_b = _extract_dates(event_b)

    if not dates_a or not dates_b:
        return 0.0

    overlap = dates_a & dates_b
    union = dates_a | dates_b

    if not union:
        return 0.0

    jaccard = len(overlap) / len(union)

    if not overlap:
        return 0.0

    # Compute time proximity on shared dates
    times_a = _extract_times(event_a)
    times_b = _extract_times(event_b)

    time_factors = []
    for d in overlap:
        factor = _time_proximity_factor(times_a.get(d), times_b.get(d), config)
        time_factors.append(factor)

    avg_time_factor = sum(time_factors) / len(time_factors) if time_factors else 1.0

    return jaccard * avg_time_factor
