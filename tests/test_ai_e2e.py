"""End-to-end integration test for AI matching pipeline.

Verifies the full flow: deterministic scoring -> AI resolution (mocked) ->
re-clustering -> persistence -> database state verification.
"""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from sqlalchemy import func, select

from event_dedup.ai_matching.schemas import AIMatchResult
from event_dedup.matching.candidate_pairs import CandidatePairStats
from event_dedup.matching.combiner import SignalScores
from event_dedup.matching.config import AIMatchingConfig, MatchingConfig
from event_dedup.matching.pipeline import (
    MatchDecisionRecord,
    MatchResult,
    _cluster_has_ai_decisions,
    rebuild_pipeline_result,
)
from event_dedup.models.ai_match_cache import AIMatchCache
from event_dedup.models.ai_usage_log import AIUsageLog
from event_dedup.models.canonical_event import CanonicalEvent
from event_dedup.models.match_decision import MatchDecision
from event_dedup.worker.orchestrator import _maybe_resolve_ai
from event_dedup.worker.persistence import replace_canonical_events


# ---- Helpers ----


def _make_event(id: str, title: str, city: str = "Freiburg") -> dict:
    """Create a minimal event dict with blocking keys for pipeline compatibility."""
    return {
        "id": id,
        "title": title,
        "title_normalized": title.lower(),
        "short_description": f"Description of {title}",
        "short_description_normalized": f"description of {title}".lower(),
        "description": f"Long description of {title}",
        "highlights": None,
        "location_name": "Marktplatz",
        "location_city": city,
        "location_district": None,
        "location_street": None,
        "location_zipcode": "79098",
        "geo_latitude": 48.0,
        "geo_longitude": 7.85,
        "geo_confidence": 0.9,
        "source_code": "bwb",
        "source_type": "artikel",
        "blocking_keys": [f"{city.lower()}_2026-01"],
        "categories": ["test"],
        "is_family_event": False,
        "is_child_focused": False,
        "admission_free": True,
        "dates": [{"date": "2026-01-15", "start_time": "10:00", "end_time": None, "end_date": None}],
    }


# ---- Unit tests for _cluster_has_ai_decisions ----


class TestClusterHasAIDecisions:
    def test_no_ai_decisions(self):
        cluster = {"a", "b"}
        decisions = [
            MatchDecisionRecord("a", "b", SignalScores(0.9, 0.9, 0.9, 0.9), 0.9, "match", "deterministic"),
        ]
        assert _cluster_has_ai_decisions(cluster, decisions) is False

    def test_has_ai_decision(self):
        cluster = {"a", "b"}
        decisions = [
            MatchDecisionRecord("a", "b", SignalScores(0.9, 0.9, 0.9, 0.9), 0.9, "match", "ai"),
        ]
        assert _cluster_has_ai_decisions(cluster, decisions) is True

    def test_has_ai_low_confidence(self):
        cluster = {"a", "b"}
        decisions = [
            MatchDecisionRecord("a", "b", SignalScores(0.5, 0.5, 0.5, 0.5), 0.5, "ambiguous", "ai_low_confidence"),
        ]
        assert _cluster_has_ai_decisions(cluster, decisions) is True

    def test_ai_decision_outside_cluster(self):
        cluster = {"a", "b"}
        decisions = [
            MatchDecisionRecord("c", "d", SignalScores(0.9, 0.9, 0.9, 0.9), 0.9, "match", "ai"),
        ]
        assert _cluster_has_ai_decisions(cluster, decisions) is False

    def test_empty_cluster(self):
        cluster = {"a"}
        decisions: list[MatchDecisionRecord] = []
        assert _cluster_has_ai_decisions(cluster, decisions) is False


# ---- Integration test: full pipeline -> AI -> persistence ----


