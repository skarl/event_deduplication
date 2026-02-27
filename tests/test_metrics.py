"""Tests for evaluation metrics (precision, recall, F1)."""

import pytest

from event_dedup.evaluation.metrics import MetricsResult, compute_metrics, format_metrics


class TestPerfectScore:
    def test_perfect_score(self):
        """All same pairs predicted correctly -> P=1, R=1, F1=1."""
        gt_same = {("a", "b"), ("c", "d")}
        gt_diff = {("e", "f")}
        predicted = {("a", "b"), ("c", "d")}

        result = compute_metrics(predicted, gt_same, gt_diff)

        assert result.precision == 1.0
        assert result.recall == 1.0
        assert result.f1 == 1.0
        assert result.true_positives == 2
        assert result.false_positives == 0
        assert result.false_negatives == 0
        assert result.true_negatives == 1


class TestAllFalsePositives:
    def test_all_false_positives(self):
        """Predicting pairs that are labeled different -> low precision."""
        gt_same = {("a", "b")}
        gt_diff = {("c", "d"), ("e", "f")}
        predicted = {("a", "b"), ("c", "d"), ("e", "f")}

        result = compute_metrics(predicted, gt_same, gt_diff)

        assert result.true_positives == 1
        assert result.false_positives == 2
        assert result.precision == pytest.approx(1 / 3)
        assert result.recall == 1.0


class TestAllFalseNegatives:
    def test_all_false_negatives(self):
        """Predicting nothing -> R=0, F1=0."""
        gt_same = {("a", "b"), ("c", "d")}
        gt_diff = {("e", "f")}
        predicted: set[tuple[str, str]] = set()

        result = compute_metrics(predicted, gt_same, gt_diff)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0
        assert result.false_negatives == 2
        assert result.true_negatives == 1


class TestMixedResults:
    def test_mixed_results(self):
        """TP=3, FP=1, FN=2 -> known precision, recall, F1."""
        gt_same = {("a", "b"), ("c", "d"), ("e", "f"), ("g", "h"), ("i", "j")}
        gt_diff = {("k", "l"), ("m", "n")}

        # Predict 4 pairs: 3 correct (TP), 1 from gt_diff (FP)
        predicted = {("a", "b"), ("c", "d"), ("e", "f"), ("k", "l")}

        result = compute_metrics(predicted, gt_same, gt_diff)

        assert result.true_positives == 3
        assert result.false_positives == 1
        assert result.false_negatives == 2  # (g,h) and (i,j) missed
        assert result.true_negatives == 1  # (m,n) correctly not predicted

        assert result.precision == pytest.approx(3 / 4)  # 0.75
        assert result.recall == pytest.approx(3 / 5)  # 0.6
        expected_f1 = 2 * 0.75 * 0.6 / (0.75 + 0.6)
        assert result.f1 == pytest.approx(expected_f1)


class TestCanonicalOrdering:
    def test_canonical_ordering(self):
        """(b, a) and (a, b) should be treated as the same pair."""
        gt_same = {("b", "a")}  # reversed
        gt_diff = set()
        predicted = {("a", "b")}  # canonical

        result = compute_metrics(predicted, gt_same, gt_diff)

        assert result.true_positives == 1
        assert result.precision == 1.0
        assert result.recall == 1.0


class TestEmptyGroundTruth:
    def test_empty_ground_truth(self):
        """No ground truth -> 0.0 metrics."""
        gt_same: set[tuple[str, str]] = set()
        gt_diff: set[tuple[str, str]] = set()
        predicted = {("a", "b")}

        result = compute_metrics(predicted, gt_same, gt_diff)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0


class TestEmptyPredictions:
    def test_empty_predictions(self):
        """No predictions -> P=0, R=0, F1=0."""
        gt_same = {("a", "b")}
        gt_diff = {("c", "d")}
        predicted: set[tuple[str, str]] = set()

        result = compute_metrics(predicted, gt_same, gt_diff)

        assert result.precision == 0.0
        assert result.recall == 0.0
        assert result.f1 == 0.0


class TestFormatMetrics:
    def test_format_metrics_returns_string(self):
        """format_metrics should return a non-empty formatted string."""
        result = MetricsResult(
            precision=0.75,
            recall=0.60,
            f1=0.6667,
            true_positives=3,
            false_positives=1,
            false_negatives=2,
            true_negatives=1,
            total_ground_truth_same=5,
            total_ground_truth_different=2,
            total_predicted_same=4,
        )
        formatted = format_metrics(result)
        assert "Precision" in formatted
        assert "Recall" in formatted
        assert "F1 Score" in formatted
        assert "0.75" in formatted
