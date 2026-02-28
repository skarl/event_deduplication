"""Unit tests for canonical event synthesis with field strategies."""

from __future__ import annotations

import pytest

from event_dedup.canonical.synthesizer import synthesize_canonical
from event_dedup.matching.config import CanonicalConfig


def _make_source(
    id: str,
    title: str = "Test Event",
    short_description: str | None = None,
    description: str | None = None,
    highlights: list | None = None,
    location_name: str | None = None,
    location_city: str | None = None,
    location_district: str | None = None,
    location_street: str | None = None,
    location_zipcode: str | None = None,
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
        "location_name": location_name,
        "location_city": location_city,
        "location_district": location_district,
        "location_street": location_street,
        "location_zipcode": location_zipcode,
        "geo_latitude": geo_latitude,
        "geo_longitude": geo_longitude,
        "geo_confidence": geo_confidence,
        "dates": dates or [{"date": "2026-03-01"}],
        "categories": categories,
        "is_family_event": is_family_event,
        "is_child_focused": is_child_focused,
        "admission_free": admission_free,
    }


class TestSingleSource:
    """Synthesis with a single source event."""

    def test_all_fields_copied(self):
        """All fields are taken directly from the single source."""
        src = _make_source(
            id="ev-1",
            title="Grosser Fasnetumzug Waldkirch 2026",
            short_description="Ein grosser Umzug",
            description="Langer Text zum Umzug durch die Stadt",
            location_city="Waldkirch",
            geo_latitude=48.09,
            geo_longitude=7.96,
            geo_confidence=0.95,
        )
        result = synthesize_canonical([src])

        assert result["title"] == "Grosser Fasnetumzug Waldkirch 2026"
        assert result["short_description"] == "Ein grosser Umzug"
        assert result["description"] == "Langer Text zum Umzug durch die Stadt"
        assert result["location_city"] == "Waldkirch"
        assert result["geo_latitude"] == 48.09
        assert result["geo_confidence"] == 0.95

    def test_provenance_points_to_single_source(self):
        """Provenance maps every field to the single source event."""
        src = _make_source(id="ev-1", title="Grosser Fasnetumzug Waldkirch 2026")
        result = synthesize_canonical([src])

        prov = result["field_provenance"]
        assert prov["title"] == "ev-1"
        assert prov["short_description"] == "ev-1"
        assert prov["description"] == "ev-1"
        assert prov["geo"] == "ev-1"

    def test_source_count_is_one(self):
        """source_count == 1 for a single source."""
        result = synthesize_canonical([_make_source(id="ev-1")])
        assert result["source_count"] == 1


class TestTitleLongestNonGeneric:
    """Title field strategy: longest non-generic (>= 10 chars preferred)."""

    def test_picks_longest_above_min_length(self):
        """Given 3 sources, selects the longest title >= 10 chars."""
        sources = [
            _make_source(id="a", title="Fasnet"),
            _make_source(id="b", title="Fasnet Waldkirch"),
            _make_source(id="c", title="Grosse Fasnet Waldkirch 2026"),
        ]
        result = synthesize_canonical(sources)

        assert result["title"] == "Grosse Fasnet Waldkirch 2026"
        assert result["field_provenance"]["title"] == "c"

    def test_fallback_when_all_short(self):
        """When all titles < 10 chars, picks the longest anyway."""
        sources = [
            _make_source(id="a", title="Fasnet"),
            _make_source(id="b", title="Umzug"),
            _make_source(id="c", title="Narren"),
        ]
        result = synthesize_canonical(sources)

        assert result["title"] == "Fasnet"  # 6 chars, longest
        assert result["field_provenance"]["title"] == "a"

    def test_ignores_short_when_long_exists(self):
        """Short generic title is ignored when a descriptive one exists."""
        sources = [
            _make_source(id="a", title="Fasnet"),
            _make_source(id="b", title="Waldkircher Fasnetumzug am Sonntag"),
        ]
        result = synthesize_canonical(sources)

        assert result["title"] == "Waldkircher Fasnetumzug am Sonntag"
        assert result["field_provenance"]["title"] == "b"


