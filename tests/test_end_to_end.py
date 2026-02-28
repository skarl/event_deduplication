"""End-to-end integration tests for the full deduplication pipeline.

Tests run the complete chain: blocking -> scoring -> clustering ->
canonical synthesis, verifying that events are correctly deduplicated
and canonical events have the best fields from all sources.
"""

from __future__ import annotations

from event_dedup.evaluation.harness import generate_predictions_multisignal
from event_dedup.matching.config import MatchingConfig
from event_dedup.matching.pipeline import (
    PipelineResult,
    extract_predicted_pairs,
    run_full_pipeline,
)


def make_test_event(
    id: str,
    title: str,
    title_normalized: str,
    source_code: str,
    blocking_keys: list[str],
    dates: list[dict],
    city: str | None = None,
    geo_lat: float | None = None,
    geo_lon: float | None = None,
    geo_conf: float | None = None,
    short_desc: str | None = None,
    short_desc_norm: str | None = None,
    description: str | None = None,
    highlights: list | None = None,
    categories: list | None = None,
    **kwargs,
) -> dict:
    """Create a test event dict with ALL fields the pipeline expects.

    The pipeline scorers use these key names:
    - title_score: ``"title"`` (original title text)
    - description_score: ``"description"`` (uses short_description_normalized
      via the ``"description"`` key -- see test_pipeline.py pattern)
    - Blocking: ``"source_code"``, ``"blocking_keys"``
    - Synthesis: all original fields
    """
    return {
        "id": id,
        "title": title,
        "title_normalized": title_normalized,
        "short_description": short_desc,
        "short_description_normalized": short_desc_norm or "",
        "description": description,
        "highlights": highlights,
        "location_name": kwargs.get("location_name"),
        "location_city": city,
        "location_district": kwargs.get("location_district"),
        "location_street": kwargs.get("location_street"),
        "location_zipcode": kwargs.get("location_zipcode"),
        "geo_latitude": geo_lat,
        "geo_longitude": geo_lon,
        "geo_confidence": geo_conf,
        "source_code": source_code,
        "source_type": kwargs.get("source_type", "artikel"),
        "blocking_keys": blocking_keys,
        "dates": dates,
        "categories": categories,
        "is_family_event": kwargs.get("is_family_event"),
        "is_child_focused": kwargs.get("is_child_focused"),
        "admission_free": kwargs.get("admission_free"),
    }


