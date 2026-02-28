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
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker
from sqlalchemy.orm import selectinload

from event_dedup.evaluation.metrics import MetricsResult, compute_metrics, format_metrics
from event_dedup.matching.config import MatchingConfig, load_matching_config
from event_dedup.matching.pipeline import get_match_pairs, score_candidate_pairs
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


# ---------------------------------------------------------------------------
# Multi-signal evaluation (Phase 2+)
# ---------------------------------------------------------------------------


def generate_predictions_multisignal(
    events: list[dict],
    config: MatchingConfig,
) -> set[tuple[str, str]]:
    """Generate predictions using the multi-signal scoring pipeline.

    This is a pure function that replaces the Phase 1 title-only
    prediction with the full multi-signal pipeline (blocking +
    4-signal scoring + threshold decisions).

    Args:
        events: List of event dicts with all fields required by
            the scoring pipeline.
        config: Full matching configuration.

    Returns:
        Set of canonically ordered ``(event_id_a, event_id_b)`` tuples
        predicted as duplicates.
    """
    match_result = score_candidate_pairs(events, config)
    return get_match_pairs(match_result)


async def run_multisignal_evaluation(
    session: AsyncSession,
    config: MatchingConfig,
) -> EvaluationResult:
    """Run evaluation using multi-signal matching against ground truth.

    Loads all source events from the database, converts them to dicts
    with all fields needed by the scoring pipeline, generates
    predictions using ``generate_predictions_multisignal``, and
    computes metrics against ground truth.

    Args:
        session: Async SQLAlchemy session.
        config: Full matching configuration.

    Returns:
        EvaluationResult with metrics and error analysis.
    """
    gt_same, gt_diff = await load_ground_truth(session)

    # Load all source events with dates
    result = await session.execute(
        select(SourceEvent).options(selectinload(SourceEvent.dates))
    )
    source_events = result.scalars().all()

    # Convert to dicts with ALL fields needed by scorers
    events = []
    for evt in source_events:
        events.append(
            {
                "id": evt.id,
                "title": evt.title,
                "title_normalized": evt.title_normalized,
                "short_description": evt.short_description,
                "short_description_normalized": evt.short_description_normalized,
                "description": evt.description,
                "highlights": evt.highlights,
                "location_name": evt.location_name,
                "location_city": evt.location_city,
                "location_district": evt.location_district,
                "location_street": evt.location_street,
                "location_zipcode": evt.location_zipcode,
                "geo_latitude": evt.geo_latitude,
                "geo_longitude": evt.geo_longitude,
                "geo_confidence": evt.geo_confidence,
                "source_code": evt.source_code,
                "source_type": evt.source_type,
                "blocking_keys": evt.blocking_keys,
                "categories": evt.categories,
                "is_family_event": evt.is_family_event,
                "is_child_focused": evt.is_child_focused,
                "admission_free": evt.admission_free,
                "dates": [
                    {
                        "date": str(d.date),
                        "start_time": str(d.start_time) if d.start_time else None,
                        "end_time": str(d.end_time) if d.end_time else None,
                        "end_date": str(d.end_date) if d.end_date else None,
                    }
                    for d in evt.dates
                ],
            }
        )

    predicted = generate_predictions_multisignal(events, config)
    metrics = compute_metrics(predicted, gt_same, gt_diff)

    pred_canonical = {(min(a, b), max(a, b)) for a, b in predicted}
    gt_same_canonical = {(min(a, b), max(a, b)) for a, b in gt_same}
    gt_diff_canonical = {(min(a, b), max(a, b)) for a, b in gt_diff}

    false_positives = list(pred_canonical & gt_diff_canonical)
    false_negatives = list(gt_same_canonical - pred_canonical)

    return EvaluationResult(
        config=EvaluationConfig(),  # placeholder since we use MatchingConfig
        metrics=metrics,
        false_positive_pairs=false_positives,
        false_negative_pairs=false_negatives,
    )


def evaluate_category_subset(
    ground_truth_same: set[tuple[str, str]],
    ground_truth_different: set[tuple[str, str]],
    predicted_same: set[tuple[str, str]],
    events_by_id: dict[str, dict],
    category: str,
) -> MetricsResult:
    """Compute evaluation metrics for a specific event category subset.

    Filters ground truth and predicted pairs to only include those where
    at least one event in the pair has the specified category. Then
    computes precision/recall/F1 on the filtered subset.

    Args:
        ground_truth_same: All ground truth "same" pairs.
        ground_truth_different: All ground truth "different" pairs.
        predicted_same: All predicted "same" pairs.
        events_by_id: Dict mapping event IDs to event dicts (must include "categories" field).
        category: Category to filter by.

    Returns:
        MetricsResult for the category subset.
    """
    def pair_has_category(pair: tuple[str, str], cat: str) -> bool:
        a_id, b_id = pair
        cats_a = set(events_by_id.get(a_id, {}).get("categories") or [])
        cats_b = set(events_by_id.get(b_id, {}).get("categories") or [])
        return cat in cats_a or cat in cats_b

    gt_same_cat = {p for p in ground_truth_same if pair_has_category(p, category)}
    gt_diff_cat = {p for p in ground_truth_different if pair_has_category(p, category)}
    pred_cat = {p for p in predicted_same if pair_has_category(p, category)}

    return compute_metrics(pred_cat, gt_same_cat, gt_diff_cat)


