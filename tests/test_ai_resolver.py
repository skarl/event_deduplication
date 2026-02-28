"""Tests for AI matching resolver.

Uses mocked Gemini client to test resolution logic without API calls.
"""
from __future__ import annotations

from unittest.mock import AsyncMock, patch

import pytest

from event_dedup.ai_matching.resolver import _apply_ai_result, resolve_ambiguous_pairs
from event_dedup.ai_matching.schemas import AIMatchResult
from event_dedup.matching.combiner import SignalScores
from event_dedup.matching.config import AIMatchingConfig
from event_dedup.matching.pipeline import MatchDecisionRecord, MatchResult
from event_dedup.matching.candidate_pairs import CandidatePairStats


# ---- Helpers ----

def _make_signals(score: float = 0.5) -> SignalScores:
    return SignalScores(date=score, geo=score, title=score, description=score)


def _make_decision(
    id_a: str, id_b: str, decision: str = "ambiguous", score: float = 0.7
) -> MatchDecisionRecord:
    return MatchDecisionRecord(
        event_id_a=id_a,
        event_id_b=id_b,
        signals=_make_signals(score),
        combined_score_value=score,
        decision=decision,
    )


def _make_match_result(decisions: list[MatchDecisionRecord]) -> MatchResult:
    return MatchResult(
        decisions=decisions,
        pair_stats=CandidatePairStats(
            total_events=10, total_possible_pairs=5, blocked_pairs=5, reduction_pct=50.0
        ),
        match_count=sum(1 for d in decisions if d.decision == "match"),
        ambiguous_count=sum(1 for d in decisions if d.decision == "ambiguous"),
        no_match_count=sum(1 for d in decisions if d.decision == "no_match"),
    )


def _make_event(id: str, title: str = "Event") -> dict:
    return {
        "id": id,
        "title": title,
        "description": "Description",
        "short_description": "Short",
        "source_code": "bwb",
        "source_type": "artikel",
        "location_name": "Marktplatz",
        "location_city": "Freiburg",
        "dates": [{"date": "2026-01-01"}],
        "categories": ["test"],
    }


# ---- _apply_ai_result tests ----

class TestApplyAIResult:
    def test_high_confidence_same(self):
        d = _make_decision("a", "b")
        r = _apply_ai_result(d, AIMatchResult(decision="same", confidence=0.9, reasoning="match"), 0.6)
        assert r.decision == "match"
        assert r.tier == "ai"

    def test_high_confidence_different(self):
        d = _make_decision("a", "b")
        r = _apply_ai_result(d, AIMatchResult(decision="different", confidence=0.8, reasoning="no match"), 0.6)
        assert r.decision == "no_match"
        assert r.tier == "ai"

    def test_low_confidence_stays_ambiguous(self):
        d = _make_decision("a", "b")
        r = _apply_ai_result(d, AIMatchResult(decision="same", confidence=0.3, reasoning="unsure"), 0.6)
        assert r.decision == "ambiguous"
        assert r.tier == "ai_low_confidence"

    def test_exactly_at_threshold(self):
        d = _make_decision("a", "b")
        r = _apply_ai_result(d, AIMatchResult(decision="same", confidence=0.6, reasoning="borderline"), 0.6)
        assert r.decision == "match"
        assert r.tier == "ai"

    def test_preserves_signal_scores(self):
        signals = SignalScores(date=0.9, geo=0.8, title=0.7, description=0.6)
        d = MatchDecisionRecord("a", "b", signals, 0.75, "ambiguous")
        r = _apply_ai_result(d, AIMatchResult(decision="same", confidence=0.9, reasoning="match"), 0.6)
        assert r.signals == signals
        assert r.combined_score_value == 0.75


# ---- resolve_ambiguous_pairs tests ----

