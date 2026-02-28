"""Integration tests for the matching pipeline orchestrator."""

import pytest

from event_dedup.matching.config import CategoryWeightsConfig, MatchingConfig, ScoringWeights, ThresholdConfig
from event_dedup.matching.pipeline import (
    MatchDecisionRecord,
    MatchResult,
    get_match_pairs,
    resolve_weights,
    score_candidate_pairs,
)


def make_event(
    id: str,
    title_normalized: str,
    source_code: str,
    blocking_keys: list[str],
    dates: list[dict],
    geo_latitude: float | None = None,
    geo_longitude: float | None = None,
    geo_confidence: float | None = None,
    short_description_normalized: str | None = None,
) -> dict:
    """Create an event dict matching the scorer interface.

    The ``title`` field is set from ``title_normalized`` and
    ``description`` is set from ``short_description_normalized`` to
    match what the scorers expect.
    """
    evt: dict = {
        "id": id,
        "title": title_normalized,
        "source_code": source_code,
        "blocking_keys": blocking_keys,
        "dates": dates,
    }
    if geo_latitude is not None:
        evt["geo_latitude"] = geo_latitude
    if geo_longitude is not None:
        evt["geo_longitude"] = geo_longitude
    if geo_confidence is not None:
        evt["geo_confidence"] = geo_confidence
    if short_description_normalized is not None:
        evt["description"] = short_description_normalized
    return evt


