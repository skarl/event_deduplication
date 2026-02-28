"""Matching pipeline orchestrator.

Scores all candidate pairs using the four signal scorers and the
weighted combiner.  This is a PURE FUNCTION -- no database access.
It takes event dicts and a ``MatchingConfig``, and returns scored
decisions for every candidate pair.
"""

from __future__ import annotations

from dataclasses import dataclass

from event_dedup.matching.candidate_pairs import (
    CandidatePairStats,
    generate_candidate_pairs,
)
from event_dedup.matching.combiner import SignalScores, combined_score, decide
from event_dedup.matching.config import MatchingConfig
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

        score = combined_score(signals, config.scoring)
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
