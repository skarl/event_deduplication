"""Score combiner and decision maker.

Combines four signal scores into a single weighted score and
applies threshold-based decision logic.
"""

from __future__ import annotations

from dataclasses import dataclass

from event_dedup.matching.config import ScoringWeights, ThresholdConfig


@dataclass(frozen=True)
class SignalScores:
    """Container for the four matching signal scores."""

    date: float
    geo: float
    title: float
    description: float


def combined_score(
    scores: SignalScores, weights: ScoringWeights | None = None
) -> float:
    """Compute a weighted average of the four signal scores.

    The weights are normalised so they always sum to 1.0,
    even if the configured weights do not.

    Returns a float in [0, 1].
    """
    if weights is None:
        weights = ScoringWeights()

    total_weight = weights.date + weights.geo + weights.title + weights.description

    if total_weight == 0:
        return 0.0

    weighted = (
        weights.date * scores.date
        + weights.geo * scores.geo
        + weights.title * scores.title
        + weights.description * scores.description
    )

    return weighted / total_weight


def decide(
    score: float, thresholds: ThresholdConfig | None = None
) -> str:
    """Apply threshold-based decision logic.

    Returns:
        ``"match"`` if score >= high threshold,
        ``"no_match"`` if score <= low threshold,
        ``"ambiguous"`` otherwise.
    """
    if thresholds is None:
        thresholds = ThresholdConfig()

    if score >= thresholds.high:
        return "match"
    if score <= thresholds.low:
        return "no_match"
    return "ambiguous"
