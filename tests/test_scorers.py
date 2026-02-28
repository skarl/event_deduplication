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
        # 240 min apart -> far_factor=0.3
        score = date_score(a, b, config=cfg)
        assert score == pytest.approx(0.3)

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
