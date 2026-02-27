"""Auto-label candidate pairs using conservative multi-signal heuristics.

Labels pairs as "same" or "different" with high confidence, skipping
ambiguous cases. The heuristics are intentionally stricter than the
matching algorithm to ensure ground truth reliability.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from rapidfuzz.fuzz import token_sort_ratio

from event_dedup.ground_truth.candidate_generator import CandidatePair


@dataclass
class LabelDecision:
    """A labeling decision for a candidate pair."""

    event_id_a: str
    event_id_b: str
    label: str  # "same" or "different"
    confidence: str  # "high" or "medium"
    reason: str
    title_sim: float
    desc_sim: float
    loc_sim: float


@dataclass
class AutoLabelResult:
    """Result of auto-labeling a set of candidate pairs."""

    labeled: list[LabelDecision] = field(default_factory=list)
    skipped_ambiguous: int = 0

    @property
    def same_count(self) -> int:
        return sum(1 for d in self.labeled if d.label == "same")

    @property
    def different_count(self) -> int:
        return sum(1 for d in self.labeled if d.label == "different")

    @property
    def total(self) -> int:
        return len(self.labeled)


def _compute_desc_sim(event_a: dict, event_b: dict) -> float:
    """Compute description similarity between two events."""
    desc_a = event_a.get("short_description_normalized") or ""
    desc_b = event_b.get("short_description_normalized") or ""
    if not desc_a or not desc_b:
        return 0.0
    return token_sort_ratio(desc_a, desc_b) / 100.0


def _compute_loc_sim(event_a: dict, event_b: dict) -> float:
    """Compute location name similarity between two events."""
    loc_a = event_a.get("location_name_normalized") or ""
    loc_b = event_b.get("location_name_normalized") or ""
    if not loc_a or not loc_b:
        return 0.0
    return token_sort_ratio(loc_a, loc_b) / 100.0


def _same_city(event_a: dict, event_b: dict) -> bool:
    """Check if two events have the same normalized city."""
    city_a = event_a.get("location_city_normalized") or ""
    city_b = event_b.get("location_city_normalized") or ""
    return bool(city_a and city_b and city_a == city_b)


def _different_city(event_a: dict, event_b: dict) -> bool:
    """Check if two events have different normalized cities (both non-empty)."""
    city_a = event_a.get("location_city_normalized") or ""
    city_b = event_b.get("location_city_normalized") or ""
    return bool(city_a and city_b and city_a != city_b)


def auto_label_candidates(
    candidates: list[CandidatePair],
    events_by_id: dict[str, dict],
) -> AutoLabelResult:
    """Auto-label candidate pairs using conservative multi-signal heuristics.

    Rules are intentionally stricter than the matching algorithm:

    Auto "same" (requires different source, enforced by candidate generator):
      1. title_sim >= 0.90 AND same city → high confidence same
      2. title_sim >= 0.70 AND same city AND desc_sim >= 0.80 → medium confidence same

    Auto "different":
      1. title_sim < 0.40 → high confidence different
      2. different city AND title_sim < 0.70 → high confidence different

    Everything else is skipped as ambiguous.

    Args:
        candidates: Candidate pairs from the candidate generator.
        events_by_id: Dict mapping event ID to event dict with normalized fields.

    Returns:
        AutoLabelResult with labeled decisions and ambiguous count.
    """
    result = AutoLabelResult()

    for candidate in candidates:
        event_a = events_by_id.get(candidate.event_id_a)
        event_b = events_by_id.get(candidate.event_id_b)

        if not event_a or not event_b:
            continue

        title_sim = candidate.title_sim
        desc_sim = _compute_desc_sim(event_a, event_b)
        loc_sim = _compute_loc_sim(event_a, event_b)

        decision = None

        # --- Auto "same" rules ---
        if title_sim >= 0.90 and _same_city(event_a, event_b):
            decision = LabelDecision(
                event_id_a=candidate.event_id_a,
                event_id_b=candidate.event_id_b,
                label="same",
                confidence="high",
                reason="title_sim>=0.90 + same_city",
                title_sim=title_sim,
                desc_sim=desc_sim,
                loc_sim=loc_sim,
            )
        elif (
            title_sim >= 0.70
            and _same_city(event_a, event_b)
            and desc_sim >= 0.80
        ):
            decision = LabelDecision(
                event_id_a=candidate.event_id_a,
                event_id_b=candidate.event_id_b,
                label="same",
                confidence="medium",
                reason="title_sim>=0.70 + same_city + desc_sim>=0.80",
                title_sim=title_sim,
                desc_sim=desc_sim,
                loc_sim=loc_sim,
            )

        # --- Auto "different" rules ---
        elif title_sim < 0.40:
            decision = LabelDecision(
                event_id_a=candidate.event_id_a,
                event_id_b=candidate.event_id_b,
                label="different",
                confidence="high",
                reason="title_sim<0.40",
                title_sim=title_sim,
                desc_sim=desc_sim,
                loc_sim=loc_sim,
            )
        elif _different_city(event_a, event_b) and title_sim < 0.70:
            decision = LabelDecision(
                event_id_a=candidate.event_id_a,
                event_id_b=candidate.event_id_b,
                label="different",
                confidence="high",
                reason="different_city + title_sim<0.70",
                title_sim=title_sim,
                desc_sim=desc_sim,
                loc_sim=loc_sim,
            )

        # --- Ambiguous ---
        else:
            result.skipped_ambiguous += 1
            continue

        result.labeled.append(decision)

    return result
