"""Tests for the score combiner and decision logic."""

import pytest

from event_dedup.matching.combiner import SignalScores, combined_score, decide
from event_dedup.matching.config import ScoringWeights, ThresholdConfig


class TestCombinedScore:
    """Tests for the weighted average combination."""

    def test_all_ones(self) -> None:
        scores = SignalScores(date=1.0, geo=1.0, title=1.0, description=1.0)
        assert combined_score(scores) == pytest.approx(1.0)

    def test_all_zeros(self) -> None:
        scores = SignalScores(date=0.0, geo=0.0, title=0.0, description=0.0)
        assert combined_score(scores) == pytest.approx(0.0)

    def test_default_weights(self) -> None:
        """Verify weighted average with default weights (0.30, 0.25, 0.30, 0.15)."""
        scores = SignalScores(date=1.0, geo=0.0, title=1.0, description=0.0)
        # (0.30*1 + 0.25*0 + 0.30*1 + 0.15*0) / 1.0 = 0.60
        assert combined_score(scores) == pytest.approx(0.6)

    def test_custom_weights(self) -> None:
        weights = ScoringWeights(date=0.5, geo=0.5, title=0.0, description=0.0)
        scores = SignalScores(date=0.8, geo=0.6, title=0.9, description=0.1)
        # (0.5*0.8 + 0.5*0.6 + 0.0*0.9 + 0.0*0.1) / 1.0 = 0.70
        assert combined_score(scores, weights) == pytest.approx(0.7)

    def test_weight_normalization(self) -> None:
        """Weights that don't sum to 1.0 should be normalised."""
        weights = ScoringWeights(date=1.0, geo=1.0, title=1.0, description=1.0)
        scores = SignalScores(date=0.8, geo=0.6, title=0.4, description=0.2)
        expected = (0.8 + 0.6 + 0.4 + 0.2) / 4.0
        assert combined_score(scores, weights) == pytest.approx(expected)

    def test_zero_weights(self) -> None:
        weights = ScoringWeights(date=0.0, geo=0.0, title=0.0, description=0.0)
        scores = SignalScores(date=1.0, geo=1.0, title=1.0, description=1.0)
        assert combined_score(scores, weights) == 0.0


class TestDecide:
    """Tests for the threshold-based decision logic."""

    def test_match(self) -> None:
        assert decide(0.80) == "match"

    def test_no_match(self) -> None:
        assert decide(0.20) == "no_match"

    def test_ambiguous(self) -> None:
        assert decide(0.50) == "ambiguous"

    def test_exact_high_threshold(self) -> None:
        assert decide(0.75) == "match"

    def test_exact_low_threshold(self) -> None:
        assert decide(0.35) == "no_match"

    def test_just_above_low(self) -> None:
        assert decide(0.36) == "ambiguous"

    def test_just_below_high(self) -> None:
        assert decide(0.74) == "ambiguous"

    def test_custom_thresholds(self) -> None:
        cfg = ThresholdConfig(high=0.90, low=0.10)
        assert decide(0.85, cfg) == "ambiguous"
        assert decide(0.90, cfg) == "match"
        assert decide(0.10, cfg) == "no_match"
        assert decide(0.05, cfg) == "no_match"

    def test_title_veto_prevents_match(self) -> None:
        """Low title score vetoes auto-merge even when combined score is above high threshold."""
        assert decide(0.80, title_score=0.20) == "ambiguous"

    def test_title_veto_allows_match_above_threshold(self) -> None:
        """Title score above veto threshold allows normal match."""
        assert decide(0.80, title_score=0.50) == "match"

    def test_title_veto_at_boundary(self) -> None:
        """Title score exactly at veto threshold is NOT vetoed (< not <=)."""
        assert decide(0.80, title_score=0.30) == "match"

    def test_title_veto_no_effect_on_no_match(self) -> None:
        """Title veto doesn't affect no_match decisions."""
        assert decide(0.20, title_score=0.10) == "no_match"

    def test_title_veto_no_effect_on_ambiguous(self) -> None:
        """Title veto doesn't affect already-ambiguous decisions."""
        assert decide(0.50, title_score=0.10) == "ambiguous"

    def test_title_veto_not_passed(self) -> None:
        """When title_score is not passed, no veto is applied."""
        assert decide(0.80) == "match"

    def test_title_veto_disabled_when_zero(self) -> None:
        """Title veto is disabled when threshold is set to 0."""
        cfg = ThresholdConfig(title_veto=0.0)
        assert decide(0.80, cfg, title_score=0.10) == "match"

    def test_title_veto_custom_threshold(self) -> None:
        """Custom veto threshold is respected."""
        cfg = ThresholdConfig(title_veto=0.50)
        assert decide(0.80, cfg, title_score=0.40) == "ambiguous"
        assert decide(0.80, cfg, title_score=0.50) == "match"
