"""Coherence validation for event clusters.

Checks whether a cluster of events is "coherent" -- i.e. the events
genuinely represent the same real-world event.  Incoherent clusters
(over-large, low internal similarity, excessive date spread) are
flagged for review rather than silently accepted.
"""

from __future__ import annotations

import networkx as nx

from event_dedup.matching.config import ClusterConfig


def is_cluster_coherent(
    cluster: set[str],
    graph: nx.Graph,
    config: ClusterConfig,
    events_by_id: dict[str, dict] | None = None,
) -> bool:
    """Check whether a cluster passes all coherence checks.

    Checks performed (in order, short-circuiting on first failure):

    1. **Size check** -- cluster must not exceed ``max_cluster_size``.
    2. **Internal similarity** -- average edge weight in the cluster
       subgraph must be at least ``min_internal_similarity``.
    3. **Date spread** (only if ``events_by_id`` provided) -- the
       cluster must not span more than 3 distinct dates.

    Args:
        cluster: Set of event IDs forming the cluster.
        graph: The full match graph (edges carry ``weight`` attribute).
        config: Clustering constraints.
        events_by_id: Optional mapping of event ID to event dict
            (must contain ``"dates"`` list with ``{"date": ...}`` dicts).

    Returns:
        ``True`` if the cluster is coherent, ``False`` otherwise.
    """
    # Size check
    if len(cluster) > config.max_cluster_size:
        return False

    # Internal similarity check
    subgraph = graph.subgraph(cluster)
    edge_weights = [d["weight"] for _, _, d in subgraph.edges(data=True)]
    if edge_weights:
        avg_weight = sum(edge_weights) / len(edge_weights)
        if avg_weight < config.min_internal_similarity:
            return False

    # Date spread check (only if events_by_id provided)
    if events_by_id:
        all_dates: set[str | None] = set()
        for eid in cluster:
            evt = events_by_id.get(eid, {})
            for d in evt.get("dates", []):
                all_dates.add(d.get("date"))
        all_dates.discard(None)
        if len(all_dates) > 3:
            return False

    return True
