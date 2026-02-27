"""Evaluation harness for event deduplication.

Runs end-to-end evaluation by loading ground truth, generating
predictions using blocking + title similarity, and computing
precision/recall/F1 metrics. Supports threshold sweep for
parameter tuning.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz.fuzz import token_sort_ratio
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from event_dedup.evaluation.metrics import MetricsResult, compute_metrics, format_metrics
from event_dedup.models.ground_truth import GroundTruthPair
from event_dedup.models.source_event import SourceEvent


@dataclass
class EvaluationConfig:
    """Configuration for evaluation runs."""

    title_sim_threshold: float = 0.80


@dataclass
class EvaluationResult:
    """Result of a single evaluation run."""

    config: EvaluationConfig
    metrics: MetricsResult
    false_positive_pairs: list[tuple[str, str]] = field(default_factory=list)
    false_negative_pairs: list[tuple[str, str]] = field(default_factory=list)


async def load_ground_truth(
    session: AsyncSession,
) -> tuple[set[tuple[str, str]], set[tuple[str, str]]]:
    """Load ground truth labels from the database.

    Args:
        session: Async SQLAlchemy session.

    Returns:
        Tuple of (ground_truth_same, ground_truth_different) sets,
        each containing canonically ordered (event_id_a, event_id_b) tuples.
    """
    result = await session.execute(select(GroundTruthPair))
    pairs = result.scalars().all()

    ground_truth_same: set[tuple[str, str]] = set()
    ground_truth_different: set[tuple[str, str]] = set()

    for pair in pairs:
        canonical = (pair.event_id_a, pair.event_id_b)
        if pair.label == "same":
            ground_truth_same.add(canonical)
        elif pair.label == "different":
            ground_truth_different.add(canonical)

    return ground_truth_same, ground_truth_different


def generate_predictions_from_events(
    events: list[dict],
    config: EvaluationConfig,
) -> set[tuple[str, str]]:
    """Generate predicted duplicate pairs from event data.

    This is a pure function for easy testing. Groups events by
    blocking keys, then generates cross-source pairs with title
    similarity above the configured threshold.

    Args:
        events: List of dicts with keys: id, title_normalized,
            source_code, blocking_keys.
        config: Evaluation configuration with threshold.

    Returns:
        Set of canonically ordered (event_id_a, event_id_b) tuples
        predicted as duplicates.
    """
    # Build blocking index
    blocking_index: dict[str, list[dict]] = {}
    for event in events:
        for key in event.get("blocking_keys") or []:
            blocking_index.setdefault(key, []).append(event)

    predicted_same: set[tuple[str, str]] = set()

    for _key, group in blocking_index.items():
        for i in range(len(group)):
            for j in range(i + 1, len(group)):
                evt_a = group[i]
                evt_b = group[j]

                # Only cross-source pairs
                if evt_a["source_code"] == evt_b["source_code"]:
                    continue

                # Canonical ordering
                id_a, id_b = evt_a["id"], evt_b["id"]
                if id_a > id_b:
                    id_a, id_b = id_b, id_a

                pair_key = (id_a, id_b)
                if pair_key in predicted_same:
                    continue

                # Compute title similarity
                title_norm_a = evt_a.get("title_normalized") or ""
                title_norm_b = evt_b.get("title_normalized") or ""
                sim = token_sort_ratio(title_norm_a, title_norm_b) / 100.0

                if sim >= config.title_sim_threshold:
                    predicted_same.add(pair_key)

    return predicted_same


async def generate_predictions(
    session: AsyncSession,
    config: EvaluationConfig,
) -> set[tuple[str, str]]:
    """Generate predictions from the database.

    Args:
        session: Async SQLAlchemy session.
        config: Evaluation configuration.

    Returns:
        Set of predicted duplicate pairs.
    """
    result = await session.execute(
        select(SourceEvent).options(selectinload(SourceEvent.dates))
    )
    source_events = result.scalars().all()

    events = [
        {
            "id": evt.id,
            "title_normalized": evt.title_normalized,
            "source_code": evt.source_code,
            "blocking_keys": evt.blocking_keys,
        }
        for evt in source_events
    ]

    return generate_predictions_from_events(events, config)


async def run_evaluation(
    session: AsyncSession,
    config: EvaluationConfig,
) -> EvaluationResult:
    """Run a full evaluation against ground truth.

    Args:
        session: Async SQLAlchemy session.
        config: Evaluation configuration.

    Returns:
        EvaluationResult with metrics and error analysis.
    """
    gt_same, gt_diff = await load_ground_truth(session)
    predicted = await generate_predictions(session, config)

    metrics = compute_metrics(predicted, gt_same, gt_diff)

    # Identify false positives and false negatives for analysis
    pred_canonical = {(min(a, b), max(a, b)) for a, b in predicted}
    gt_same_canonical = {(min(a, b), max(a, b)) for a, b in gt_same}
    gt_diff_canonical = {(min(a, b), max(a, b)) for a, b in gt_diff}

    false_positives = list(pred_canonical & gt_diff_canonical)
    false_negatives = list(gt_same_canonical - pred_canonical)

    return EvaluationResult(
        config=config,
        metrics=metrics,
        false_positive_pairs=false_positives,
        false_negative_pairs=false_negatives,
    )


async def run_threshold_sweep(
    session: AsyncSession,
    thresholds: list[float] | None = None,
) -> list[EvaluationResult]:
    """Run evaluation across multiple thresholds.

    Args:
        session: Async SQLAlchemy session.
        thresholds: List of thresholds to test. Defaults to
            [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95].

    Returns:
        List of EvaluationResult, one per threshold.
    """
    if thresholds is None:
        thresholds = [0.50, 0.60, 0.70, 0.75, 0.80, 0.85, 0.90, 0.95]

    results = []
    for threshold in thresholds:
        config = EvaluationConfig(title_sim_threshold=threshold)
        result = await run_evaluation(session, config)
        results.append(result)

    # Print comparison table
    print("\n" + "=" * 80)
    print("  Threshold Sweep Results")
    print("=" * 80)
    print(f"  {'Threshold':>10s}  {'Precision':>10s}  {'Recall':>8s}  {'F1':>8s}  {'TP':>5s}  {'FP':>5s}  {'FN':>5s}")
    print("-" * 80)
    for r in results:
        m = r.metrics
        print(
            f"  {r.config.title_sim_threshold:>10.2f}  "
            f"{m.precision:>10.4f}  {m.recall:>8.4f}  {m.f1:>8.4f}  "
            f"{m.true_positives:>5d}  {m.false_positives:>5d}  {m.false_negatives:>5d}"
        )
    print("=" * 80 + "\n")

    return results
