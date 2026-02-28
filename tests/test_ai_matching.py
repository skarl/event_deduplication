"""Tests for AI matching infrastructure.

All tests are self-contained -- no Gemini API key required.
Tests cover schemas, cache hashing, cost estimation, prompt formatting,
and DB cache operations.
"""
import hashlib
import json

import pytest

from event_dedup.ai_matching.cache import compute_pair_hash, lookup_cache, store_cache
from event_dedup.ai_matching.cost_tracker import estimate_cost, get_batch_summary, log_usage
from event_dedup.ai_matching.prompt import SYSTEM_PROMPT, format_event_pair
from event_dedup.ai_matching.schemas import AIMatchResult
from event_dedup.matching.combiner import SignalScores
from event_dedup.matching.config import AIMatchingConfig, MatchingConfig


# ---- Schema tests ----

class TestAIMatchResult:
    def test_valid_same(self):
        r = AIMatchResult(decision="same", confidence=0.95, reasoning="Same event")
        assert r.decision == "same"
        assert r.confidence == 0.95

    def test_valid_different(self):
        r = AIMatchResult(decision="different", confidence=0.8, reasoning="Different events")
        assert r.decision == "different"

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            AIMatchResult(decision="same", confidence=1.5, reasoning="test")
        with pytest.raises(Exception):
            AIMatchResult(decision="same", confidence=-0.1, reasoning="test")

    def test_json_roundtrip(self):
        r = AIMatchResult(decision="same", confidence=0.9, reasoning="Title match")
        j = r.model_dump_json()
        r2 = AIMatchResult.model_validate_json(j)
        assert r2.decision == r.decision
        assert r2.confidence == r.confidence


# ---- Config tests ----

class TestAIMatchingConfig:
    def test_defaults(self):
        cfg = AIMatchingConfig()
        assert cfg.enabled is False
        assert cfg.model == "gemini-2.5-flash"
        assert cfg.confidence_threshold == 0.6
        assert cfg.max_concurrent_requests == 5

    def test_in_matching_config(self):
        cfg = MatchingConfig()
        assert cfg.ai.enabled is False

    def test_from_yaml_dict(self):
        cfg = MatchingConfig(ai={"enabled": True, "api_key": "test-key"})
        assert cfg.ai.enabled is True
        assert cfg.ai.api_key == "test-key"
        assert cfg.ai.model == "gemini-2.5-flash"  # default preserved


# ---- Cache hash tests ----

class TestComputePairHash:
    def test_deterministic(self):
        a = {"id": "aaa", "title": "Event A", "description": "Desc A", "dates": [{"date": "2026-01-01"}], "categories": ["cat1"]}
        b = {"id": "bbb", "title": "Event B", "description": "Desc B", "dates": [{"date": "2026-01-02"}], "categories": ["cat2"]}
        h1 = compute_pair_hash(a, b)
        h2 = compute_pair_hash(a, b)
        assert h1 == h2
        assert len(h1) == 64  # SHA-256 hex

    def test_canonical_ordering(self):
        """Hash is the same regardless of argument order."""
        a = {"id": "aaa", "title": "Event A"}
        b = {"id": "bbb", "title": "Event B"}
        assert compute_pair_hash(a, b) == compute_pair_hash(b, a)

    def test_different_content_different_hash(self):
        a = {"id": "aaa", "title": "Event A"}
        b = {"id": "bbb", "title": "Event B"}
        c = {"id": "ccc", "title": "Event C"}
        assert compute_pair_hash(a, b) != compute_pair_hash(a, c)

    def test_ignores_non_content_fields(self):
        """Fields like batch_index or created_at don't affect the hash."""
        base = {"id": "aaa", "title": "Event A"}
        with_extra = {"id": "aaa", "title": "Event A", "batch_index": 5, "created_at": "2026-01-01"}
        b = {"id": "bbb", "title": "Event B"}
        assert compute_pair_hash(base, b) == compute_pair_hash(with_extra, b)


# ---- Cost estimation tests ----

