"""Tests for graph-based clustering with coherence validation."""

from __future__ import annotations

import pytest

from event_dedup.clustering import ClusterResult, cluster_matches
from event_dedup.clustering.coherence import is_cluster_coherent
from event_dedup.matching.combiner import SignalScores
from event_dedup.matching.config import ClusterConfig
from event_dedup.matching.pipeline import MatchDecisionRecord


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_decision(
    id_a: str,
    id_b: str,
    decision: str = "match",
    score: float = 0.80,
) -> MatchDecisionRecord:
    """Create a MatchDecisionRecord with sensible defaults."""
    return MatchDecisionRecord(
        event_id_a=id_a,
        event_id_b=id_b,
        signals=SignalScores(date=score, geo=score, title=score, description=score),
        combined_score_value=score,
        decision=decision,
    )


def _default_config(**overrides) -> ClusterConfig:
    """Create a ClusterConfig with optional overrides."""
    return ClusterConfig(**overrides)


def _cluster_sets(result: ClusterResult) -> list[frozenset[str]]:
    """Convert cluster list to sorted frozensets for easier assertion."""
    return sorted(frozenset(c) for c in result.clusters)


def _flagged_sets(result: ClusterResult) -> list[frozenset[str]]:
    """Convert flagged cluster list to sorted frozensets."""
    return sorted(frozenset(c) for c in result.flagged_clusters)


# ---------------------------------------------------------------------------
# Basic clustering tests
# ---------------------------------------------------------------------------

class TestBasicClustering:
    """Tests for basic connected-component clustering behaviour."""

    def test_two_matched_events_form_one_cluster(self):
        """Two events with a match decision form a single cluster."""
        decisions = [_make_decision("A", "B")]
        result = cluster_matches(decisions, ["A", "B"], _default_config())

        assert len(result.clusters) == 1
        assert {"A", "B"} in result.clusters
        assert result.flagged_clusters == []
        assert result.singleton_count == 0
        assert result.total_cluster_count == 1

    def test_transitive_closure(self):
        """A-B match + B-C match produces a single {A, B, C} cluster."""
        decisions = [
            _make_decision("A", "B"),
            _make_decision("B", "C"),
        ]
        result = cluster_matches(decisions, ["A", "B", "C"], _default_config())

        assert len(result.clusters) == 1
        assert {"A", "B", "C"} in result.clusters
        assert result.total_cluster_count == 1

    def test_separate_clusters(self):
        """A-B match + C-D match (no link) produces 2 separate clusters."""
        decisions = [
            _make_decision("A", "B"),
            _make_decision("C", "D"),
        ]
        result = cluster_matches(
            decisions, ["A", "B", "C", "D"], _default_config()
        )

        clusters = _cluster_sets(result)
        assert frozenset({"A", "B"}) in clusters
        assert frozenset({"C", "D"}) in clusters
        assert result.total_cluster_count == 2
        assert result.singleton_count == 0

    def test_singleton_events(self):
        """Events with no matches become singleton clusters."""
        result = cluster_matches([], ["E", "F"], _default_config())

        assert result.singleton_count == 2
        assert result.total_cluster_count == 2
        assert len(result.clusters) == 2
        assert {"E"} in result.clusters
        assert {"F"} in result.clusters

    def test_mix_of_clusters_and_singletons(self):
        """A-B match + standalone C gives 2 clusters, 1 singleton."""
        decisions = [_make_decision("A", "B")]
        result = cluster_matches(decisions, ["A", "B", "C"], _default_config())

        assert result.total_cluster_count == 2
        assert result.singleton_count == 1
        assert {"A", "B"} in result.clusters
        assert {"C"} in result.clusters

    def test_all_event_ids_ensures_completeness(self):
        """Events not in any decision still appear as singleton clusters."""
        decisions = [_make_decision("A", "B")]
        result = cluster_matches(
            decisions, ["A", "B", "X", "Y", "Z"], _default_config()
        )

        assert result.total_cluster_count == 4  # {A,B}, {X}, {Y}, {Z}
        assert result.singleton_count == 3
        assert {"A", "B"} in result.clusters
        assert {"X"} in result.clusters
        assert {"Y"} in result.clusters
        assert {"Z"} in result.clusters


# ---------------------------------------------------------------------------
# Coherence / flagging tests
# ---------------------------------------------------------------------------