class TestScoreCandidatePairs:
    """Tests for the full scoring pipeline."""

    def test_identical_events_match(self) -> None:
        """Two nearly-identical events from different sources -> match."""
        events = [
            make_event(
                id="a1",
                title_normalized="fasnetumzug ettenheim",
                source_code="src_a",
                blocking_keys=["2026-03-01:ettenheim"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                geo_latitude=48.256,
                geo_longitude=7.812,
                geo_confidence=0.95,
                short_description_normalized="grosser fasnetumzug durch ettenheim mit vielen zuenftigen gruppen",
            ),
            make_event(
                id="b1",
                title_normalized="fasnetumzug ettenheim",
                source_code="src_b",
                blocking_keys=["2026-03-01:ettenheim"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                geo_latitude=48.256,
                geo_longitude=7.812,
                geo_confidence=0.95,
                short_description_normalized="grosser fasnetumzug durch ettenheim mit vielen zuenftigen gruppen",
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        assert len(result.decisions) == 1
        dec = result.decisions[0]
        assert dec.decision == "match"
        assert dec.combined_score_value >= 0.75
        assert dec.signals.date == 1.0
        assert dec.signals.geo == 1.0
        assert dec.signals.title == 1.0
        assert dec.tier == "deterministic"

    def test_completely_different_no_match(self) -> None:
        """Two completely different events sharing a blocking key -> no_match."""
        events = [
            make_event(
                id="a1",
                title_normalized="fasnetumzug ettenheim",
                source_code="src_a",
                blocking_keys=["2026-03-01:ettenheim"],
                dates=[{"date": "2026-03-01"}],
                geo_latitude=48.256,
                geo_longitude=7.812,
                geo_confidence=0.95,
                short_description_normalized="grosser fasnetumzug durch ettenheim",
            ),
            make_event(
                id="b1",
                title_normalized="konzert jazz quartett offenburg",
                source_code="src_b",
                blocking_keys=["2026-03-01:ettenheim"],
                dates=[{"date": "2026-04-15"}],
                geo_latitude=49.500,
                geo_longitude=9.200,
                geo_confidence=0.95,
                short_description_normalized="jazznacht im salmen offenburg mit quartett",
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        assert len(result.decisions) == 1
        dec = result.decisions[0]
        assert dec.decision == "no_match"
        assert dec.combined_score_value <= 0.35

    def test_ambiguous_pair(self) -> None:
        """Partially similar events -> ambiguous decision."""
        events = [
            make_event(
                id="a1",
                title_normalized="fasnetumzug nordweil",
                source_code="src_a",
                blocking_keys=["2026-03-01:nordweil"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                geo_latitude=48.1,
                geo_longitude=7.8,
                geo_confidence=0.90,
            ),
            make_event(
                id="b1",
                title_normalized="nordwiler narrenfahrplan mit umzug",
                source_code="src_b",
                blocking_keys=["2026-03-01:nordweil"],
                dates=[{"date": "2026-03-01", "start_time": "14:00"}],
                geo_latitude=48.1,
                geo_longitude=7.8,
                geo_confidence=0.90,
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        assert len(result.decisions) == 1
        dec = result.decisions[0]
        # With high date/geo but low-medium title similarity (~0.41)
        # and neutral description (both missing -> 0.5), the combined
        # score lands in the ambiguous zone
        assert dec.decision == "ambiguous"
        assert 0.35 < dec.combined_score_value < 0.75

    def test_pipeline_stats_sum(self) -> None:
        """match_count + ambiguous_count + no_match_count == len(decisions)."""
        events = [
            make_event(
                id="a1",
                title_normalized="fasnetumzug ettenheim",
                source_code="src_a",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_event(
                id="a2",
                title_normalized="konzert im park",
                source_code="src_a",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_event(
                id="b1",
                title_normalized="fasnetumzug ettenheim",
                source_code="src_b",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_event(
                id="b2",
                title_normalized="konzert im park",
                source_code="src_b",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_event(
                id="c1",
                title_normalized="vortrag technologie",
                source_code="src_c",
                blocking_keys=["key1"],
                dates=[{"date": "2026-05-15"}],
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        assert result.match_count + result.ambiguous_count + result.no_match_count == len(
            result.decisions
        )
        assert result.pair_stats.blocked_pairs == len(result.decisions)

    def test_get_match_pairs_returns_only_matches(self) -> None:
        """get_match_pairs returns only pairs with decision 'match'."""
        events = [
            make_event(
                id="a1",
                title_normalized="fasnetumzug ettenheim",
                source_code="src_a",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
                geo_latitude=48.256,
                geo_longitude=7.812,
                geo_confidence=0.95,
                short_description_normalized="grosser umzug",
            ),
            make_event(
                id="b1",
                title_normalized="fasnetumzug ettenheim",
                source_code="src_b",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
                geo_latitude=48.256,
                geo_longitude=7.812,
                geo_confidence=0.95,
                short_description_normalized="grosser umzug",
            ),
            make_event(
                id="c1",
                title_normalized="jazz quartett offenburg",
                source_code="src_c",
                blocking_keys=["key1"],
                dates=[{"date": "2026-06-01"}],
                geo_latitude=50.0,
                geo_longitude=10.0,
                geo_confidence=0.95,
                short_description_normalized="jazzkonzert",
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        match_pairs = get_match_pairs(result)
        # a1-b1 should match (identical), c1 should not match either
        assert ("a1", "b1") in match_pairs
        for pair in match_pairs:
            matching_dec = [
                d
                for d in result.decisions
                if (d.event_id_a, d.event_id_b) == pair
            ]
            assert len(matching_dec) == 1
            assert matching_dec[0].decision == "match"

    def test_cross_source_enforcement(self) -> None:
        """Same-source events sharing a blocking key -> 0 decisions."""
        events = [
            make_event(
                id="a1",
                title_normalized="fasnetumzug",
                source_code="src_a",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_event(
                id="a2",
                title_normalized="fasnetumzug",
                source_code="src_a",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        assert len(result.decisions) == 0
        assert result.match_count == 0
        assert result.ambiguous_count == 0
        assert result.no_match_count == 0

    def test_config_high_threshold_no_matches(self) -> None:
        """Custom config with very high threshold -> no match decisions.

        Even events that would normally match are rejected when the
        threshold is set above their combined score.
        """
        config = MatchingConfig(thresholds=ThresholdConfig(high=0.99, low=0.35))
        # Use events that are similar but NOT identical so combined < 0.99
        events = [
            make_event(
                id="a1",
                title_normalized="fasnetumzug ettenheim innenstadt",
                source_code="src_a",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
                geo_latitude=48.256,
                geo_longitude=7.812,
                geo_confidence=0.95,
                short_description_normalized="grosser fasnetumzug durch die ettenheimer innenstadt",
            ),
            make_event(
                id="b1",
                title_normalized="ettenheim fasnetumzug grosser",
                source_code="src_b",
                blocking_keys=["key1"],
                dates=[{"date": "2026-03-01"}],
                geo_latitude=48.257,
                geo_longitude=7.813,
                geo_confidence=0.95,
                short_description_normalized="umzug in ettenheim zum fasnet",
            ),
        ]
        result = score_candidate_pairs(events, config)
        assert result.match_count == 0
        assert all(d.decision != "match" for d in result.decisions)

    def test_decision_record_fields(self) -> None:
        """MatchDecisionRecord contains all expected fields."""
        events = [
            make_event(
                id="a1",
                title_normalized="test event",
                source_code="src_a",
                blocking_keys=["k1"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_event(
                id="b1",
                title_normalized="test event",
                source_code="src_b",
                blocking_keys=["k1"],
                dates=[{"date": "2026-03-01"}],
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        dec = result.decisions[0]
        assert isinstance(dec, MatchDecisionRecord)
        assert dec.event_id_a == "a1"
        assert dec.event_id_b == "b1"
        assert hasattr(dec.signals, "date")
        assert hasattr(dec.signals, "geo")
        assert hasattr(dec.signals, "title")
        assert hasattr(dec.signals, "description")
        assert isinstance(dec.combined_score_value, float)
        assert dec.decision in {"match", "no_match", "ambiguous"}
        assert dec.tier == "deterministic"

    def test_match_result_type(self) -> None:
        """score_candidate_pairs returns a MatchResult."""
        events = [
            make_event(
                id="a1",
                title_normalized="test",
                source_code="src_a",
                blocking_keys=["k1"],
                dates=[{"date": "2026-03-01"}],
            ),
            make_event(
                id="b1",
                title_normalized="test",
                source_code="src_b",
                blocking_keys=["k1"],
                dates=[{"date": "2026-03-01"}],
            ),
        ]
        result = score_candidate_pairs(events, MatchingConfig())
        assert isinstance(result, MatchResult)
        assert isinstance(result.decisions, list)
        assert isinstance(result.match_count, int)

    def test_empty_events(self) -> None:
        """Empty event list -> empty result."""
        result = score_candidate_pairs([], MatchingConfig())
        assert len(result.decisions) == 0
        assert result.match_count == 0
        assert result.ambiguous_count == 0
        assert result.no_match_count == 0


class TestResolveWeights:
    """Tests for category-aware weight resolution."""

    def _config_with_categories(self) -> MatchingConfig:
        return MatchingConfig(
            category_weights=CategoryWeightsConfig(
                priority=["fasnacht", "versammlung"],
                overrides={
                    "fasnacht": ScoringWeights(date=0.30, geo=0.30, title=0.25, description=0.15),
                    "versammlung": ScoringWeights(date=0.25, geo=0.20, title=0.40, description=0.15),
                }
            )
        )

    def test_shared_category_uses_override(self) -> None:
        """Events sharing a priority category get override weights."""
        config = self._config_with_categories()
        evt_a = {"categories": ["fasnacht", "kinder"]}
        evt_b = {"categories": ["fasnacht"]}
        weights = resolve_weights(evt_a, evt_b, config)
        assert weights.title == 0.25
        assert weights.geo == 0.30

    def test_no_shared_category_uses_default(self) -> None:
        """Events with no shared category get default weights."""
        config = self._config_with_categories()
        evt_a = {"categories": ["musik"]}
        evt_b = {"categories": ["sport"]}
        weights = resolve_weights(evt_a, evt_b, config)
        assert weights == config.scoring

    def test_no_categories_uses_default(self) -> None:
        """Events without categories field get default weights."""
        config = self._config_with_categories()
        evt_a: dict = {}
        evt_b = {"categories": ["fasnacht"]}
        weights = resolve_weights(evt_a, evt_b, config)
        assert weights == config.scoring

    def test_none_categories_uses_default(self) -> None:
        """Events with None categories get default weights."""
        config = self._config_with_categories()
        evt_a = {"categories": None}
        evt_b = {"categories": ["fasnacht"]}
        weights = resolve_weights(evt_a, evt_b, config)
        assert weights == config.scoring

    def test_priority_order_respected(self) -> None:
        """First matching priority category wins."""
        config = self._config_with_categories()
        evt_a = {"categories": ["fasnacht", "versammlung"]}
        evt_b = {"categories": ["fasnacht", "versammlung"]}
        weights = resolve_weights(evt_a, evt_b, config)
        assert weights.title == 0.25  # fasnacht weights (higher priority)

    def test_empty_priority_uses_default(self) -> None:
        """Empty priority list means no overrides."""
        config = MatchingConfig()
        evt_a = {"categories": ["fasnacht"]}
        evt_b = {"categories": ["fasnacht"]}
        weights = resolve_weights(evt_a, evt_b, config)
        assert weights == config.scoring

    def test_shared_category_not_in_overrides_uses_default(self) -> None:
        """Shared category in priority but not in overrides uses default."""
        config = MatchingConfig(
            category_weights=CategoryWeightsConfig(
                priority=["musik"],
                overrides={}
            )
        )
        evt_a = {"categories": ["musik"]}
        evt_b = {"categories": ["musik"]}
        weights = resolve_weights(evt_a, evt_b, config)
        assert weights == config.scoring

    def test_category_aware_scoring_integration(self) -> None:
        """Full pipeline with category-aware weights produces different scores."""
        events = [
            make_event(
                id="a1",
                title_normalized="fastnachtumzug waldkirch",
                source_code="src_a",
                blocking_keys=["2026-03-01:waldkirch"],
                dates=[{"date": "2026-03-01"}],
                geo_latitude=48.09,
                geo_longitude=7.96,
                geo_confidence=0.95,
            ),
            make_event(
                id="b1",
                title_normalized="grosser umzug waldkirch",
                source_code="src_b",
                blocking_keys=["2026-03-01:waldkirch"],
                dates=[{"date": "2026-03-01"}],
                geo_latitude=48.09,
                geo_longitude=7.96,
                geo_confidence=0.95,
            ),
        ]
        events[0]["categories"] = ["fasnacht"]
        events[1]["categories"] = ["fasnacht"]

        config_with_cats = MatchingConfig(
            category_weights=CategoryWeightsConfig(
                priority=["fasnacht"],
                overrides={
                    "fasnacht": ScoringWeights(date=0.30, geo=0.30, title=0.25, description=0.15),
                }
            )
        )
        config_without_cats = MatchingConfig()

        result_with = score_candidate_pairs(events, config_with_cats)
        result_without = score_candidate_pairs(events, config_without_cats)

        assert len(result_with.decisions) == 1
        assert len(result_without.decisions) == 1
        assert result_with.decisions[0].combined_score_value != result_without.decisions[0].combined_score_value
