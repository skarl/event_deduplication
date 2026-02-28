"""Tests for the blocking-based candidate pair generator."""

import pytest

from event_dedup.matching.candidate_pairs import (
    CandidatePairStats,
    _count_cross_source_pairs,
    generate_candidate_pairs,
)


def _evt(id: str, source: str, keys: list[str]) -> dict:
    """Shorthand to create a minimal event dict for pair-generation tests."""
    return {"id": id, "source_code": source, "blocking_keys": keys}


class TestGenerateCandidatePairs:
    """Tests for generate_candidate_pairs."""

    def test_two_events_different_sources_one_pair(self) -> None:
        """Two events sharing a blocking key from different sources -> 1 pair."""
        events = [
            _evt("a1", "src_a", ["2026-03-01:freiburg"]),
            _evt("b1", "src_b", ["2026-03-01:freiburg"]),
        ]
        pairs, stats = generate_candidate_pairs(events)
        assert pairs == [("a1", "b1")]
        assert stats.blocked_pairs == 1

    def test_two_events_same_source_no_pairs(self) -> None:
        """Two events from the SAME source sharing a key -> 0 pairs."""
        events = [
            _evt("a1", "src_a", ["2026-03-01:freiburg"]),
            _evt("a2", "src_a", ["2026-03-01:freiburg"]),
        ]
        pairs, stats = generate_candidate_pairs(events)
        assert pairs == []
        assert stats.blocked_pairs == 0

    def test_three_events_two_sources(self) -> None:
        """3 events in same block: 2 from src_a, 1 from src_b -> 2 cross-source pairs."""
        events = [
            _evt("a1", "src_a", ["2026-03-01:freiburg"]),
            _evt("a2", "src_a", ["2026-03-01:freiburg"]),
            _evt("b1", "src_b", ["2026-03-01:freiburg"]),
        ]
        pairs, stats = generate_candidate_pairs(events)
        assert len(pairs) == 2
        assert ("a1", "b1") in pairs
        assert ("a2", "b1") in pairs

    def test_canonical_ordering(self) -> None:
        """Pairs always have id_a < id_b regardless of input order."""
        events = [
            _evt("z99", "src_a", ["key1"]),
            _evt("a01", "src_b", ["key1"]),
        ]
        pairs, _ = generate_candidate_pairs(events)
        assert pairs == [("a01", "z99")]

    def test_deduplication_across_blocking_groups(self) -> None:
        """Events sharing multiple blocking keys produce each pair only once."""
        events = [
            _evt("a1", "src_a", ["key1", "key2", "key3"]),
            _evt("b1", "src_b", ["key1", "key2", "key3"]),
        ]
        pairs, stats = generate_candidate_pairs(events)
        assert pairs == [("a1", "b1")]
        assert stats.blocked_pairs == 1

    def test_no_shared_blocking_keys(self) -> None:
        """Events with disjoint blocking keys -> 0 pairs."""
        events = [
            _evt("a1", "src_a", ["key_x"]),
            _evt("b1", "src_b", ["key_y"]),
        ]
        pairs, stats = generate_candidate_pairs(events)
        assert pairs == []
        assert stats.blocked_pairs == 0

    def test_empty_blocking_keys(self) -> None:
        """Events with no blocking keys -> 0 pairs."""
        events = [
            _evt("a1", "src_a", []),
            _evt("b1", "src_b", []),
        ]
        pairs, stats = generate_candidate_pairs(events)
        assert pairs == []

    def test_none_blocking_keys(self) -> None:
        """Events with None blocking_keys field -> 0 pairs."""
        events = [
            {"id": "a1", "source_code": "src_a", "blocking_keys": None},
            {"id": "b1", "source_code": "src_b", "blocking_keys": None},
        ]
        pairs, _ = generate_candidate_pairs(events)
        assert pairs == []

    def test_reduction_stats(self) -> None:
        """Blocking should reduce pairs vs naive all-pairs comparison."""
        # 3 sources: src_a(3 events), src_b(3 events), src_c(4 events)
        # Total cross-source: 3*3 + 3*4 + 3*4 = 9 + 12 + 12 = 33
        # Only some share blocking keys -> blocked < 33
        events = [
            _evt("a1", "src_a", ["key1"]),
            _evt("a2", "src_a", ["key2"]),
            _evt("a3", "src_a", ["key3"]),
            _evt("b1", "src_b", ["key1"]),
            _evt("b2", "src_b", ["key2"]),
            _evt("b3", "src_b", ["key3"]),
            _evt("c1", "src_c", ["key1"]),
            _evt("c2", "src_c", ["key2"]),
            _evt("c3", "src_c", ["key4"]),
            _evt("c4", "src_c", ["key5"]),
        ]
        pairs, stats = generate_candidate_pairs(events)
        assert stats.total_events == 10
        assert stats.total_possible_pairs == 33  # 3*3 + 3*4 + 3*4
        assert stats.blocked_pairs < stats.total_possible_pairs
        assert stats.reduction_pct > 50.0

    def test_stats_dataclass_fields(self) -> None:
        """CandidatePairStats has all expected fields."""
        events = [
            _evt("a1", "src_a", ["k1"]),
            _evt("b1", "src_b", ["k1"]),
        ]
        _, stats = generate_candidate_pairs(events)
        assert isinstance(stats, CandidatePairStats)
        assert stats.total_events == 2
        assert stats.total_possible_pairs == 1
        assert stats.blocked_pairs == 1
        assert stats.reduction_pct == pytest.approx(0.0)

    def test_empty_events_list(self) -> None:
        """Empty event list -> empty pairs and zero stats."""
        pairs, stats = generate_candidate_pairs([])
        assert pairs == []
        assert stats.total_events == 0
        assert stats.total_possible_pairs == 0
        assert stats.blocked_pairs == 0
        assert stats.reduction_pct == 0.0

    def test_pairs_are_sorted(self) -> None:
        """Returned pairs list is sorted."""
        events = [
            _evt("z1", "src_a", ["k1"]),
            _evt("a1", "src_b", ["k1"]),
            _evt("m1", "src_c", ["k1"]),
        ]
        pairs, _ = generate_candidate_pairs(events)
        assert pairs == sorted(pairs)


class TestCountCrossSourcePairs:
    """Tests for the _count_cross_source_pairs helper."""

    def test_two_sources(self) -> None:
        events = [
            _evt("a1", "src_a", []),
            _evt("a2", "src_a", []),
            _evt("b1", "src_b", []),
        ]
        assert _count_cross_source_pairs(events) == 2  # 2 * 1

    def test_three_sources(self) -> None:
        events = [
            _evt("a1", "src_a", []),
            _evt("a2", "src_a", []),
            _evt("b1", "src_b", []),
            _evt("b2", "src_b", []),
            _evt("c1", "src_c", []),
        ]
        # 2*2 + 2*1 + 2*1 = 4 + 2 + 2 = 8
        assert _count_cross_source_pairs(events) == 8

    def test_single_source(self) -> None:
        events = [_evt("a1", "src_a", []), _evt("a2", "src_a", [])]
        assert _count_cross_source_pairs(events) == 0

    def test_empty(self) -> None:
        assert _count_cross_source_pairs([]) == 0

    def test_one_event_per_source(self) -> None:
        """n sources with 1 event each -> n*(n-1)/2 pairs."""
        events = [_evt(f"e{i}", f"src_{i}", []) for i in range(5)]
        assert _count_cross_source_pairs(events) == 10  # 5*4/2
