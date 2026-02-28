"""Graph-based clustering for event deduplication.

Turns pairwise match decisions into event clusters using networkx
connected components, with coherence validation to flag suspicious clusters.
"""

from .graph_cluster import ClusterResult, cluster_matches

__all__ = ["cluster_matches", "ClusterResult"]