class TestResolveAmbiguousPairs:
    @pytest.fixture
    def ai_config(self):
        return AIMatchingConfig(
            enabled=True,
            api_key="test-key",
            model="gemini-2.5-flash",
            confidence_threshold=0.6,
            cache_enabled=False,  # Disable cache for simpler testing
            max_concurrent_requests=5,
        )

    async def test_no_ambiguous_noop(self, test_session_factory, ai_config):
        """When no ambiguous pairs exist, result is returned unchanged."""
        decisions = [_make_decision("a", "b", "match")]
        match_result = _make_match_result(decisions)
        events = [_make_event("a"), _make_event("b")]

        result = await resolve_ambiguous_pairs(
            match_result, events, ai_config, test_session_factory
        )
        assert result.match_count == 1
        assert result.ambiguous_count == 0

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_resolves_ambiguous_to_match(
        self, mock_create, mock_call, test_session_factory, ai_config
    ):
        """Ambiguous pair resolved to match by AI."""
        mock_create.return_value = AsyncMock()
        mock_call.return_value = (
            AIMatchResult(decision="same", confidence=0.9, reasoning="Same event"),
            800, 100,
        )

        decisions = [
            _make_decision("a", "b", "match"),
            _make_decision("c", "d", "ambiguous"),
        ]
        match_result = _make_match_result(decisions)
        events = [_make_event("a"), _make_event("b"), _make_event("c"), _make_event("d")]

        result = await resolve_ambiguous_pairs(
            match_result, events, ai_config, test_session_factory
        )
        assert result.match_count == 2  # Original match + AI match
        assert result.ambiguous_count == 0
        assert mock_call.call_count == 1

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_resolves_ambiguous_to_no_match(
        self, mock_create, mock_call, test_session_factory, ai_config
    ):
        """Ambiguous pair resolved to no_match by AI."""
        mock_create.return_value = AsyncMock()
        mock_call.return_value = (
            AIMatchResult(decision="different", confidence=0.85, reasoning="Different events"),
            800, 100,
        )

        decisions = [_make_decision("a", "b", "ambiguous")]
        match_result = _make_match_result(decisions)
        events = [_make_event("a"), _make_event("b")]

        result = await resolve_ambiguous_pairs(
            match_result, events, ai_config, test_session_factory
        )
        assert result.match_count == 0
        assert result.no_match_count == 1
        assert result.ambiguous_count == 0

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_low_confidence_stays_ambiguous(
        self, mock_create, mock_call, test_session_factory, ai_config
    ):
        """Low-confidence AI result keeps pair as ambiguous."""
        mock_create.return_value = AsyncMock()
        mock_call.return_value = (
            AIMatchResult(decision="same", confidence=0.3, reasoning="Unsure"),
            800, 100,
        )

        decisions = [_make_decision("a", "b", "ambiguous")]
        match_result = _make_match_result(decisions)
        events = [_make_event("a"), _make_event("b")]

        result = await resolve_ambiguous_pairs(
            match_result, events, ai_config, test_session_factory
        )
        assert result.ambiguous_count == 1
        assert result.match_count == 0

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_api_failure_keeps_ambiguous(
        self, mock_create, mock_call, test_session_factory, ai_config
    ):
        """API failure keeps pair as ambiguous without crashing."""
        mock_create.return_value = AsyncMock()
        mock_call.side_effect = Exception("API rate limit exceeded")

        decisions = [_make_decision("a", "b", "ambiguous")]
        match_result = _make_match_result(decisions)
        events = [_make_event("a"), _make_event("b")]

        result = await resolve_ambiguous_pairs(
            match_result, events, ai_config, test_session_factory
        )
        assert result.ambiguous_count == 1
        assert result.decisions[0].decision == "ambiguous"

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_non_ambiguous_unchanged(
        self, mock_create, mock_call, test_session_factory, ai_config
    ):
        """Match and no_match decisions are never sent to AI."""
        mock_create.return_value = AsyncMock()
        mock_call.return_value = (
            AIMatchResult(decision="same", confidence=0.9, reasoning="Same"),
            800, 100,
        )

        decisions = [
            _make_decision("a", "b", "match"),
            _make_decision("c", "d", "no_match"),
            _make_decision("e", "f", "ambiguous"),
        ]
        match_result = _make_match_result(decisions)
        events = [_make_event(id) for id in ["a", "b", "c", "d", "e", "f"]]

        result = await resolve_ambiguous_pairs(
            match_result, events, ai_config, test_session_factory
        )

        # Only the ambiguous pair was sent to AI
        assert mock_call.call_count == 1
        # Original match and no_match preserved
        assert result.match_count == 2  # original + AI resolved
        assert result.no_match_count == 1

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_cache_hit_skips_api(
        self, mock_create, mock_call, test_session_factory
    ):
        """Cache hits avoid API calls."""
        ai_config = AIMatchingConfig(
            enabled=True, api_key="test-key", model="gemini-2.5-flash",
            confidence_threshold=0.6, cache_enabled=True,
        )

        # Pre-populate cache
        from event_dedup.ai_matching.cache import compute_pair_hash, store_cache
        from event_dedup.ai_matching.schemas import AIMatchResult as AIR

        evt_a = _make_event("a", "Event A")
        evt_b = _make_event("b", "Event B")
        pair_hash = compute_pair_hash(evt_a, evt_b)
        await store_cache(
            test_session_factory, pair_hash, "a", "b",
            AIR(decision="same", confidence=0.9, reasoning="Cached match"),
            "gemini-2.5-flash",
        )

        mock_create.return_value = AsyncMock()
        decisions = [_make_decision("a", "b", "ambiguous")]
        match_result = _make_match_result(decisions)

        result = await resolve_ambiguous_pairs(
            match_result, [evt_a, evt_b], ai_config, test_session_factory
        )

        # API was never called
        assert mock_call.call_count == 0
        assert result.match_count == 1
