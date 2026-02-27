"""Evaluation metrics for event deduplication.

Computes precision, recall, and F1 score by comparing predicted
duplicate pairs against ground truth labels.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class MetricsResult:
    """Container for evaluation metrics."""

    precision: float
    recall: float
    f1: float
    true_positives: int
    false_positives: int
    false_negatives: int
    true_negatives: int
    total_ground_truth_same: int
    total_ground_truth_different: int
    total_predicted_same: int


def _canonicalize(pair: tuple[str, str]) -> tuple[str, str]:
    """Ensure canonical ordering (a < b) for a pair of event IDs."""
    if pair[0] > pair[1]:
        return (pair[1], pair[0])
    return pair


def compute_metrics(
    predicted_same: set[tuple[str, str]],
    ground_truth_same: set[tuple[str, str]],
    ground_truth_different: set[tuple[str, str]],
) -> MetricsResult:
    """Compute precision, recall, and F1 for deduplication predictions.

    All pairs are normalized to canonical ordering (event_id_a < event_id_b)
    before comparison.

    Args:
        predicted_same: Set of (event_id_a, event_id_b) pairs predicted
            as duplicates.
        ground_truth_same: Set of (event_id_a, event_id_b) pairs labeled
            as the same event.
        ground_truth_different: Set of (event_id_a, event_id_b) pairs
            labeled as different events.

    Returns:
        MetricsResult with precision, recall, F1, and confusion matrix counts.
    """
    # Normalize all pairs to canonical ordering
    pred = {_canonicalize(p) for p in predicted_same}
    gt_same = {_canonicalize(p) for p in ground_truth_same}
    gt_diff = {_canonicalize(p) for p in ground_truth_different}

    # Confusion matrix
    tp = len(pred & gt_same)
    fp = len(pred & gt_diff)
    fn = len(gt_same - pred)
    tn = len(gt_diff - pred)

    # Metrics
    precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
    recall = tp / (tp + fn) if (tp + fn) > 0 else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0

    return MetricsResult(
        precision=precision,
        recall=recall,
        f1=f1,
        true_positives=tp,
        false_positives=fp,
        false_negatives=fn,
        true_negatives=tn,
        total_ground_truth_same=len(gt_same),
        total_ground_truth_different=len(gt_diff),
        total_predicted_same=len(pred),
    )


def format_metrics(result: MetricsResult) -> str:
    """Format metrics for terminal display.

    Args:
        result: MetricsResult to format.

    Returns:
        Human-readable string representation of the metrics.
    """
    lines = [
        "",
        "=" * 50,
        "  Evaluation Metrics",
        "=" * 50,
        "",
        f"  Precision:  {result.precision:.4f}",
        f"  Recall:     {result.recall:.4f}",
        f"  F1 Score:   {result.f1:.4f}",
        "",
        "  Confusion Matrix:",
        f"    True Positives:   {result.true_positives}",
        f"    False Positives:  {result.false_positives}",
        f"    False Negatives:  {result.false_negatives}",
        f"    True Negatives:   {result.true_negatives}",
        "",
        f"  Ground Truth: {result.total_ground_truth_same} same, "
        f"{result.total_ground_truth_different} different",
        f"  Predicted Same: {result.total_predicted_same}",
        "=" * 50,
        "",
    ]
    return "\n".join(lines)