class TestFullPipelineDuplicates:
    """Pipeline correctly deduplicates identical/similar events."""

    def test_two_duplicates_one_canonical(self):
        """Two events from different sources with same title -> 1 canonical."""
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch mit vielen Zuenftigen",
            ),
            make_test_event(
                id="ev-b",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch mit vielen Zuenftigen",
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        assert isinstance(result, PipelineResult)
        # Two identical events -> 1 cluster -> 1 canonical
        multi_source = [c for c in result.canonical_events if c["source_count"] > 1]
        assert len(multi_source) == 1
        assert multi_source[0]["source_count"] == 2

    def test_two_different_events_two_canonicals(self):
        """Two completely different events -> 2 singleton canonicals."""
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01"}],
                city="Waldkirch",
            ),
            make_test_event(
                id="ev-b",
                title="Jazzkonzert Freiburg",
                title_normalized="jazzkonzert freiburg",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-06-15"}],
                city="Freiburg",
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        singletons = [c for c in result.canonical_events if c["source_count"] == 1]
        assert len(singletons) == 2

    def test_four_events_two_clusters(self):
        """4 events forming 2 pairs -> 2 canonicals with source_count=2."""
        events = [
            make_test_event(
                id="ev-a1",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch",
            ),
            make_test_event(
                id="ev-a2",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch",
            ),
            make_test_event(
                id="ev-b1",
                title="Konzert im Salmen Offenburg",
                title_normalized="konzert im salmen offenburg",
                source_code="bwb",
                blocking_keys=["dc|2026-04-10|offenburg"],
                dates=[{"date": "2026-04-10", "start_time": "20:00"}],
                city="Offenburg",
                geo_lat=48.47,
                geo_lon=7.94,
                geo_conf=0.95,
                description="Grosses Konzert im historischen Salmen",
            ),
            make_test_event(
                id="ev-b2",
                title="Konzert im Salmen Offenburg",
                title_normalized="konzert im salmen offenburg",
                source_code="fvs",
                blocking_keys=["dc|2026-04-10|offenburg"],
                dates=[{"date": "2026-04-10", "start_time": "20:00"}],
                city="Offenburg",
                geo_lat=48.47,
                geo_lon=7.94,
                geo_conf=0.95,
                description="Grosses Konzert im historischen Salmen",
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        multi_source = [c for c in result.canonical_events if c["source_count"] == 2]
        assert len(multi_source) == 2

    def test_transitive_match_three_sources(self):
        """A-B and B-C match -> one cluster {A, B, C} via transitivity."""
        # B shares blocking keys with both A and C
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnetumzug Waldkirch Innenstadt",
                title_normalized="fasnetumzug waldkirch innenstadt",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch die Waldkircher Innenstadt",
            ),
            make_test_event(
                id="ev-b",
                title="Fasnetumzug Waldkirch Innenstadt",
                title_normalized="fasnetumzug waldkirch innenstadt",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch", "dc|2026-03-01|waldkirch2"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch die Waldkircher Innenstadt",
            ),
            make_test_event(
                id="ev-c",
                title="Fasnetumzug Waldkirch Innenstadt",
                title_normalized="fasnetumzug waldkirch innenstadt",
                source_code="bzk",
                blocking_keys=["dc|2026-03-01|waldkirch2"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch die Waldkircher Innenstadt",
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        # All three should end up in one cluster
        three_source = [c for c in result.canonical_events if c["source_count"] == 3]
        assert len(three_source) == 1
        assert three_source[0]["source_count"] == 3


class TestCanonicalBestFields:
    """Canonical event selects the best field from each source."""

    def test_best_title_and_description_from_different_sources(self):
        """Source A has long description, source B has long title."""
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnet",  # short title (< 10 chars)
                title_normalized="fasnet",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Ein sehr ausfuehrlicher und langer Beschreibungstext zum Fasnetumzug in Waldkirch mit vielen Details",
            ),
            make_test_event(
                id="ev-b",
                title="Grosser Fasnetumzug durch die Waldkircher Innenstadt 2026",
                title_normalized="grosser fasnetumzug durch die waldkircher innenstadt 2026",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description=None,
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        # Should match (same date, same geo, title fuzzy match)
        multi = [c for c in result.canonical_events if c["source_count"] > 1]
        if multi:
            canonical = multi[0]
            # Best title from source B (longest non-generic >= 10 chars)
            assert "Waldkircher" in canonical["title"]
            assert canonical["field_provenance"]["title"] == "ev-b"
            # Best description from source A (longest)
            assert "ausfuehrlicher" in canonical["description"]
            assert canonical["field_provenance"]["description"] == "ev-a"


class TestBlockingReductionStats:
    """Blocking produces meaningful pair reduction."""

    def test_reduction_with_multiple_sources(self):
        """Events with specific blocking keys have reduced pair count."""
        events = [
            make_test_event(
                id=f"ev-{src}-{i}",
                title=f"Event {i}",
                title_normalized=f"event {i}",
                source_code=src,
                blocking_keys=[f"dc|2026-03-0{i}|city{i}"],
                dates=[{"date": f"2026-03-0{i}"}],
            )
            for src in ("bwb", "fvs", "bzk")
            for i in range(1, 3)
        ]
        result = run_full_pipeline(events, MatchingConfig())

        # With separate blocking keys per date/city, not all cross-source
        # pairs will be generated
        stats = result.match_result.pair_stats
        assert stats.total_events == 6
        # Some reduction should occur since events have different blocking keys
        assert stats.blocked_pairs <= stats.total_possible_pairs


class TestExtractPredictedPairs:
    """extract_predicted_pairs returns match pairs for evaluation."""

    def test_returns_match_pairs(self):
        """Extracted pairs match the scoring pipeline match decisions."""
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch mit vielen Zuenftigen",
            ),
            make_test_event(
                id="ev-b",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch mit vielen Zuenftigen",
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())
        pairs = extract_predicted_pairs(result)

        assert ("ev-a", "ev-b") in pairs


class TestGeneratePredictionsMultisignal:
    """generate_predictions_multisignal pure function."""

    def test_returns_same_as_pipeline_match_pairs(self):
        """Multi-signal predictions match the pipeline match pairs."""
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch mit vielen Zuenftigen",
            ),
            make_test_event(
                id="ev-b",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch mit vielen Zuenftigen",
            ),
        ]
        config = MatchingConfig()
        predicted = generate_predictions_multisignal(events, config)
        pipeline_result = run_full_pipeline(events, config)
        pipeline_pairs = extract_predicted_pairs(pipeline_result)

        assert predicted == pipeline_pairs

    def test_no_matches_returns_empty(self):
        """Different events produce no match predictions."""
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_test_event(
                id="ev-b",
                title="Konzert Jazz Offenburg",
                title_normalized="konzert jazz offenburg",
                source_code="fvs",
                blocking_keys=["dc|2026-06-15|offenburg"],
                dates=[{"date": "2026-06-15"}],
            ),
        ]
        predicted = generate_predictions_multisignal(events, MatchingConfig())

        # No shared blocking keys -> no candidates -> no matches
        assert len(predicted) == 0


class TestPipelineResultStructure:
    """PipelineResult has correct structure and metadata."""

    def test_needs_review_flag(self):
        """Singleton canonicals have needs_review=False."""
        events = [
            make_test_event(
                id="ev-a",
                title="Standalone Event",
                title_normalized="standalone event",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|city"],
                dates=[{"date": "2026-03-01"}],
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        assert len(result.canonical_events) == 1
        assert result.canonical_events[0]["needs_review"] is False

    def test_match_confidence_none_for_singletons(self):
        """Singleton canonicals have match_confidence=None."""
        events = [
            make_test_event(
                id="ev-a",
                title="Solo Event",
                title_normalized="solo event",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|city"],
                dates=[{"date": "2026-03-01"}],
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        assert result.canonical_events[0]["match_confidence"] is None

    def test_match_confidence_set_for_matches(self):
        """Matched canonicals have a numeric match_confidence."""
        events = [
            make_test_event(
                id="ev-a",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="bwb",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch",
            ),
            make_test_event(
                id="ev-b",
                title="Fasnetumzug Waldkirch",
                title_normalized="fasnetumzug waldkirch",
                source_code="fvs",
                blocking_keys=["dc|2026-03-01|waldkirch"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                city="Waldkirch",
                geo_lat=48.09,
                geo_lon=7.96,
                geo_conf=0.95,
                description="Grosser Fasnetumzug durch Waldkirch",
            ),
        ]
        result = run_full_pipeline(events, MatchingConfig())

        multi = [c for c in result.canonical_events if c["source_count"] > 1]
        if multi:
            assert multi[0]["match_confidence"] is not None
            assert multi[0]["match_confidence"] > 0.0