class TestCoherence:
    """Tests for coherence validation and cluster flagging."""

    def test_overlarge_cluster_flagged(self):
        """A chain of 20 events exceeds max_cluster_size=15 and is flagged."""
        # Chain: e0-e1, e1-e2, ..., e18-e19  (20 events in one component)
        event_ids = [f"e{i}" for i in range(20)]
        decisions = [
            _make_decision(f"e{i}", f"e{i+1}", score=0.80)
            for i in range(19)
        ]
        config = _default_config(max_cluster_size=15)
        result = cluster_matches(decisions, event_ids, config)

        assert len(result.flagged_clusters) == 1
        assert set(event_ids) in result.flagged_clusters
        # The flagged cluster should NOT appear in valid clusters
        for c in result.clusters:
            assert len(c) == 1 or c != set(event_ids)

    def test_low_similarity_cluster_flagged(self):
        """Cluster with avg edge weight 0.30 < min_internal_similarity=0.40."""
        decisions = [
            _make_decision("A", "B", score=0.30),
            _make_decision("B", "C", score=0.30),
            _make_decision("A", "C", score=0.30),
        ]
        config = _default_config(min_internal_similarity=0.40)
        result = cluster_matches(decisions, ["A", "B", "C"], config)

        flagged = _flagged_sets(result)
        assert frozenset({"A", "B", "C"}) in flagged
        # Should not be in valid clusters
        for c in result.clusters:
            assert c != {"A", "B", "C"}

    def test_coherent_cluster_passes(self):
        """Cluster with high edge weights passes coherence checks."""
        decisions = [
            _make_decision("A", "B", score=0.80),
            _make_decision("B", "C", score=0.80),
            _make_decision("A", "C", score=0.80),
        ]
        config = _default_config(min_internal_similarity=0.40)
        result = cluster_matches(decisions, ["A", "B", "C"], config)

        assert {"A", "B", "C"} in result.clusters
        assert result.flagged_clusters == []

    def test_no_match_and_ambiguous_decisions_ignored(self):
        """Only 'match' decisions create edges; others are ignored."""
        decisions = [
            _make_decision("A", "B", decision="no_match"),
            _make_decision("C", "D", decision="ambiguous"),
        ]
        result = cluster_matches(
            decisions, ["A", "B", "C", "D"], _default_config()
        )

        # All events should be singletons since no "match" edges
        assert result.singleton_count == 4
        assert result.total_cluster_count == 4
        assert len(result.flagged_clusters) == 0


# ---------------------------------------------------------------------------
# Date spread coherence tests
# ---------------------------------------------------------------------------

class TestDateSpreadCoherence:
    """Tests for date-spread coherence checking."""

    def test_five_different_dates_flagged(self):
        """Cluster spanning 5 different dates is flagged."""
        decisions = [
            _make_decision("A", "B", score=0.80),
            _make_decision("B", "C", score=0.80),
        ]
        events_by_id = {
            "A": {"dates": [{"date": "2026-01-01"}, {"date": "2026-01-02"}]},
            "B": {"dates": [{"date": "2026-01-03"}, {"date": "2026-01-04"}]},
            "C": {"dates": [{"date": "2026-01-05"}]},
        }
        config = _default_config()
        result = cluster_matches(
            decisions, ["A", "B", "C"], config, events_by_id=events_by_id
        )

        flagged = _flagged_sets(result)
        assert frozenset({"A", "B", "C"}) in flagged

    def test_two_dates_coherent(self):
        """Cluster spanning only 2 dates is coherent."""
        decisions = [
            _make_decision("A", "B", score=0.80),
            _make_decision("B", "C", score=0.80),
        ]
        events_by_id = {
            "A": {"dates": [{"date": "2026-03-01"}]},
            "B": {"dates": [{"date": "2026-03-01"}]},
            "C": {"dates": [{"date": "2026-03-02"}]},
        }
        config = _default_config()
        result = cluster_matches(
            decisions, ["A", "B", "C"], config, events_by_id=events_by_id
        )

        assert {"A", "B", "C"} in result.clusters
        assert result.flagged_clusters == []

    def test_date_spread_not_checked_without_events_by_id(self):
        """Without events_by_id, date spread check is skipped."""
        decisions = [
            _make_decision("A", "B", score=0.80),
            _make_decision("B", "C", score=0.80),
        ]
        # No events_by_id passed -- should be coherent (date check skipped)
        config = _default_config()
        result = cluster_matches(decisions, ["A", "B", "C"], config)

        assert {"A", "B", "C"} in result.clusters
        assert result.flagged_clusters == []


# ---------------------------------------------------------------------------
# Coherence function unit tests
# ---------------------------------------------------------------------------

class TestIsClusterCoherent:
    """Direct unit tests for is_cluster_coherent."""

    def test_size_check_boundary(self):
        """Cluster of exactly max_cluster_size is coherent."""
        import networkx as nx

        G = nx.Graph()
        ids = [f"n{i}" for i in range(15)]
        for i in range(14):
            G.add_edge(ids[i], ids[i + 1], weight=0.80)
        config = _default_config(max_cluster_size=15)

        assert is_cluster_coherent(set(ids), G, config) is True

    def test_size_check_exceeds(self):
        """Cluster exceeding max_cluster_size is incoherent."""
        import networkx as nx

        G = nx.Graph()
        ids = [f"n{i}" for i in range(16)]
        for i in range(15):
            G.add_edge(ids[i], ids[i + 1], weight=0.80)
        config = _default_config(max_cluster_size=15)

        assert is_cluster_coherent(set(ids), G, config) is False

    def test_similarity_boundary(self):
        """Avg weight exactly at min_internal_similarity passes."""
        import networkx as nx

        G = nx.Graph()
        G.add_edge("A", "B", weight=0.40)
        config = _default_config(min_internal_similarity=0.40)

        assert is_cluster_coherent({"A", "B"}, G, config) is True

    def test_three_dates_passes(self):
        """Exactly 3 distinct dates is still coherent (limit is >3)."""
        import networkx as nx

        G = nx.Graph()
        G.add_edge("A", "B", weight=0.80)
        G.add_edge("B", "C", weight=0.80)
        events = {
            "A": {"dates": [{"date": "2026-01-01"}]},
            "B": {"dates": [{"date": "2026-01-02"}]},
            "C": {"dates": [{"date": "2026-01-03"}]},
        }
        config = _default_config()

        assert is_cluster_coherent({"A", "B", "C"}, G, config, events) is True
