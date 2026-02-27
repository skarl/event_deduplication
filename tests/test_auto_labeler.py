"""Tests for the auto-labeling heuristics."""

from event_dedup.ground_truth.auto_labeler import (
    AutoLabelResult,
    auto_label_candidates,
)
from event_dedup.ground_truth.candidate_generator import CandidatePair


def _make_event(
    event_id: str,
    title_normalized: str = "test event",
    city_normalized: str = "emmendingen",
    source_code: str = "bwb",
    short_description_normalized: str | None = None,
    location_name_normalized: str | None = None,
) -> dict:
    return {
        "id": event_id,
        "title_normalized": title_normalized,
        "location_city_normalized": city_normalized,
        "source_code": source_code,
        "short_description_normalized": short_description_normalized,
        "location_name_normalized": location_name_normalized,
    }


def _make_candidate(
    id_a: str, id_b: str, title_sim: float, source_a: str = "bwb", source_b: str = "emt"
) -> CandidatePair:
    return CandidatePair(
        event_id_a=id_a,
        event_id_b=id_b,
        title_sim=title_sim,
        event_a_title="Title A",
        event_b_title="Title B",
        event_a_city="City A",
        event_b_city="City B",
        event_a_source=source_a,
        event_b_source=source_b,
    )


class TestAutoSameHighConfidence:
    """title_sim >= 0.90 AND same city → same."""

    def test_high_title_sim_same_city(self):
        events = {
            "a": _make_event("a", city_normalized="waldkirch", source_code="bwb"),
            "b": _make_event("b", city_normalized="waldkirch", source_code="emt"),
        }
        candidates = [_make_candidate("a", "b", 0.95)]
        result = auto_label_candidates(candidates, events)
        assert result.same_count == 1
        assert result.labeled[0].label == "same"
        assert result.labeled[0].confidence == "high"

    def test_exact_match_same_city(self):
        events = {
            "a": _make_event("a", city_normalized="emmendingen"),
            "b": _make_event("b", city_normalized="emmendingen"),
        }
        candidates = [_make_candidate("a", "b", 1.00)]
        result = auto_label_candidates(candidates, events)
        assert result.same_count == 1

    def test_high_title_sim_different_city_not_auto_same(self):
        """0.95 title_sim but different city should NOT be auto-labeled same."""
        events = {
            "a": _make_event("a", city_normalized="waldkirch"),
            "b": _make_event("b", city_normalized="emmendingen"),
        }
        candidates = [_make_candidate("a", "b", 0.95)]
        result = auto_label_candidates(candidates, events)
        assert result.same_count == 0


class TestAutoSameMediumConfidence:
    """title_sim >= 0.70 AND same city AND desc_sim >= 0.80 → same."""

    def test_multi_signal_same(self):
        events = {
            "a": _make_event(
                "a",
                city_normalized="waldkirch",
                short_description_normalized="grosser kindersachen-flohmarkt im buergersaal emmendingen",
            ),
            "b": _make_event(
                "b",
                city_normalized="waldkirch",
                short_description_normalized="grosser kindersachen-flohmarkt emmendingen buergersaal",
            ),
        }
        candidates = [_make_candidate("a", "b", 0.75)]
        result = auto_label_candidates(candidates, events)
        assert result.same_count == 1
        assert result.labeled[0].confidence == "medium"

    def test_multi_signal_low_desc_sim_ambiguous(self):
        """title_sim 0.75 + same city but low desc_sim → ambiguous, not labeled."""
        events = {
            "a": _make_event(
                "a",
                city_normalized="waldkirch",
                short_description_normalized="fasnet umzug",
            ),
            "b": _make_event(
                "b",
                city_normalized="waldkirch",
                short_description_normalized="konzert im park",
            ),
        }
        candidates = [_make_candidate("a", "b", 0.75)]
        result = auto_label_candidates(candidates, events)
        assert result.same_count == 0
        assert result.skipped_ambiguous == 1


