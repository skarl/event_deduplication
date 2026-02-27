"""Tests for the ground truth candidate generator."""

from event_dedup.ground_truth.candidate_generator import (
    CandidatePair,
    generate_candidates_from_events,
)


def _make_event(
    event_id: str,
    title: str = "Test Event",
    title_normalized: str = "test event",
    source_code: str = "bwb",
    location_city: str | None = "Freiburg",
    location_city_normalized: str | None = "freiburg",
    blocking_keys: list[str] | None = None,
) -> dict:
    """Helper to create a synthetic event dict."""
    return {
        "id": event_id,
        "title": title,
        "title_normalized": title_normalized,
        "location_city": location_city,
        "location_city_normalized": location_city_normalized,
        "source_code": source_code,
        "blocking_keys": blocking_keys or [],
    }


class TestCrossSourcePairs:
    def test_cross_source_pairs_only(self):
        """Events from the same source should not be paired."""
        events = [
            _make_event("e1", source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e3", source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        result = generate_candidates_from_events(events)
        assert len(result) == 0

    def test_cross_source_pairs_generated(self):
        """Events from different sources in the same block should be paired."""
        events = [
            _make_event("e1", source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        result = generate_candidates_from_events(events)
        assert len(result) == 1
        assert result[0].event_id_a == "e1"
        assert result[0].event_id_b == "e2"


class TestTitleSimilarityFilter:
    def test_title_similarity_filter(self):
        """Pairs below min_title_sim should be filtered out (except hard negatives)."""
        events = [
            _make_event(
                "e1",
                title="Sommerkonzert im Stadtpark Freiburg",
                title_normalized="sommerkonzert im stadtpark freiburg",
                source_code="bwb",
                blocking_keys=["dc|2026-02-12|freiburg"],
            ),
            _make_event(
                "e2",
                title="Sommerkonzert im Stadtpark Freiburg",
                title_normalized="sommerkonzert im stadtpark freiburg",
                source_code="emt",
                blocking_keys=["dc|2026-02-12|freiburg"],
            ),
            _make_event(
                "e3",
                title="Bauernmarkt am Muensterplatz",
                title_normalized="bauernmarkt am muensterplatz",
                source_code="xyz",
                blocking_keys=["dc|2026-02-12|freiburg"],
            ),
        ]
        # High threshold to filter out less similar pairs
        result = generate_candidates_from_events(events, min_title_sim=0.90, hard_negative_ratio=0.0)

        # Only the identical titles should pass at 0.90 threshold
        high_sim_ids = {(c.event_id_a, c.event_id_b) for c in result}
        assert ("e1", "e2") in high_sim_ids  # identical titles
        # The dissimilar pair should be filtered
        for c in result:
            assert c.title_sim >= 0.90


class TestPairDeduplication:
    def test_pair_deduplication(self):
        """Events sharing multiple blocking keys should produce only one pair."""
        events = [
            _make_event(
                "e1",
                source_code="bwb",
                blocking_keys=["dc|2026-02-12|freiburg", "dg|2026-02-12|48.00|7.80"],
            ),
            _make_event(
                "e2",
                source_code="emt",
                blocking_keys=["dc|2026-02-12|freiburg", "dg|2026-02-12|48.00|7.80"],
            ),
        ]
        result = generate_candidates_from_events(events, min_title_sim=0.0)
        # Should appear exactly once despite sharing two blocking keys
        pair_ids = [(c.event_id_a, c.event_id_b) for c in result]
        assert pair_ids.count(("e1", "e2")) == 1


class TestCanonicalIdOrdering:
    def test_canonical_id_ordering(self):
        """event_id_a should always be < event_id_b."""
        events = [
            _make_event("z-event", source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("a-event", source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        result = generate_candidates_from_events(events, min_title_sim=0.0)
        assert len(result) >= 1
        for candidate in result:
            assert candidate.event_id_a < candidate.event_id_b


class TestGeoBlockingCandidates:
    def test_geo_blocking_candidates(self):
        """Events in the same geo grid but different cities should be candidates."""
        events = [
            _make_event(
                "e1",
                source_code="bwb",
                location_city="Freiburg",
                blocking_keys=["dg|2026-02-12|48.15|7.80"],
            ),
            _make_event(
                "e2",
                source_code="emt",
                location_city="Merzhausen",
                blocking_keys=["dg|2026-02-12|48.15|7.80"],
            ),
        ]
        result = generate_candidates_from_events(events, min_title_sim=0.0)
        assert len(result) >= 1
        pair = result[0]
        assert pair.event_a_city != pair.event_b_city


class TestHardNegativeSampling:
    def test_hard_negative_sampling(self):
        """Some pairs below min_title_sim should be included as hard negatives."""
        events = [
            _make_event(
                "e1",
                title="Konzert A",
                title_normalized="konzert a",
                source_code="bwb",
                blocking_keys=["dc|2026-02-12|freiburg"],
            ),
            _make_event(
                "e2",
                title="Voellig anderes Event B",
                title_normalized="voellig anderes event b",
                source_code="emt",
                blocking_keys=["dc|2026-02-12|freiburg"],
            ),
            _make_event(
                "e3",
                title="Noch etwas ganz anderes C",
                title_normalized="noch etwas ganz anderes c",
                source_code="xyz",
                blocking_keys=["dc|2026-02-12|freiburg"],
            ),
        ]
        # Use a high threshold so all pairs are below it, then request hard negatives
        result = generate_candidates_from_events(
            events, min_title_sim=0.99, hard_negative_ratio=1.0
        )
        # All pairs are below threshold, but hard_negative_ratio=1.0 should include them all
        assert len(result) > 0
        # All included should have low similarity
        for c in result:
            assert c.title_sim < 0.99

    def test_hard_negative_seeded_reproducibility(self):
        """Hard negative sampling should be reproducible with the same seed."""
        events = [
            _make_event(f"e{i}", title=f"unique title {i}", title_normalized=f"unique title {i}",
                        source_code="bwb" if i % 2 == 0 else "emt",
                        blocking_keys=["dc|2026-02-12|freiburg"])
            for i in range(20)
        ]
        result1 = generate_candidates_from_events(events, min_title_sim=0.99, hard_negative_ratio=0.5, seed=42)
        result2 = generate_candidates_from_events(events, min_title_sim=0.99, hard_negative_ratio=0.5, seed=42)
        assert result1 == result2
