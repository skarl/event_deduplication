"""Tests for the four matching signal scorers."""

import pytest

from event_dedup.matching.config import DateConfig, GeoConfig, TitleConfig
from event_dedup.matching.scorers import date_score, description_score, geo_score, title_score


# ===========================================================================
# date_score tests
# ===========================================================================

class TestDateScore:
    """Tests for the date overlap scorer."""

    def test_identical_dates(self) -> None:
        a = {"dates": [{"date": "2026-03-01"}]}
        b = {"dates": [{"date": "2026-03-01"}]}
        assert date_score(a, b) == 1.0

    def test_no_overlap(self) -> None:
        a = {"dates": [{"date": "2026-03-01"}]}
        b = {"dates": [{"date": "2026-04-01"}]}
        assert date_score(a, b) == 0.0

    def test_partial_overlap(self) -> None:
        a = {"dates": [{"date": "2026-03-01"}, {"date": "2026-03-02"}]}
        b = {"dates": [{"date": "2026-03-01"}, {"date": "2026-03-03"}]}
        # Jaccard: 1/3
        score = date_score(a, b)
        assert 0.33 <= score <= 0.34

    def test_missing_dates_a(self) -> None:
        a: dict = {}
        b = {"dates": [{"date": "2026-03-01"}]}
        assert date_score(a, b) == 0.0

    def test_missing_dates_both(self) -> None:
        assert date_score({}, {}) == 0.0

    def test_date_range_expansion(self) -> None:
        a = {"dates": [{"start_date": "2026-03-01", "end_date": "2026-03-03"}]}
        b = {"dates": [{"date": "2026-03-02"}]}
        # a has {03-01, 03-02, 03-03}, b has {03-02} -> jaccard = 1/3
        score = date_score(a, b)
        assert 0.33 <= score <= 0.34

    def test_time_exact_match(self) -> None:
        a = {"dates": [{"date": "2026-03-01", "start_time": "14:00"}]}
        b = {"dates": [{"date": "2026-03-01", "start_time": "14:00"}]}
        assert date_score(a, b) == 1.0

    def test_time_close_match(self) -> None:
        cfg = DateConfig(time_tolerance_minutes=30, time_close_minutes=90, close_factor=0.7)
        a = {"dates": [{"date": "2026-03-01", "start_time": "14:00"}]}
        b = {"dates": [{"date": "2026-03-01", "start_time": "15:00"}]}
        # 60 min apart -> close_factor=0.7
        score = date_score(a, b, config=cfg)
        assert score == pytest.approx(0.7)

    def test_time_far_match(self) -> None:
        cfg = DateConfig(time_tolerance_minutes=30, time_close_minutes=90, far_factor=0.3)
        a = {"dates": [{"date": "2026-03-01", "start_time": "10:00"}]}
        b = {"dates": [{"date": "2026-03-01", "start_time": "14:00"}]}
        # 240 min apart -> beyond 2h threshold -> time_gap_penalty_factor=0.15
        score = date_score(a, b, config=cfg)
        assert score == pytest.approx(0.15)

    def test_time_gap_boundary_below(self) -> None:
        """119 min apart -> still within 2h threshold -> far_factor."""
        cfg = DateConfig()
        a = {"dates": [{"date": "2026-03-01", "start_time": "10:00"}]}
        b = {"dates": [{"date": "2026-03-01", "start_time": "11:59"}]}
        # 119 min apart -> <= 120 min -> far_factor=0.3
        score = date_score(a, b, config=cfg)
        assert score == pytest.approx(0.3)

    def test_time_gap_boundary_at(self) -> None:
        """121 min apart -> exceeds 2h threshold -> time_gap_penalty_factor."""
        cfg = DateConfig()
        a = {"dates": [{"date": "2026-03-01", "start_time": "10:00"}]}
        b = {"dates": [{"date": "2026-03-01", "start_time": "12:01"}]}
        # 121 min apart -> > 120 min -> time_gap_penalty_factor=0.15
        score = date_score(a, b, config=cfg)
        assert score == pytest.approx(0.15)

    def test_time_gap_custom_threshold(self) -> None:
        """3h threshold, 150 min apart -> still within threshold -> far_factor."""
        cfg = DateConfig(time_gap_penalty_hours=3.0)
        a = {"dates": [{"date": "2026-03-01", "start_time": "10:00"}]}
        b = {"dates": [{"date": "2026-03-01", "start_time": "12:30"}]}
        # 150 min apart -> <= 180 min -> far_factor=0.3
        score = date_score(a, b, config=cfg)
        assert score == pytest.approx(0.3)

    def test_time_gap_custom_threshold_exceeded(self) -> None:
        """3h threshold, 201 min apart -> exceeds threshold -> penalty_factor."""
        cfg = DateConfig(time_gap_penalty_hours=3.0, time_gap_penalty_factor=0.1)
        a = {"dates": [{"date": "2026-03-01", "start_time": "10:00"}]}
        b = {"dates": [{"date": "2026-03-01", "start_time": "13:21"}]}
        # 201 min apart -> > 180 min -> time_gap_penalty_factor=0.1
        score = date_score(a, b, config=cfg)
        assert score == pytest.approx(0.1)

    def test_missing_times_benefit_of_doubt(self) -> None:
        a = {"dates": [{"date": "2026-03-01", "start_time": "14:00"}]}
        b = {"dates": [{"date": "2026-03-01"}]}
        # Missing time -> factor=1.0
        assert date_score(a, b) == 1.0

    def test_event_dates_key(self) -> None:
        """Support 'event_dates' key as used in raw JSON."""
        a = {"event_dates": [{"date": "2026-03-01"}]}
        b = {"event_dates": [{"date": "2026-03-01"}]}
        assert date_score(a, b) == 1.0

    def test_empty_dates_list(self) -> None:
        a = {"dates": []}
        b = {"dates": [{"date": "2026-03-01"}]}
        assert date_score(a, b) == 0.0


