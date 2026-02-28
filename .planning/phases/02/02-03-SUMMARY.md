---
phase: "02"
plan: "03"
subsystem: "graph-clustering"
tags: [clustering, networkx, connected-components, coherence, graph]
dependency-graph:
  requires: [02-01, 02-02]
  provides: [cluster-matches, cluster-result, coherence-validation]
  affects: [02-04]
tech-stack:
  added: []
  patterns: [connected-components, coherence-validation, flagged-clusters, date-spread-check]
key-files:
  created:
    - src/event_dedup/clustering/__init__.py
    - src/event_dedup/clustering/graph_cluster.py
    - src/event_dedup/clustering/coherence.py
    - tests/test_clustering.py
  modified: []
decisions:
  - "Singletons (unmatched events) included in clusters list as size-1 sets for downstream uniformity"
  - "Flagged clusters separated from valid clusters -- both tracked in ClusterResult for review workflows"
  - "Date spread limit of >3 distinct dates catches unrelated events bridged by false positives"
  - "Coherence checks short-circuit: size -> similarity -> date spread (cheapest first)"
metrics:
  duration: "~2 minutes"
  completed: "2026-02-28"
  tasks: 1
  tests-added: 17
  tests-total: 203
---

# Phase 2 Plan 3: Graph-Based Clustering with Coherence Validation

Networkx connected-components clustering over match-decision graph, with three-layer coherence validation (size, internal similarity, date spread) to flag suspicious clusters for review.

## What Was Built

### Clustering Module (`src/event_dedup/clustering/`)

**`graph_cluster.py` -- Core clustering logic**

- **`cluster_matches(decisions, all_event_ids, config, events_by_id=None)`** builds an undirected graph from `MatchDecisionRecord` list, adding edges only for `"match"` decisions (weighted by combined score). All event IDs are added as nodes to guarantee singletons appear. Connected components are extracted via `nx.connected_components`.
- **`ClusterResult`** dataclass tracks: `clusters` (valid, including singletons), `flagged_clusters` (over-large or incoherent), `singleton_count`, and `total_cluster_count`.
- Only `"match"` decisions create edges; `"no_match"` and `"ambiguous"` are ignored, so those events become singletons unless matched by another pair.

**`coherence.py` -- Cluster validation**

- **`is_cluster_coherent(cluster, graph, config, events_by_id=None)`** applies three checks in order (short-circuiting on first failure):
  1. **Size check** -- cluster must not exceed `max_cluster_size` (default 15)
  2. **Internal similarity** -- average edge weight in subgraph must be at least `min_internal_similarity` (default 0.40)
  3. **Date spread** -- if `events_by_id` provided, cluster must not span more than 3 distinct dates
- Checks are ordered cheapest-first for efficiency.

**`__init__.py` -- Public API**

- Re-exports `cluster_matches` and `ClusterResult` for clean imports.

### Tests (`tests/test_clustering.py`, 313 lines, 17 tests)

**Basic clustering (6 tests):**
- Two matched events form one cluster
- Transitive closure: A-B + B-C = {A, B, C}
- Separate clusters: A-B + C-D = two clusters
- Singleton events get their own cluster
- Mix of clusters and singletons
- `all_event_ids` ensures completeness (events not in decisions become singletons)

**Coherence / flagging (4 tests):**
- Over-large cluster flagged (chain of 20, max_cluster_size=15)
- Low-similarity cluster flagged (edge weights 0.30, min_internal_similarity=0.40)
- Coherent cluster passes (edge weights 0.80)
- No-match and ambiguous decisions ignored (events become singletons)

**Date spread coherence (3 tests):**
- 5 different dates -> flagged
- 2 dates -> coherent
- Without events_by_id, date check skipped

**Coherence unit tests (4 tests):**
- Size boundary: exactly max_cluster_size passes
- Size exceeded: max_cluster_size+1 fails
- Similarity boundary: exactly min_internal_similarity passes
- Three dates passes (limit is >3, not >=3)

All 203 project tests pass with no regressions.

## Commits

| Hash | Type | Description |
|------|------|-------------|
| `f1c3f16` | feat | Add graph-based clustering with coherence validation |

## Deviations from Plan

None -- plan executed exactly as written.

## Self-Check: PASSED

- All 4 created files verified on disk
- Commit f1c3f16 verified in git log
- All 203 tests passing (17 new + 186 existing)
