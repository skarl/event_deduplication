"""Matching pipeline orchestrator.

Scores all candidate pairs using the four signal scorers and the
weighted combiner, then clusters matches and synthesizes canonical
events.  All functions are PURE -- no database access.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from event_dedup.clustering.graph_cluster import ClusterResult

from event_dedup.matching.candidate_pairs import (
    CandidatePairStats,
    generate_candidate_pairs,
)
from event_dedup.matching.combiner import SignalScores, combined_score, decide
from event_dedup.matching.config import MatchingConfig, ScoringWeights
from event_dedup.matching.scorers import (
    date_score,
    description_score,
    geo_score,
    title_score,
)


@dataclass
class MatchDecisionRecord:
    """A single pairwise match decision with all signal details.

    Attributes:
        event_id_a: First event ID (canonical ordering: id_a < id_b).
        event_id_b: Second event ID.
        signals: The four individual signal scores.
        combined_score_value: Weighted combined score.
        decision: One of ``"match"``, ``"no_match"``, ``"ambiguous"``.
        tier: Matching tier (default ``"deterministic"``).
    """

    event_id_a: str
    event_id_b: str
    signals: SignalScores
    combined_score_value: float
    decision: str
    tier: str = "deterministic"


@dataclass
class MatchResult:
    """Aggregate result from the matching pipeline.

    Attributes:
        decisions: All pairwise match decisions.
        pair_stats: Blocking/candidate pair statistics.
        match_count: Number of ``"match"`` decisions.
        ambiguous_count: Number of ``"ambiguous"`` decisions.
        no_match_count: Number of ``"no_match"`` decisions.
    """

    decisions: list[MatchDecisionRecord]
    pair_stats: CandidatePairStats
    match_count: int
    ambiguous_count: int
    no_match_count: int


def resolve_weights(
    event_a: dict, event_b: dict, config: MatchingConfig
) -> ScoringWeights:
    """Select scoring weights based on shared event categories.

    Checks if both events share a category that has weight overrides.
    Uses the priority list to determine which override takes precedence
    when multiple categories overlap.

    Returns the default config.scoring if no category-specific override applies.
    """
    if not config.category_weights.priority:
        return config.scoring

    cats_a = set(event_a.get("categories") or [])
    cats_b = set(event_b.get("categories") or [])
    shared = cats_a & cats_b

    if not shared:
        return config.scoring

    for cat in config.category_weights.priority:
        if cat in shared and cat in config.category_weights.overrides:
            return config.category_weights.overrides[cat]

    return config.scoring


def score_candidate_pairs(
    events: list[dict], config: MatchingConfig
) -> MatchResult:
    """Score all candidate pairs.  PURE FUNCTION -- no DB access.

    1. Generates candidate pairs via blocking keys.
    2. Scores each pair with the four signal scorers.
    3. Combines scores into a weighted average.
    4. Applies threshold-based decision logic.

    Args:
        events: List of event dicts with ``"id"``, ``"source_code"``,
            ``"blocking_keys"``, plus fields required by each scorer.
        config: Full matching configuration.

    Returns:
        A ``MatchResult`` containing all decisions and statistics.
    """
    pairs, pair_stats = generate_candidate_pairs(events)
    events_by_id = {e["id"]: e for e in events}
    decisions: list[MatchDecisionRecord] = []
    match_count = 0
    ambiguous_count = 0
    no_match_count = 0

    for id_a, id_b in pairs:
        evt_a = events_by_id[id_a]
        evt_b = events_by_id[id_b]

        signals = SignalScores(
            date=date_score(evt_a, evt_b, config.date),
            geo=geo_score(evt_a, evt_b, config.geo),
            title=title_score(evt_a, evt_b, config.title),
            description=description_score(evt_a, evt_b),
        )

        weights = resolve_weights(evt_a, evt_b, config)
        score = combined_score(signals, weights)
        dec = decide(score, config.thresholds)

        decisions.append(
            MatchDecisionRecord(
                event_id_a=id_a,
                event_id_b=id_b,
                signals=signals,
                combined_score_value=score,
                decision=dec,
            )
        )

        if dec == "match":
            match_count += 1
        elif dec == "ambiguous":
            ambiguous_count += 1
        else:
            no_match_count += 1

    return MatchResult(
        decisions=decisions,
        pair_stats=pair_stats,
        match_count=match_count,
        ambiguous_count=ambiguous_count,
        no_match_count=no_match_count,
    )


def get_match_pairs(result: MatchResult) -> set[tuple[str, str]]:
    """Extract match-decision pairs for clustering.

    Returns the set of ``(event_id_a, event_id_b)`` tuples where the
    decision was ``"match"``.  This is the interface that Plan 02-03
    (graph-based clustering) consumes.
    """
    return {
        (d.event_id_a, d.event_id_b)
        for d in result.decisions
        if d.decision == "match"
    }


# ---------------------------------------------------------------------------
# Full pipeline: blocking -> scoring -> clustering -> synthesis
# ---------------------------------------------------------------------------


@dataclass
class PipelineResult:
    """Complete result from the full deduplication pipeline.

    Attributes:
        match_result: Scoring phase output.
        cluster_result: Clustering phase output.
        canonical_events: Synthesized canonical events (one per cluster).
        canonical_count: Total number of canonical events.
        flagged_count: Number of canonical events from flagged clusters.
    """

    match_result: MatchResult
    cluster_result: ClusterResult
    canonical_events: list[dict]
    canonical_count: int
    flagged_count: int


def run_full_pipeline(
    events: list[dict], config: MatchingConfig
) -> PipelineResult:
    """Full pipeline: blocking -> scoring -> clustering -> synthesis.

    This is a PURE FUNCTION -- no database access.  Takes event dicts
    and configuration, returns the complete deduplication result
    including synthesized canonical events.

    Args:
        events: List of event dicts with all fields required by
            scorers, blocking, and synthesis.
        config: Full matching configuration.

    Returns:
        A ``PipelineResult`` with match decisions, clusters, and
        canonical events.
    """
    # Lazy imports to avoid circular dependency
    # (graph_cluster imports MatchDecisionRecord from this module)
    from event_dedup.canonical.synthesizer import synthesize_canonical
    from event_dedup.clustering.graph_cluster import cluster_matches

    # Step 1: Score candidate pairs
    match_result = score_candidate_pairs(events, config)

    # Step 2: Cluster matches
    all_event_ids = [e["id"] for e in events]
    events_by_id = {e["id"]: e for e in events}
    cluster_result = cluster_matches(
        match_result.decisions, all_event_ids, config.cluster, events_by_id
    )

    # Step 3: Synthesize canonical events
    canonical_events: list[dict] = []

    for cluster in cluster_result.clusters:
        sources = [events_by_id[eid] for eid in cluster]
        canonical = synthesize_canonical(sources, config.canonical)
        canonical["needs_review"] = False
        canonical["match_confidence"] = _avg_cluster_confidence(
            cluster, match_result.decisions
        )
        canonical["ai_assisted"] = _cluster_has_ai_decisions(
            cluster, match_result.decisions
        )
        canonical_events.append(canonical)

    for cluster in cluster_result.flagged_clusters:
        sources = [events_by_id[eid] for eid in cluster]
        canonical = synthesize_canonical(sources, config.canonical)
        canonical["needs_review"] = True
        canonical["match_confidence"] = _avg_cluster_confidence(
            cluster, match_result.decisions
        )
        canonical["ai_assisted"] = _cluster_has_ai_decisions(
            cluster, match_result.decisions
        )
        canonical_events.append(canonical)

    return PipelineResult(
        match_result=match_result,
        cluster_result=cluster_result,
        canonical_events=canonical_events,
        canonical_count=len(canonical_events),
        flagged_count=len(cluster_result.flagged_clusters),
    )


def extract_predicted_pairs(
    result: PipelineResult,
) -> set[tuple[str, str]]:
    """Extract match pairs from a pipeline result for evaluation.

    Returns the set of canonically ordered ``(event_id_a, event_id_b)``
    pairs that were scored as ``"match"``.
    """
    return get_match_pairs(result.match_result)


def _avg_cluster_confidence(
    cluster: set[str],
    decisions: list[MatchDecisionRecord],
) -> float | None:
    """Compute average combined_score for match decisions within a cluster.

    Returns ``None`` for singleton clusters (no internal decisions).
    """
    cluster_decisions = [
        d
        for d in decisions
        if d.decision == "match"
        and d.event_id_a in cluster
        and d.event_id_b in cluster
    ]
    if not cluster_decisions:
        return None
    return sum(d.combined_score_value for d in cluster_decisions) / len(
        cluster_decisions
    )


def _cluster_has_ai_decisions(
    cluster: set[str],
    decisions: list[MatchDecisionRecord],
) -> bool:
    """Check if any match decision in a cluster was resolved by AI."""
    return any(
        d.tier.startswith("ai")
        and d.event_id_a in cluster
        and d.event_id_b in cluster
        for d in decisions
    )


def rebuild_pipeline_result(
    match_result: MatchResult,
    events: list[dict],
    config: MatchingConfig,
) -> PipelineResult:
    """Rebuild clustering and synthesis from an updated MatchResult.

    Use this after AI resolution modifies match decisions. It re-runs
    clustering and canonical synthesis using the updated decisions
    while preserving the same logic as ``run_full_pipeline``.

    Args:
        match_result: Updated MatchResult (e.g., after AI resolution).
        events: All event dicts.
        config: Full matching configuration.

    Returns:
        A new ``PipelineResult`` with re-clustered and re-synthesized data.
    """
    # Lazy imports to avoid circular dependency (same as run_full_pipeline)
    from event_dedup.canonical.synthesizer import synthesize_canonical
    from event_dedup.clustering.graph_cluster import cluster_matches

    all_event_ids = [e["id"] for e in events]
    events_by_id = {e["id"]: e for e in events}

    cluster_result = cluster_matches(
        match_result.decisions, all_event_ids, config.cluster, events_by_id
    )

    canonical_events: list[dict] = []

    for cluster in cluster_result.clusters:
        sources = [events_by_id[eid] for eid in cluster]
        canonical = synthesize_canonical(sources, config.canonical)
        canonical["needs_review"] = False
        canonical["match_confidence"] = _avg_cluster_confidence(
            cluster, match_result.decisions
        )
        canonical["ai_assisted"] = _cluster_has_ai_decisions(
            cluster, match_result.decisions
        )
        canonical_events.append(canonical)

    for cluster in cluster_result.flagged_clusters:
        sources = [events_by_id[eid] for eid in cluster]
        canonical = synthesize_canonical(sources, config.canonical)
        canonical["needs_review"] = True
        canonical["match_confidence"] = _avg_cluster_confidence(
            cluster, match_result.decisions
        )
        canonical["ai_assisted"] = _cluster_has_ai_decisions(
            cluster, match_result.decisions
        )
        canonical_events.append(canonical)

    return PipelineResult(
        match_result=match_result,
        cluster_result=cluster_result,
        canonical_events=canonical_events,
        canonical_count=len(canonical_events),
        flagged_count=len(cluster_result.flagged_clusters),
    )