async def run_ai_comparison_evaluation(
    session: AsyncSession,
    matching_config: MatchingConfig,
    session_factory: async_sessionmaker | None = None,
) -> dict:
    """Run evaluation comparing deterministic-only vs AI-assisted matching.

    Produces a side-by-side comparison showing how AI matching improves
    (or changes) the F1 score on the ground truth dataset.

    Args:
        session: Async SQLAlchemy session for loading events/ground truth.
        matching_config: Full matching config (must have ai section configured).
        session_factory: Async session factory for AI cache/usage DB access.
            Required when AI is enabled.

    Returns:
        Dict with deterministic_metrics, ai_metrics, and improvement delta.
    """
    gt_same, gt_diff = await load_ground_truth(session)

    # Load all source events
    result = await session.execute(
        select(SourceEvent).options(selectinload(SourceEvent.dates))
    )
    source_events = result.scalars().all()

    events = []
    for evt in source_events:
        events.append(
            {
                "id": evt.id,
                "title": evt.title,
                "title_normalized": evt.title_normalized,
                "short_description": evt.short_description,
                "short_description_normalized": evt.short_description_normalized,
                "description": evt.description,
                "highlights": evt.highlights,
                "location_name": evt.location_name,
                "location_city": evt.location_city,
                "location_district": evt.location_district,
                "location_street": evt.location_street,
                "location_zipcode": evt.location_zipcode,
                "geo_latitude": evt.geo_latitude,
                "geo_longitude": evt.geo_longitude,
                "geo_confidence": evt.geo_confidence,
                "source_code": evt.source_code,
                "source_type": evt.source_type,
                "blocking_keys": evt.blocking_keys,
                "categories": evt.categories,
                "is_family_event": evt.is_family_event,
                "is_child_focused": evt.is_child_focused,
                "admission_free": evt.admission_free,
                "dates": [
                    {
                        "date": str(d.date),
                        "start_time": str(d.start_time) if d.start_time else None,
                        "end_time": str(d.end_time) if d.end_time else None,
                        "end_date": str(d.end_date) if d.end_date else None,
                    }
                    for d in evt.dates
                ],
            }
        )

    # --- Deterministic-only ---
    det_predicted = generate_predictions_multisignal(events, matching_config)
    det_metrics = compute_metrics(det_predicted, gt_same, gt_diff)

    # --- With AI assistance ---
    if matching_config.ai.enabled and session_factory is not None:
        from event_dedup.ai_matching.resolver import resolve_ambiguous_pairs
        from event_dedup.matching.pipeline import get_match_pairs, score_candidate_pairs

        match_result = score_candidate_pairs(events, matching_config)
        match_result = await resolve_ambiguous_pairs(
            match_result, events, matching_config.ai, session_factory,
        )
        ai_predicted = get_match_pairs(match_result)
    else:
        ai_predicted = det_predicted

    ai_metrics = compute_metrics(ai_predicted, gt_same, gt_diff)

    # Print comparison
    print("\n" + "=" * 80)
    print("  Deterministic vs AI-Assisted Matching Comparison")
    print("=" * 80)
    print(f"  {'Metric':>15s}  {'Deterministic':>15s}  {'AI-Assisted':>15s}  {'Delta':>10s}")
    print("-" * 80)
    for name, det_val, ai_val in [
        ("Precision", det_metrics.precision, ai_metrics.precision),
        ("Recall", det_metrics.recall, ai_metrics.recall),
        ("F1", det_metrics.f1, ai_metrics.f1),
        ("True Pos", det_metrics.true_positives, ai_metrics.true_positives),
        ("False Pos", det_metrics.false_positives, ai_metrics.false_positives),
        ("False Neg", det_metrics.false_negatives, ai_metrics.false_negatives),
    ]:
        if isinstance(det_val, int):
            delta = ai_val - det_val
            print(f"  {name:>15s}  {det_val:>15d}  {ai_val:>15d}  {delta:>+10d}")
        else:
            delta = ai_val - det_val
            print(f"  {name:>15s}  {det_val:>15.4f}  {ai_val:>15.4f}  {delta:>+10.4f}")
    print("=" * 80 + "\n")

    return {
        "deterministic": {
            "precision": det_metrics.precision,
            "recall": det_metrics.recall,
            "f1": det_metrics.f1,
            "true_positives": det_metrics.true_positives,
            "false_positives": det_metrics.false_positives,
            "false_negatives": det_metrics.false_negatives,
        },
        "ai_assisted": {
            "precision": ai_metrics.precision,
            "recall": ai_metrics.recall,
            "f1": ai_metrics.f1,
            "true_positives": ai_metrics.true_positives,
            "false_positives": ai_metrics.false_positives,
            "false_negatives": ai_metrics.false_negatives,
        },
        "f1_improvement": ai_metrics.f1 - det_metrics.f1,
    }
