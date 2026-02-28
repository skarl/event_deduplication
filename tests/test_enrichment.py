"""Unit tests for canonical event enrichment with downgrade prevention."""

from __future__ import annotations

from event_dedup.canonical.enrichment import enrich_canonical
from event_dedup.canonical.synthesizer import synthesize_canonical


def _make_source(
    id: str,
    title: str = "Test Event",
    short_description: str | None = None,
    description: str | None = None,
    highlights: list | None = None,
    location_city: str | None = None,
    geo_latitude: float | None = None,
    geo_longitude: float | None = None,
    geo_confidence: float | None = None,
    dates: list[dict] | None = None,
    categories: list | None = None,
    is_family_event: bool | None = None,
    is_child_focused: bool | None = None,
    admission_free: bool | None = None,
) -> dict:
    """Create a source event dict for testing."""
    return {
        "id": id,
        "title": title,
        "short_description": short_description,
        "description": description,
        "highlights": highlights,
        "location_name": None,
        "location_city": location_city,
        "location_district": None,
        "location_street": None,
        "location_zipcode": None,
        "geo_latitude": geo_latitude,
        "geo_longitude": geo_longitude,
        "geo_confidence": geo_confidence,
        "dates": dates or [{"date": "2026-03-01"}],
        "categories": categories,
        "is_family_event": is_family_event,
        "is_child_focused": is_child_focused,
        "admission_free": admission_free,
    }


class TestEnrichmentUpgrade:
    """Enrichment upgrades fields when new sources are better."""

    def test_better_title_upgrades(self):
        """Longer title from new source replaces short existing title."""
        old_sources = [_make_source(id="a", title="Fasnet")]
        existing = synthesize_canonical(old_sources)

        new_source = _make_source(id="b", title="Grosser Fasnetumzug Waldkirch 2026")
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["title"] == "Grosser Fasnetumzug Waldkirch 2026"
        assert enriched["field_provenance"]["title"] == "b"

    def test_enrichment_adds_new_highlights(self):
        """New highlights are added to the union."""
        old_sources = [_make_source(id="a", highlights=["musik"])]
        existing = synthesize_canonical(old_sources)

        new_source = _make_source(id="b", highlights=["tanz"])
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        assert set(enriched["highlights"]) == {"musik", "tanz"}

    def test_enrichment_adds_new_dates(self):
        """New dates are merged into the canonical."""
        old_sources = [_make_source(id="a", dates=[{"date": "2026-02-12"}])]
        existing = synthesize_canonical(old_sources)

        new_source = _make_source(id="b", dates=[{"date": "2026-02-13"}])
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        date_values = sorted(d["date"] for d in enriched["dates"])
        assert date_values == ["2026-02-12", "2026-02-13"]

    def test_enrichment_upgrades_geo(self):
        """Higher geo confidence from new source replaces existing."""
        old_sources = [
            _make_source(id="a", geo_latitude=48.0, geo_longitude=7.8, geo_confidence=0.70)
        ]
        existing = synthesize_canonical(old_sources)

        new_source = _make_source(
            id="b", geo_latitude=48.1, geo_longitude=7.9, geo_confidence=0.90
        )
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["geo_confidence"] == 0.90
        assert enriched["geo_latitude"] == 48.1


class TestEnrichmentDowngradePrevention:
    """Enrichment prevents downgrading text fields."""

    def test_preserves_better_existing_title(self):
        """Existing longer title is NOT replaced by shorter new title."""
        old_sources = [
            _make_source(id="a", title="Grosser Fasnetumzug Waldkirch 2026")
        ]
        existing = synthesize_canonical(old_sources)

        new_source = _make_source(id="b", title="Fasnet")
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        # Synthesis would pick "a" anyway (longest non-generic), but
        # downgrade prevention also ensures it stays
        assert enriched["title"] == "Grosser Fasnetumzug Waldkirch 2026"

    def test_preserves_existing_description(self):
        """Existing long description is preserved when new source has none."""
        old_sources = [
            _make_source(id="a", description="A very detailed event description for testing.")
        ]
        existing = synthesize_canonical(old_sources)

        new_source = _make_source(id="b", description=None)
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["description"] == "A very detailed event description for testing."
        assert enriched["field_provenance"]["description"] == "a"

    def test_preserves_existing_short_description(self):
        """Existing short_description is preserved against shorter replacement."""
        old_sources = [
            _make_source(id="a", short_description="Ein ausfuehrlicher Kurztext zum Event")
        ]
        existing = synthesize_canonical(old_sources)

        new_source = _make_source(id="b", short_description="Kurz")
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["short_description"] == "Ein ausfuehrlicher Kurztext zum Event"


class TestEnrichmentVersioning:
    """Version tracking and source counting."""

    def test_version_increment(self):
        """Version increments from 1 to 2."""
        old_sources = [_make_source(id="a")]
        existing = synthesize_canonical(old_sources)
        existing["version"] = 1

        all_sources = old_sources + [_make_source(id="b")]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["version"] == 2

    def test_version_increment_from_higher(self):
        """Version increments correctly from higher values."""
        old_sources = [_make_source(id="a")]
        existing = synthesize_canonical(old_sources)
        existing["version"] = 5

        all_sources = old_sources + [_make_source(id="b")]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["version"] == 6

    def test_missing_version_defaults_to_one(self):
        """If existing has no version, defaults to 1, so enriched = 2."""
        old_sources = [_make_source(id="a")]
        existing = synthesize_canonical(old_sources)
        existing.pop("version", None)

        all_sources = old_sources + [_make_source(id="b")]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["version"] == 2

    def test_source_count_updated(self):
        """source_count reflects total number of sources."""
        old_sources = [_make_source(id="a"), _make_source(id="b")]
        existing = synthesize_canonical(old_sources)
        assert existing["source_count"] == 2

        new_source = _make_source(id="c")
        all_sources = old_sources + [new_source]
        enriched = enrich_canonical(existing, all_sources)

        assert enriched["source_count"] == 3
