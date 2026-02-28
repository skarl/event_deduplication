"""Prompt template and event formatting for AI matching."""
from __future__ import annotations

from event_dedup.matching.combiner import SignalScores

SYSTEM_PROMPT = """You are an expert event deduplication system analyzing German regional events.

Your task: determine whether two event records describe the SAME real-world event
(same gathering, same place, same time) or DIFFERENT events.

Key considerations:
- German compound words and regional dialects may describe the same thing differently
  (e.g., Fasnet/Fasching/Fastnacht/Karneval are all carnival)
- Source types differ: "artikel" (newspaper articles) have journalistic headlines,
  "terminliste" (event listings) have formal event names
- Same event may have slightly different dates if one source lists a multi-day range
- Location names may vary (abbreviations, spelling differences, missing street details)
- Description length/style varies by source -- focus on factual overlap, not style
- Events at the same venue on the same day may still be DIFFERENT events (check titles carefully)

Respond with ONLY a JSON object matching the required schema."""


def format_event_pair(
    event_a: dict,
    event_b: dict,
    signals: SignalScores,
) -> str:
    """Format two events for AI comparison.

    Args:
        event_a: First event dict with all fields.
        event_b: Second event dict with all fields.
        signals: Pre-computed signal scores from deterministic matching.

    Returns:
        Formatted prompt string for the user message.
    """
    combined = signals.date + signals.geo + signals.title + signals.description

    return f"""Compare these two events:

## Event A (ID: {event_a['id']}, Source: {event_a.get('source_code', 'unknown')}, Type: {event_a.get('source_type', 'unknown')})
Title: {event_a.get('title', 'N/A')}
Description: {_truncate(event_a.get('description') or event_a.get('short_description') or 'N/A', 500)}
Location: {event_a.get('location_name', '')}, {event_a.get('location_city', '')}
Dates: {_format_dates(event_a.get('dates', []))}
Categories: {', '.join(event_a.get('categories') or [])}

## Event B (ID: {event_b['id']}, Source: {event_b.get('source_code', 'unknown')}, Type: {event_b.get('source_type', 'unknown')})
Title: {event_b.get('title', 'N/A')}
Description: {_truncate(event_b.get('description') or event_b.get('short_description') or 'N/A', 500)}
Location: {event_b.get('location_name', '')}, {event_b.get('location_city', '')}
Dates: {_format_dates(event_b.get('dates', []))}
Categories: {', '.join(event_b.get('categories') or [])}

## Deterministic Scoring Context
Combined score: {combined / 4:.2f} (weighted average of signals below)
- Date similarity: {signals.date:.2f}
- Geo proximity: {signals.geo:.2f}
- Title similarity: {signals.title:.2f}
- Description similarity: {signals.description:.2f}

These scores placed this pair in the "ambiguous" zone (between auto-match and auto-reject thresholds).

Are these the SAME real-world event or DIFFERENT events?"""


def _format_dates(dates: list[dict]) -> str:
    """Format a list of date dicts into a readable string."""
    if not dates:
        return "N/A"
    parts = []
    for d in dates[:5]:  # Limit to 5 dates to avoid prompt bloat
        s = d.get("date", "?")
        if d.get("start_time"):
            s += f" {d['start_time']}"
        if d.get("end_time"):
            s += f"-{d['end_time']}"
        if d.get("end_date"):
            s += f" to {d['end_date']}"
        parts.append(s)
    return "; ".join(parts)


def _truncate(text: str, max_len: int) -> str:
    """Truncate text to max_len, adding ellipsis if needed."""
    if len(text) <= max_len:
        return text
    return text[:max_len - 3] + "..."