# ===========================================================================
# geo_score tests
# ===========================================================================

class TestGeoScore:
    """Tests for the geographic distance scorer."""

    def test_same_location(self) -> None:
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        assert geo_score(a, b) == 1.0

    def test_far_apart(self) -> None:
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        b = {"geo_latitude": 49.0, "geo_longitude": 9.0, "geo_confidence": 0.95}
        # ~130 km apart -> 0.0
        assert geo_score(a, b) == 0.0

    def test_moderate_distance(self) -> None:
        """Two points ~5km apart should score around 0.5."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        # ~5km north
        b = {"geo_latitude": 48.045, "geo_longitude": 7.8, "geo_confidence": 0.95}
        score = geo_score(a, b)
        assert 0.4 <= score <= 0.6

    def test_missing_lat(self) -> None:
        a = {"geo_longitude": 7.8, "geo_confidence": 0.95}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        assert geo_score(a, b) == 0.5

    def test_missing_all_geo(self) -> None:
        assert geo_score({}, {}) == 0.5

    def test_low_confidence(self) -> None:
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.50}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        assert geo_score(a, b) == 0.5

    def test_no_confidence_field(self) -> None:
        """If confidence is not provided, treat as acceptable."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8}
        assert geo_score(a, b) == 1.0

    def test_custom_max_distance(self) -> None:
        cfg = GeoConfig(max_distance_km=5.0)
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        b = {"geo_latitude": 48.045, "geo_longitude": 7.8, "geo_confidence": 0.95}
        # ~5km apart with max=5 -> ~0.0
        score = geo_score(a, b, config=cfg)
        assert score <= 0.1

    def test_custom_neutral_score(self) -> None:
        cfg = GeoConfig(neutral_score=0.3)
        assert geo_score({}, {}, config=cfg) == 0.3

    def test_same_venue_name(self) -> None:
        """Same coordinates, same venue name -> 1.0."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Stadttheater"}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Stadttheater"}
        assert geo_score(a, b) == 1.0

    def test_different_venue_name_close(self) -> None:
        """Same coordinates, completely different venue names -> 0.5."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Stadttheater"}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Messehalle"}
        score = geo_score(a, b)
        assert score == pytest.approx(0.5)

    def test_venue_name_missing_one(self) -> None:
        """Same coordinates, one venue name missing -> 1.0 (no penalty)."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Stadttheater"}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        assert geo_score(a, b) == 1.0

    def test_venue_name_missing_both(self) -> None:
        """Same coordinates, both venue names missing -> 1.0 (no penalty)."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95}
        assert geo_score(a, b) == 1.0

    def test_venue_name_far_distance(self) -> None:
        """Far apart, different venue names -> distance-only score (no venue penalty)."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Stadttheater"}
        # ~5km north -> beyond venue_match_distance_km=1.0
        b = {"geo_latitude": 48.045, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Messehalle"}
        score = geo_score(a, b)
        # Should be distance-only, no venue factor applied
        score_no_names = geo_score(
            {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95},
            {"geo_latitude": 48.045, "geo_longitude": 7.8, "geo_confidence": 0.95},
        )
        assert score == pytest.approx(score_no_names)

    def test_similar_venue_name(self) -> None:
        """Same coordinates, similar venue names -> 1.0 (similarity >= 0.5)."""
        a = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Stadttheater Freiburg"}
        b = {"geo_latitude": 48.0, "geo_longitude": 7.8, "geo_confidence": 0.95, "location_name": "Freiburg Stadttheater"}
        assert geo_score(a, b) == 1.0


# ===========================================================================
# title_score tests
# ===========================================================================

class TestTitleScore:
    """Tests for the title fuzzy-matching scorer."""

    def test_identical_titles(self) -> None:
        a = {"title": "Konzert im Park"}
        b = {"title": "Konzert im Park"}
        assert title_score(a, b) == 1.0

    def test_completely_different(self) -> None:
        a = {"title": "AAAA BBBB CCCC"}
        b = {"title": "XXXX YYYY ZZZZ"}
        assert title_score(a, b) < 0.2

    def test_similar_titles(self) -> None:
        a = {"title": "Konzert im Stadtpark"}
        b = {"title": "Stadtpark Konzert"}
        score = title_score(a, b)
        assert score > 0.7

    def test_missing_title_a(self) -> None:
        a: dict = {}
        b = {"title": "Konzert"}
        assert title_score(a, b) == 0.0

    def test_missing_title_both(self) -> None:
        assert title_score({}, {}) == 0.0

    def test_empty_title(self) -> None:
        a = {"title": ""}
        b = {"title": "Konzert"}
        assert title_score(a, b) == 0.0

    def test_whitespace_only(self) -> None:
        a = {"title": "   "}
        b = {"title": "Konzert"}
        assert title_score(a, b) == 0.0

    def test_blending_range(self) -> None:
        """When primary score is in blend range, result should differ from pure primary."""
        cfg = TitleConfig(blend_lower=0.0, blend_upper=1.0)
        a = {"title": "Konzert im Stadtpark Freiburg"}
        b = {"title": "Stadtpark Freiburg Konzert"}
        # With full blending enabled, score may differ from primary-only
        score_blend = title_score(a, b, config=cfg)
        assert 0.0 < score_blend <= 1.0

    def test_cross_source_type_uses_override(self) -> None:
        """When source types differ (artikel vs terminliste), cross_source_type config is used."""
        cross_cfg = TitleConfig(
            primary_weight=0.4, secondary_weight=0.6,
            blend_lower=0.25, blend_upper=0.95,
        )
        cfg = TitleConfig(cross_source_type=cross_cfg)
        a = {"title": "Preismaskenball", "source_type": "terminliste"}
        b = {"title": "Preismaskenball mit Hemdglunker und Musikverein", "source_type": "artikel"}
        score_cross = title_score(a, b, config=cfg)
        score_default = title_score(a, b, config=TitleConfig())
        assert score_cross > score_default

    def test_same_source_type_no_override(self) -> None:
        """When both events have same source type, default config is used."""
        cross_cfg = TitleConfig(
            primary_weight=0.1, secondary_weight=0.9,
            blend_lower=0.0, blend_upper=1.0,
        )
        cfg = TitleConfig(cross_source_type=cross_cfg)
        a = {"title": "Konzert im Park", "source_type": "artikel"}
        b = {"title": "Park Konzert", "source_type": "artikel"}
        score_with_cfg = title_score(a, b, config=cfg)
        score_default = title_score(a, b, config=TitleConfig())
        assert score_with_cfg == score_default

    def test_missing_source_type_no_override(self) -> None:
        """When source_type is missing, default config is used."""
        cross_cfg = TitleConfig(
            primary_weight=0.1, secondary_weight=0.9,
            blend_lower=0.0, blend_upper=1.0,
        )
        cfg = TitleConfig(cross_source_type=cross_cfg)
        a = {"title": "Konzert im Park"}
        b = {"title": "Park Konzert"}
        score_with_cfg = title_score(a, b, config=cfg)
        score_default = title_score(a, b, config=TitleConfig())
        assert score_with_cfg == score_default

    def test_anzeige_source_type_no_override(self) -> None:
        """Anzeige source type does not trigger cross_source_type override."""
        cross_cfg = TitleConfig(
            primary_weight=0.1, secondary_weight=0.9,
            blend_lower=0.0, blend_upper=1.0,
        )
        cfg = TitleConfig(cross_source_type=cross_cfg)
        a = {"title": "SC Freiburg Spiel", "source_type": "anzeige"}
        b = {"title": "SC Freiburg Bundesliga Spiel", "source_type": "artikel"}
        score_with_cfg = title_score(a, b, config=cfg)
        score_default = title_score(a, b, config=TitleConfig())
        assert score_with_cfg == score_default

    def test_cross_source_type_wider_blend_catches_low_sort(self) -> None:
        """Cross-type config with wider blend range catches pairs outside default range."""
        cross_cfg = TitleConfig(
            primary_weight=0.4, secondary_weight=0.6,
            blend_lower=0.25, blend_upper=0.95,
        )
        cfg = TitleConfig(cross_source_type=cross_cfg)
        a = {"title": "Schiebeschlage", "source_type": "terminliste"}
        b = {"title": "Traditionelles Schiebeschlage mit gluehenden Holzscheiben", "source_type": "artikel"}
        score = title_score(a, b, config=cfg)
        assert score > 0.5


# ===========================================================================
# description_score tests
# ===========================================================================

class TestDescriptionScore:
    """Tests for the description similarity scorer."""

    def test_identical_descriptions(self) -> None:
        a = {"description": "Ein tolles Event im Freien mit Musik und Tanz."}
        b = {"description": "Ein tolles Event im Freien mit Musik und Tanz."}
        assert description_score(a, b) == 1.0

    def test_completely_different(self) -> None:
        a = {"description": "AAAA BBBB CCCC DDDD EEEE"}
        b = {"description": "XXXX YYYY ZZZZ WWWW VVVV"}
        assert description_score(a, b) < 0.2

    def test_both_missing(self) -> None:
        assert description_score({}, {}) == 0.5

    def test_one_missing(self) -> None:
        a = {"description": "Ein tolles Event"}
        b: dict = {}
        assert description_score(a, b) == 0.4

    def test_empty_strings(self) -> None:
        a = {"description": ""}
        b = {"description": ""}
        assert description_score(a, b) == 0.5

    def test_similar_descriptions(self) -> None:
        a = {"description": "Familienkonzert im Stadtpark mit dem Philharmonie-Orchester."}
        b = {"description": "Konzert der Philharmonie im Stadtpark fuer Familien."}
        score = description_score(a, b)
        assert 0.3 < score < 0.9