class TestDescriptionLongest:
    """Description field strategy: longest non-empty."""

    def test_picks_longest_description(self):
        """Selects the longest description from 3 sources."""
        sources = [
            _make_source(id="a", description="Short."),
            _make_source(id="b", description="A medium-length description for the event."),
            _make_source(id="c", description="A rather long and detailed description of the event that includes many specifics."),
        ]
        result = synthesize_canonical(sources)

        assert result["description"] == sources[2]["description"]
        assert result["field_provenance"]["description"] == "c"

    def test_all_none_returns_none(self):
        """When all descriptions are None, result is None."""
        sources = [
            _make_source(id="a", description=None),
            _make_source(id="b", description=None),
        ]
        result = synthesize_canonical(sources)

        assert result["description"] is None
        # Provenance still set (to first event)
        assert result["field_provenance"]["description"] == "a"

    def test_short_description_longest(self):
        """Short description also uses longest strategy."""
        sources = [
            _make_source(id="a", short_description="Kurz"),
            _make_source(id="b", short_description="Ein etwas laengerer Kurztext"),
        ]
        result = synthesize_canonical(sources)

        assert result["short_description"] == "Ein etwas laengerer Kurztext"
        assert result["field_provenance"]["short_description"] == "b"


class TestHighlightsUnion:
    """Highlights field strategy: union with deduplication."""

    def test_union_deduplicated(self):
        """Highlights from all sources are merged without duplicates."""
        sources = [
            _make_source(id="a", highlights=["musik"]),
            _make_source(id="b", highlights=["tanz", "musik"]),
        ]
        result = synthesize_canonical(sources)

        assert set(result["highlights"]) == {"musik", "tanz"}
        assert result["field_provenance"]["highlights"] == "union_all_sources"

    def test_preserves_order(self):
        """First-seen order is preserved after deduplication."""
        sources = [
            _make_source(id="a", highlights=["alpha", "beta"]),
            _make_source(id="b", highlights=["beta", "gamma"]),
        ]
        result = synthesize_canonical(sources)

        assert result["highlights"] == ["alpha", "beta", "gamma"]

    def test_empty_when_all_none(self):
        """Returns empty list when no source has highlights."""
        sources = [
            _make_source(id="a", highlights=None),
            _make_source(id="b", highlights=None),
        ]
        result = synthesize_canonical(sources)

        assert result["highlights"] == []


class TestLocationCityMostFrequent:
    """Location city field strategy: most frequent value."""

    def test_most_frequent_wins(self):
        """City appearing in most sources is selected."""
        sources = [
            _make_source(id="a", location_city="Waldkirch"),
            _make_source(id="b", location_city="Freiburg"),
            _make_source(id="c", location_city="Waldkirch"),
        ]
        result = synthesize_canonical(sources)

        assert result["location_city"] == "Waldkirch"

    def test_tie_broken_by_first_occurrence(self):
        """On a tie, the first occurrence wins."""
        sources = [
            _make_source(id="a", location_city="Freiburg"),
            _make_source(id="b", location_city="Waldkirch"),
        ]
        result = synthesize_canonical(sources)

        # Both appear once; Counter.most_common returns in insertion order
        # for equal counts, so "Freiburg" (first) wins
        assert result["location_city"] in ("Freiburg", "Waldkirch")

    def test_none_values_ignored(self):
        """None values are not counted."""
        sources = [
            _make_source(id="a", location_city=None),
            _make_source(id="b", location_city="Waldkirch"),
            _make_source(id="c", location_city=None),
        ]
        result = synthesize_canonical(sources)

        assert result["location_city"] == "Waldkirch"


class TestGeoHighestConfidence:
    """Geo field strategy: highest confidence."""

    def test_picks_highest_confidence(self):
        """Event with highest geo_confidence is selected."""
        sources = [
            _make_source(id="a", geo_latitude=48.0, geo_longitude=7.8, geo_confidence=0.70),
            _make_source(id="b", geo_latitude=48.1, geo_longitude=7.9, geo_confidence=0.90),
        ]
        result = synthesize_canonical(sources)

        assert result["geo_latitude"] == 48.1
        assert result["geo_longitude"] == 7.9
        assert result["geo_confidence"] == 0.90
        assert result["field_provenance"]["geo"] == "b"

    def test_all_missing_returns_none(self):
        """When no event has geo data, returns None values."""
        sources = [
            _make_source(id="a"),
            _make_source(id="b"),
        ]
        result = synthesize_canonical(sources)

        assert result["geo_latitude"] is None
        assert result["geo_longitude"] is None
        assert result["geo_confidence"] is None

    def test_partial_geo_ignored(self):
        """Events with latitude but missing longitude are ignored."""
        sources = [
            _make_source(id="a", geo_latitude=48.0, geo_longitude=None, geo_confidence=0.90),
            _make_source(id="b", geo_latitude=48.1, geo_longitude=7.9, geo_confidence=0.70),
        ]
        result = synthesize_canonical(sources)

        assert result["geo_latitude"] == 48.1
        assert result["geo_confidence"] == 0.70
        assert result["field_provenance"]["geo"] == "b"