class TestEstimateCost:
    def test_basic_cost(self):
        cfg = AIMatchingConfig()
        cost = estimate_cost(800, 100, cfg)
        # (800/1M * 0.30) + (100/1M * 2.50) = 0.00024 + 0.00025 = 0.00049
        assert abs(cost - 0.00049) < 0.00001

    def test_zero_tokens(self):
        cfg = AIMatchingConfig()
        assert estimate_cost(0, 0, cfg) == 0.0


# ---- Prompt formatting tests ----

class TestFormatEventPair:
    def test_basic_formatting(self):
        a = {
            "id": "aaa",
            "title": "Fasching in Freiburg",
            "description": "Annual carnival event",
            "source_code": "bwb",
            "source_type": "artikel",
            "location_name": "Marktplatz",
            "location_city": "Freiburg",
            "dates": [{"date": "2026-02-15", "start_time": "14:00"}],
            "categories": ["fasching"],
        }
        b = {
            "id": "bbb",
            "title": "Karneval Freiburg",
            "description": "Carnival celebration",
            "source_code": "rek",
            "source_type": "terminliste",
            "location_name": "Marktplatz",
            "location_city": "Freiburg",
            "dates": [{"date": "2026-02-15", "start_time": "14:30"}],
            "categories": ["karneval"],
        }
        signals = SignalScores(date=0.95, geo=1.0, title=0.65, description=0.50)
        prompt = format_event_pair(a, b, signals)

        assert "Fasching in Freiburg" in prompt
        assert "Karneval Freiburg" in prompt
        assert "Event A" in prompt
        assert "Event B" in prompt
        assert "Date similarity: 0.95" in prompt
        assert "Title similarity: 0.65" in prompt
        assert "ambiguous" in prompt.lower()

    def test_system_prompt_mentions_german(self):
        assert "German" in SYSTEM_PROMPT
        assert "artikel" in SYSTEM_PROMPT
        assert "terminliste" in SYSTEM_PROMPT


# ---- DB cache operations tests ----

class TestCacheDB:
    @pytest.fixture
    def sample_result(self):
        return AIMatchResult(decision="same", confidence=0.9, reasoning="Events match")

    async def test_store_and_lookup(self, test_session_factory, sample_result):
        pair_hash = "a" * 64
        model = "gemini-2.5-flash"

        await store_cache(
            test_session_factory, pair_hash,
            "evt-a", "evt-b", sample_result, model,
        )

        cached = await lookup_cache(test_session_factory, pair_hash, model)
        assert cached is not None
        assert cached.decision == "same"
        assert cached.confidence == 0.9

    async def test_lookup_miss(self, test_session_factory):
        cached = await lookup_cache(test_session_factory, "nonexistent" * 4, "gemini-2.5-flash")
        assert cached is None

    async def test_model_staleness(self, test_session_factory, sample_result):
        pair_hash = "b" * 64
        await store_cache(
            test_session_factory, pair_hash,
            "evt-a", "evt-b", sample_result, "gemini-2.0-flash",
        )
        # Lookup with different model returns None (stale)
        cached = await lookup_cache(test_session_factory, pair_hash, "gemini-2.5-flash")
        assert cached is None


# ---- Usage logging tests ----

class TestUsageLogging:
    async def test_log_and_summarize(self, test_session_factory):
        batch_id = "batch-001"

        await log_usage(
            test_session_factory, batch_id,
            "evt-a", "evt-b", "gemini-2.5-flash",
            prompt_tokens=800, completion_tokens=100,
            estimated_cost_usd=0.00049, cached=False,
        )
        await log_usage(
            test_session_factory, batch_id,
            "evt-c", "evt-d", "gemini-2.5-flash",
            prompt_tokens=0, completion_tokens=0,
            estimated_cost_usd=0.0, cached=True,
        )

        summary = await get_batch_summary(test_session_factory, batch_id)
        assert summary["total_requests"] == 2
        assert summary["cached_requests"] == 1
        assert summary["api_requests"] == 1
        assert summary["prompt_tokens"] == 800
        assert summary["estimated_cost_usd"] > 0
