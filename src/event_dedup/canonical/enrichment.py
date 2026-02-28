"""Canonical event enrichment with downgrade prevention.

Re-synthesizes a canonical event when new source events arrive,
but prevents downgrading text fields that were already better
in the existing canonical.
"""

from __future__ import annotations

from event_dedup.matching.config import CanonicalConfig

from .synthesizer import synthesize_canonical


# Text fields subject to downgrade prevention (longer is better).
_TEXT_FIELDS = ("title", "short_description", "description")


def enrich_canonical(
    existing_canonical: dict,
    all_sources: list[dict],
    config: CanonicalConfig | None = None,
) -> dict:
    """Enrich an existing canonical event with additional sources.

    Re-runs ``synthesize_canonical`` with ALL source events (old and
    new), then applies downgrade prevention: if the existing canonical
    already had a longer text field value, that value and its provenance
    are preserved.

    Args:
        existing_canonical: The current canonical event dict (must have
            ``field_provenance`` and ``version`` keys).
        all_sources: Complete list of source event dicts (including any
            that contributed to the existing canonical).
        config: Canonical configuration.  Defaults to ``CanonicalConfig()``
            if not provided.

    Returns:
        An updated canonical event dict with incremented version.
    """
    if config is None:
        config = CanonicalConfig()

    new_canonical = synthesize_canonical(all_sources, config)

    existing_provenance = existing_canonical.get("field_provenance", {})
    new_provenance = new_canonical.get("field_provenance", {})

    # Downgrade prevention for text fields
    for field in _TEXT_FIELDS:
        existing_len = len(existing_canonical.get(field) or "")
        new_len = len(new_canonical.get(field) or "")
        if existing_len > new_len:
            new_canonical[field] = existing_canonical[field]
            new_provenance[field] = existing_provenance.get(field, "unknown")

    # Version increment
    new_canonical["version"] = existing_canonical.get("version", 1) + 1

    # Source count from actual sources
    new_canonical["source_count"] = len(all_sources)

    return new_canonical
