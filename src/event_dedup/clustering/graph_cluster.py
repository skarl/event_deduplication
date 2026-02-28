"""Graph-based clustering using networkx connected components.

Builds an undirected graph from pairwise match decisions and extracts
connected components as event clusters.  Each component is validated
for coherence (size, internal similarity, date spread).
"""

from __future__ import annotations

from dataclasses import dataclass, field

import networkx as nx

from event_dedup.matching.config import ClusterConfig
from event_dedup.matching.pipeline import MatchDecisionRecord

from .coherence import is_cluster_coherent


@dataclass
class ClusterResult:
    """Result of graph-based clustering.

    Attributes:
        clusters: Valid clusters (sets of event IDs), including singletons.
        flagged_clusters: Over-large or incoherent clusters requiring review.
        singleton_count: Number of single-event clusters.
        total_cluster_count: Total clusters including singletons and flagged.
    """

    clusters: list[set[str]] = field(default_factory=list)
    flagged_clusters: list[set[str]] = field(default_factory=list)
    singleton_count: int = 0
    total_cluster_count: int = 0


def cluster_matches(
    decisions: list[MatchDecisionRecord],
    all_event_ids: list[str],
    config: ClusterConfig,
    events_by_id: dict[str, dict] | None = None,
) -> ClusterResult:
    """Cluster events based on pairwise match decisions.

    Builds an undirected graph where nodes are event IDs and edges
    represent ``"match"`` decisions (weighted by combined score).
    Connected components become event clusters.  Each multi-event
    cluster is validated for coherence; incoherent clusters are
    flagged for review.

    Args:
        decisions: Pairwise match decisions from the scoring pipeline.
        all_event_ids: Complete list of event IDs (ensures singletons
            with no matches still appear as clusters).
        config: Clustering constraints (max size, min similarity).
        events_by_id: Optional mapping of event ID to event dict,
            used for date-spread coherence checks.

    Returns:
        A ``ClusterResult`` with valid clusters, flagged clusters,
        singleton count, and total cluster count.
    """
    G = nx.Graph()

    # Add all nodes first (ensures singletons with no matches get a cluster)
    for event_id in all_event_ids:
        G.add_node(event_id)

    # Add edges for match decisions only
    for decision in decisions:
        if decision.decision == "match":
            G.add_edge(
                decision.event_id_a,
                decision.event_id_b,
                weight=decision.combined_score_value,
            )

    components = list(nx.connected_components(G))
    clusters: list[set[str]] = []
    flagged: list[set[str]] = []
    singleton_count = 0

    for component in components:
        if len(component) == 1:
            clusters.append(component)
            singleton_count += 1
        elif is_cluster_coherent(component, G, config, events_by_id):
            clusters.append(component)
        else:
            flagged.append(component)

    return ClusterResult(
        clusters=clusters,
        flagged_clusters=flagged,
        singleton_count=singleton_count,
        total_cluster_count=len(components),
    )