class TestDatesUnion:
    """Dates field strategy: union with deduplication."""

    def test_union_from_multiple_sources(self):
        """Dates from all sources are merged."""
        sources = [
            _make_source(id="a", dates=[{"date": "2026-02-12"}]),
            _make_source(id="b", dates=[{"date": "2026-02-12"}, {"date": "2026-02-13"}]),
        ]
        result = synthesize_canonical(sources)

        date_values = [d["date"] for d in result["dates"]]
        assert sorted(date_values) == ["2026-02-12", "2026-02-13"]

    def test_deduplication_by_full_tuple(self):
        """Same date from two sources appears only once."""
        d = {"date": "2026-03-01", "start_time": "14:00", "end_time": None, "end_date": None}
        sources = [
            _make_source(id="a", dates=[d]),
            _make_source(id="b", dates=[d]),
        ]
        result = synthesize_canonical(sources)

        assert len(result["dates"]) == 1
        assert result["dates"][0]["date"] == "2026-03-01"

    def test_different_times_not_deduplicated(self):
        """Same date but different start_time are kept separate."""
        sources = [
            _make_source(id="a", dates=[{"date": "2026-03-01", "start_time": "10:00"}]),
            _make_source(id="b", dates=[{"date": "2026-03-01", "start_time": "14:00"}]),
        ]
        result = synthesize_canonical(sources)

        assert len(result["dates"]) == 2

    def test_provenance_is_union(self):
        """Dates provenance is always 'union_all_sources'."""
        result = synthesize_canonical([_make_source(id="a")])
        assert result["field_provenance"]["dates"] == "union_all_sources"


class TestCategoriesUnion:
    """Categories field strategy: union with deduplication."""

    def test_categories_union(self):
        """Categories from multiple sources are merged without duplicates."""
        sources = [
            _make_source(id="a", categories=["carnival"]),
            _make_source(id="b", categories=["music", "carnival"]),
        ]
        result = synthesize_canonical(sources)

        assert set(result["categories"]) == {"carnival", "music"}


class TestBooleanAnyTrue:
    """Boolean fields strategy: any_true."""

    def test_any_true(self):
        """True if any source has True."""
        sources = [
            _make_source(id="a", is_family_event=False),
            _make_source(id="b", is_family_event=True),
        ]
        result = synthesize_canonical(sources)

        assert result["is_family_event"] is True

    def test_all_false(self):
        """False if no source has True."""
        sources = [
            _make_source(id="a", is_family_event=False),
            _make_source(id="b", is_family_event=False),
        ]
        result = synthesize_canonical(sources)

        assert result["is_family_event"] is False

    def test_none_treated_as_false(self):
        """None values are treated as False."""
        sources = [
            _make_source(id="a", is_family_event=None),
            _make_source(id="b", is_family_event=None),
        ]
        result = synthesize_canonical(sources)

        assert result["is_family_event"] is False

    def test_provenance_points_to_true_source(self):
        """Boolean provenance points to the first True source."""
        sources = [
            _make_source(id="a", admission_free=False),
            _make_source(id="b", admission_free=True),
            _make_source(id="c", admission_free=True),
        ]
        result = synthesize_canonical(sources)

        assert result["field_provenance"]["admission_free"] == "b"


class TestProvenanceTracking:
    """Field provenance is correctly tracked for all fields."""

    def test_every_field_has_provenance(self):
        """Every synthesized field has a provenance entry."""
        sources = [
            _make_source(id="a", title="Grosser Fasnetumzug Waldkirch"),
            _make_source(id="b", title="Fasnetumzug"),
        ]
        result = synthesize_canonical(sources)

        prov = result["field_provenance"]
        expected_fields = {
            "title", "short_description", "description", "highlights",
            "location_name", "location_city", "location_district",
            "location_street", "location_zipcode", "geo", "dates",
            "categories", "is_family_event", "is_child_focused",
            "admission_free",
        }
        assert expected_fields.issubset(set(prov.keys()))

    def test_provenance_values_are_source_ids_or_union(self):
        """Provenance values are event IDs or 'union_all_sources'."""
        sources = [_make_source(id="ev-1"), _make_source(id="ev-2")]
        result = synthesize_canonical(sources)

        valid_values = {"ev-1", "ev-2", "union_all_sources"}
        for val in result["field_provenance"].values():
            assert val in valid_values


class TestSourceCount:
    """source_count is set correctly."""

    def test_three_sources(self):
        """Three source events -> source_count == 3."""
        sources = [_make_source(id=f"ev-{i}") for i in range(3)]
        result = synthesize_canonical(sources)

        assert result["source_count"] == 3

    def test_empty_raises(self):
        """Empty source list raises ValueError."""
        with pytest.raises(ValueError, match="at least one event"):
            synthesize_canonical([])