class TestAutoDifferentHighConfidence:
    """title_sim < 0.40 → different, or different city + title_sim < 0.70."""

    def test_very_low_title_sim(self):
        events = {
            "a": _make_event("a", city_normalized="waldkirch"),
            "b": _make_event("b", city_normalized="waldkirch"),
        }
        candidates = [_make_candidate("a", "b", 0.20)]
        result = auto_label_candidates(candidates, events)
        assert result.different_count == 1
        assert result.labeled[0].label == "different"

    def test_different_city_moderate_sim(self):
        events = {
            "a": _make_event("a", city_normalized="waldkirch"),
            "b": _make_event("b", city_normalized="emmendingen"),
        }
        candidates = [_make_candidate("a", "b", 0.55)]
        result = auto_label_candidates(candidates, events)
        assert result.different_count == 1
        assert result.labeled[0].reason == "different_city + title_sim<0.70"

    def test_different_city_high_sim_ambiguous(self):
        """Different city but title_sim 0.75 → ambiguous (might be same event cross-region)."""
        events = {
            "a": _make_event("a", city_normalized="waldkirch"),
            "b": _make_event("b", city_normalized="emmendingen"),
        }
        candidates = [_make_candidate("a", "b", 0.75)]
        result = auto_label_candidates(candidates, events)
        assert result.total == 0
        assert result.skipped_ambiguous == 1


class TestAmbiguousSkipped:
    """Pairs in the ambiguous zone are excluded from ground truth."""

    def test_medium_sim_same_city_no_desc(self):
        """0.60 title_sim + same city but no description → ambiguous."""
        events = {
            "a": _make_event("a", city_normalized="waldkirch"),
            "b": _make_event("b", city_normalized="waldkirch"),
        }
        candidates = [_make_candidate("a", "b", 0.60)]
        result = auto_label_candidates(candidates, events)
        assert result.total == 0
        assert result.skipped_ambiguous == 1

    def test_boundary_title_sim_040(self):
        """title_sim exactly 0.40 + same city → ambiguous (not < 0.40)."""
        events = {
            "a": _make_event("a", city_normalized="waldkirch"),
            "b": _make_event("b", city_normalized="waldkirch"),
        }
        candidates = [_make_candidate("a", "b", 0.40)]
        result = auto_label_candidates(candidates, events)
        assert result.total == 0
        assert result.skipped_ambiguous == 1


class TestResultProperties:
    """AutoLabelResult counts and properties."""

    def test_mixed_results(self):
        events = {
            "a": _make_event("a", city_normalized="waldkirch"),
            "b": _make_event("b", city_normalized="waldkirch"),
            "c": _make_event("c", city_normalized="emmendingen"),
        }
        candidates = [
            _make_candidate("a", "b", 0.95),  # same: high title + same city
            _make_candidate("a", "c", 0.20),  # different: very low title
            _make_candidate("b", "c", 0.55),  # different: diff city + <0.70
        ]
        result = auto_label_candidates(candidates, events)
        assert result.same_count == 1
        assert result.different_count == 2
        assert result.total == 3
        assert result.skipped_ambiguous == 0

    def test_missing_event_skipped(self):
        """If event not found in events_by_id, pair is silently skipped."""
        events = {"a": _make_event("a")}
        candidates = [_make_candidate("a", "missing", 0.95)]
        result = auto_label_candidates(candidates, events)
        assert result.total == 0


class TestDecisionReasons:
    """Verify reason strings for debugging."""

    def test_high_same_reason(self):
        events = {
            "a": _make_event("a", city_normalized="w"),
            "b": _make_event("b", city_normalized="w"),
        }
        result = auto_label_candidates([_make_candidate("a", "b", 0.92)], events)
        assert "title_sim>=0.90" in result.labeled[0].reason

    def test_low_different_reason(self):
        events = {
            "a": _make_event("a", city_normalized="w"),
            "b": _make_event("b", city_normalized="w"),
        }
        result = auto_label_candidates([_make_candidate("a", "b", 0.15)], events)
        assert "title_sim<0.40" in result.labeled[0].reason
