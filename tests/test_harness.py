"""Tests for the evaluation harness."""

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from event_dedup.evaluation.harness import (
    EvaluationConfig,
    generate_predictions_from_events,
    load_ground_truth,
)
from event_dedup.models.file_ingestion import FileIngestion
from event_dedup.models.ground_truth import GroundTruthPair
from event_dedup.models.source_event import SourceEvent


def _make_event(
    event_id: str,
    title_normalized: str = "test event",
    source_code: str = "bwb",
    blocking_keys: list[str] | None = None,
) -> dict:
    """Helper to create a synthetic event dict for pure function testing."""
    return {
        "id": event_id,
        "title_normalized": title_normalized,
        "source_code": source_code,
        "blocking_keys": blocking_keys or [],
    }


class TestGeneratePredictionsRespectsThreshold:
    def test_high_threshold_filters_pairs(self):
        """With a high threshold, dissimilar pairs should not be predicted."""
        events = [
            _make_event("e1", title_normalized="sommerkonzert im park",
                        source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", title_normalized="bauernmarkt am muensterplatz",
                        source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        config = EvaluationConfig(title_sim_threshold=0.90)
        result = generate_predictions_from_events(events, config)
        assert len(result) == 0

    def test_low_threshold_includes_pairs(self):
        """With a low threshold, even somewhat different titles should match."""
        events = [
            _make_event("e1", title_normalized="sommerkonzert im park",
                        source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", title_normalized="sommerkonzert im stadtpark",
                        source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        config = EvaluationConfig(title_sim_threshold=0.50)
        result = generate_predictions_from_events(events, config)
        assert ("e1", "e2") in result

    def test_identical_titles_always_match(self):
        """Identical normalized titles should always be predicted as same."""
        events = [
            _make_event("e1", title_normalized="konzert im park",
                        source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", title_normalized="konzert im park",
                        source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        config = EvaluationConfig(title_sim_threshold=0.99)
        result = generate_predictions_from_events(events, config)
        assert ("e1", "e2") in result


class TestThresholdSweepReturnsMultipleResults:
    def test_threshold_sweep_returns_multiple_results(self):
        """Sweep with multiple thresholds should return one result per threshold."""
        events = [
            _make_event("e1", title_normalized="konzert im park",
                        source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", title_normalized="konzert im park",
                        source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        thresholds = [0.50, 0.70, 0.90]
        results = []
        for t in thresholds:
            config = EvaluationConfig(title_sim_threshold=t)
            preds = generate_predictions_from_events(events, config)
            results.append((t, preds))

        assert len(results) == 3
        # All thresholds below 1.0 should find the identical pair
        for t, preds in results:
            assert ("e1", "e2") in preds


class TestEvaluationIdentifiesFalsePositives:
    def test_evaluation_identifies_false_positives(self):
        """A predicted pair that is labeled 'different' is a false positive."""
        events = [
            _make_event("e1", title_normalized="konzert im park",
                        source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", title_normalized="konzert im park",
                        source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        config = EvaluationConfig(title_sim_threshold=0.80)
        predicted = generate_predictions_from_events(events, config)

        # Ground truth says they are different
        gt_same: set[tuple[str, str]] = set()
        gt_diff = {("e1", "e2")}

        from event_dedup.evaluation.metrics import compute_metrics
        metrics = compute_metrics(predicted, gt_same, gt_diff)

        assert metrics.false_positives == 1
        assert metrics.true_positives == 0


class TestEvaluationIdentifiesFalseNegatives:
    def test_evaluation_identifies_false_negatives(self):
        """A ground truth 'same' pair not predicted is a false negative."""
        events = [
            _make_event("e1", title_normalized="voellig anderer titel a",
                        source_code="bwb", blocking_keys=["dc|2026-02-12|freiburg"]),
            _make_event("e2", title_normalized="voellig anderer titel b",
                        source_code="emt", blocking_keys=["dc|2026-02-12|freiburg"]),
        ]
        config = EvaluationConfig(title_sim_threshold=0.95)
        predicted = generate_predictions_from_events(events, config)

        # Ground truth says they are the same (despite low similarity)
        gt_same = {("e1", "e2")}
        gt_diff: set[tuple[str, str]] = set()

        from event_dedup.evaluation.metrics import compute_metrics
        metrics = compute_metrics(predicted, gt_same, gt_diff)

        assert metrics.false_negatives == 1
        assert metrics.recall == 0.0


class TestLoadGroundTruthSeparatesLabels:
    @pytest.fixture
    async def session_with_ground_truth(self, test_session_factory):
        """Insert source events and ground truth pairs for testing."""
        async with test_session_factory() as session:
            # Create a file ingestion record first
            ingestion = FileIngestion(
                filename="test.json",
                file_hash="testhash123",
                source_code="bwb",
                event_count=3,
                status="completed",
            )
            session.add(ingestion)
            await session.flush()

            # Create source events
            for eid in ["evt-a", "evt-b", "evt-c", "evt-d"]:
                event = SourceEvent(
                    id=eid,
                    file_ingestion_id=ingestion.id,
                    title=f"Event {eid}",
                    source_type="artikel",
                    source_code="bwb",
                )
                session.add(event)
            await session.flush()

            # Create ground truth pairs (canonical ordering: a < b)
            same_pair = GroundTruthPair(
                event_id_a="evt-a",
                event_id_b="evt-b",
                label="same",
                title_similarity=0.95,
            )
            diff_pair = GroundTruthPair(
                event_id_a="evt-c",
                event_id_b="evt-d",
                label="different",
                title_similarity=0.20,
            )
            session.add_all([same_pair, diff_pair])
            await session.commit()

            yield session

    async def test_load_ground_truth_separates_labels(self, session_with_ground_truth):
        """load_ground_truth should return separate sets for same and different."""
        gt_same, gt_diff = await load_ground_truth(session_with_ground_truth)

        assert ("evt-a", "evt-b") in gt_same
        assert ("evt-c", "evt-d") in gt_diff
        assert len(gt_same) == 1
        assert len(gt_diff) == 1