class TestAIMatchingE2E:
    """End-to-end test: pipeline scoring -> AI resolution -> persistence."""

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_full_flow_ai_resolves_ambiguous_pair(
        self, mock_create, mock_call, test_session_factory
    ):
        """
        Full E2E: Two similar events score as ambiguous -> AI resolves to match ->
        rebuild produces canonical with ai_assisted=True -> persistence writes it
        to DB -> cache and cost log entries exist.
        """
        # Setup: Mock Gemini to return "same" with high confidence
        mock_create.return_value = AsyncMock()
        mock_call.return_value = (
            AIMatchResult(decision="same", confidence=0.9, reasoning="Same event"),
            800,  # prompt tokens
            100,  # completion tokens
        )

        # Create two events that share a blocking key (so they form a candidate pair)
        events = [
            _make_event("pdf-aaa-0-0", "Fasching im Schwarzwald"),
            _make_event("pdf-bbb-0-0", "Fasching im Schwarzwald"),
        ]

        # Build a MatchResult with one ambiguous decision (simulating deterministic scoring)
        ambiguous_decision = MatchDecisionRecord(
            event_id_a="pdf-aaa-0-0",
            event_id_b="pdf-bbb-0-0",
            signals=SignalScores(date=0.95, geo=1.0, title=0.55, description=0.4),
            combined_score_value=0.70,
            decision="ambiguous",
            tier="deterministic",
        )
        match_result = MatchResult(
            decisions=[ambiguous_decision],
            pair_stats=CandidatePairStats(
                total_events=2, total_possible_pairs=1, blocked_pairs=1, reduction_pct=0.0
            ),
            match_count=0,
            ambiguous_count=1,
            no_match_count=0,
        )

        # Create matching config with AI enabled
        matching_config = MatchingConfig()
        matching_config.ai = AIMatchingConfig(
            enabled=True,
            api_key="test-key-fake",
            model="gemini-2.5-flash",
            confidence_threshold=0.6,
            cache_enabled=True,
            max_concurrent_requests=5,
        )

        # Step 1: Build initial pipeline result (just clustering + synthesis from the ambiguous result)
        initial_result = rebuild_pipeline_result(match_result, events, matching_config)

        # At this point, the ambiguous pair does NOT create a match edge,
        # so each event is its own singleton cluster
        assert initial_result.canonical_count == 2
        # Singletons have no ai_assisted
        for ce in initial_result.canonical_events:
            assert ce.get("ai_assisted") is False

        # Step 2: Run AI resolution via orchestrator helper
        resolved_result = await _maybe_resolve_ai(
            initial_result, events, matching_config, test_session_factory
        )

        # AI resolved the ambiguous pair to "match", so now they cluster together
        assert resolved_result.canonical_count == 1
        assert resolved_result.match_result.match_count == 1
        assert resolved_result.match_result.ambiguous_count == 0

        # The single canonical event should be AI-assisted
        canonical_dict = resolved_result.canonical_events[0]
        assert canonical_dict["ai_assisted"] is True

        # Verify the resolved decision has tier="ai"
        resolved_decisions = [
            d for d in resolved_result.match_result.decisions
            if d.decision == "match"
        ]
        assert len(resolved_decisions) == 1
        assert resolved_decisions[0].tier == "ai"

        # Step 3: Persist to database
        async with test_session_factory() as session, session.begin():
            count = await replace_canonical_events(session, resolved_result)
        assert count == 1

        # Step 4: Verify canonical event in DB has ai_assisted=True
        async with test_session_factory() as session:
            result = await session.execute(select(CanonicalEvent))
            db_canonicals = result.scalars().all()
            assert len(db_canonicals) == 1
            assert db_canonicals[0].ai_assisted is True
            assert db_canonicals[0].source_count == 2

        # Step 5: Verify match decision in DB has tier="ai"
        async with test_session_factory() as session:
            result = await session.execute(select(MatchDecision))
            db_decisions = result.scalars().all()
            match_decisions = [d for d in db_decisions if d.decision == "match"]
            assert len(match_decisions) == 1
            assert match_decisions[0].tier == "ai"

        # Step 6: Verify cache was populated
        async with test_session_factory() as session:
            result = await session.execute(
                select(func.count(AIMatchCache.id))
            )
            cache_count = result.scalar()
            assert cache_count >= 1, "AI match cache should have at least 1 entry"

        # Step 7: Verify usage log was populated
        async with test_session_factory() as session:
            result = await session.execute(
                select(func.count(AIUsageLog.id))
            )
            usage_count = result.scalar()
            assert usage_count >= 1, "AI usage log should have at least 1 entry"

            # Verify token counts are correct
            result = await session.execute(
                select(AIUsageLog).where(AIUsageLog.cached == False)  # noqa: E712
            )
            api_log = result.scalar_one()
            assert api_log.prompt_tokens == 800
            assert api_log.completion_tokens == 100

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_deterministic_only_no_ai_flag(
        self, mock_create, mock_call, test_session_factory
    ):
        """
        When all pairs are deterministic matches (no ambiguous), ai_assisted stays False.
        Gemini should not be called at all.
        """
        mock_create.return_value = AsyncMock()

        events = [
            _make_event("pdf-aaa-0-0", "Fasching im Schwarzwald"),
            _make_event("pdf-bbb-0-0", "Fasching im Schwarzwald"),
        ]

        # All-match result (no ambiguous)
        match_decision = MatchDecisionRecord(
            event_id_a="pdf-aaa-0-0",
            event_id_b="pdf-bbb-0-0",
            signals=SignalScores(date=0.95, geo=1.0, title=0.9, description=0.8),
            combined_score_value=0.9,
            decision="match",
            tier="deterministic",
        )
        match_result = MatchResult(
            decisions=[match_decision],
            pair_stats=CandidatePairStats(
                total_events=2, total_possible_pairs=1, blocked_pairs=1, reduction_pct=0.0
            ),
            match_count=1,
            ambiguous_count=0,
            no_match_count=0,
        )

        matching_config = MatchingConfig()
        matching_config.ai = AIMatchingConfig(
            enabled=True,
            api_key="test-key-fake",
            model="gemini-2.5-flash",
            confidence_threshold=0.6,
            cache_enabled=True,
        )

        # Build pipeline result
        pipeline_result = rebuild_pipeline_result(match_result, events, matching_config)
        assert pipeline_result.canonical_count == 1
        assert pipeline_result.canonical_events[0]["ai_assisted"] is False

        # AI resolution should be a no-op (no ambiguous pairs)
        resolved_result = await _maybe_resolve_ai(
            pipeline_result, events, matching_config, test_session_factory
        )
        assert resolved_result.canonical_events[0]["ai_assisted"] is False

        # Gemini was never called
        mock_call.assert_not_called()

        # Persist and verify
        async with test_session_factory() as session, session.begin():
            await replace_canonical_events(session, resolved_result)

        async with test_session_factory() as session:
            result = await session.execute(select(CanonicalEvent))
            db_canonical = result.scalar_one()
            assert db_canonical.ai_assisted is False

    @patch("event_dedup.ai_matching.resolver.call_gemini")
    @patch("event_dedup.ai_matching.resolver.create_client")
    async def test_mixed_clusters_only_ai_cluster_flagged(
        self, mock_create, mock_call, test_session_factory
    ):
        """
        Two clusters: one resolved by AI (ai_assisted=True),
        one deterministic (ai_assisted=False).
        """
        mock_create.return_value = AsyncMock()
        mock_call.return_value = (
            AIMatchResult(decision="same", confidence=0.85, reasoning="Same event"),
            600, 80,
        )

        events = [
            _make_event("pdf-aaa-0-0", "Event A1"),
            _make_event("pdf-bbb-0-0", "Event A2"),
            _make_event("pdf-ccc-0-0", "Event B1"),
            _make_event("pdf-ddd-0-0", "Event B2"),
        ]

        decisions = [
            # Pair 1: ambiguous -> will be AI-resolved to match
            MatchDecisionRecord(
                "pdf-aaa-0-0", "pdf-bbb-0-0",
                SignalScores(0.9, 0.9, 0.55, 0.4), 0.70, "ambiguous", "deterministic",
            ),
            # Pair 2: deterministic match
            MatchDecisionRecord(
                "pdf-ccc-0-0", "pdf-ddd-0-0",
                SignalScores(0.95, 1.0, 0.9, 0.85), 0.92, "match", "deterministic",
            ),
        ]
        match_result = MatchResult(
            decisions=decisions,
            pair_stats=CandidatePairStats(
                total_events=4, total_possible_pairs=6, blocked_pairs=2, reduction_pct=66.7
            ),
            match_count=1,
            ambiguous_count=1,
            no_match_count=0,
        )

        matching_config = MatchingConfig()
        matching_config.ai = AIMatchingConfig(
            enabled=True, api_key="test-key", model="gemini-2.5-flash",
            confidence_threshold=0.6, cache_enabled=True, max_concurrent_requests=5,
        )

        initial_result = rebuild_pipeline_result(match_result, events, matching_config)
        resolved_result = await _maybe_resolve_ai(
            initial_result, events, matching_config, test_session_factory
        )

        # Should have 2 canonical events (2 clusters, each with 2 events)
        assert resolved_result.canonical_count == 2

        # Find which canonical is AI-assisted
        ai_canonicals = [c for c in resolved_result.canonical_events if c["ai_assisted"]]
        det_canonicals = [c for c in resolved_result.canonical_events if not c["ai_assisted"]]
        assert len(ai_canonicals) == 1
        assert len(det_canonicals) == 1

        # Persist and verify
        async with test_session_factory() as session, session.begin():
            await replace_canonical_events(session, resolved_result)

        async with test_session_factory() as session:
            result = await session.execute(select(CanonicalEvent))
            db_canonicals = result.scalars().all()
            ai_count = sum(1 for c in db_canonicals if c.ai_assisted)
            det_count = sum(1 for c in db_canonicals if not c.ai_assisted)
            assert ai_count == 1
            assert det_count == 1
