# Phase 2: Core Matching Pipeline - Research

**Researched:** 2026-02-27
**Domain:** Multi-signal scoring, graph clustering, canonical synthesis for German regional events
**Confidence:** HIGH

## Summary

This research covers the technical HOW for Phase 2's core matching pipeline. The Phase 1 codebase provides a solid foundation: 765 events with normalized fields, blocking keys (date+city, date+geo_grid), and an evaluation harness with 1181 labeled ground truth pairs (248 same, 933 different).

The key findings are: (1) rapidfuzz 3.14.3 is already installed and `token_sort_ratio` combined with `token_set_ratio` provides the best coverage for German event titles -- empirically verified with real title patterns; (2) a pure-Python haversine function at 2.6M pairs/sec eliminates the need for geopy entirely; (3) networkx `connected_components` is O(n+m) and trivially handles 765 nodes; (4) the YAML + Pydantic pattern already used by the project (city_aliases.yaml, prefixes.yaml) should be extended for matching configuration; (5) date scoring should combine date-set overlap (Jaccard) with time-of-day tolerance.

**Primary recommendation:** Build four independent signal scorers (date, geo, title, description), a weighted combiner with YAML-driven configuration, networkx-based clustering with coherence validation, and field-level canonical synthesis with provenance tracking.

<user_constraints>
## User Constraints (from CONTEXT.md)

### Phase Goal
The system accurately deduplicates events using multi-signal scoring and graph-based clustering, producing canonical events that combine the best information from all sources.

### Requirements
MTCH-01, MTCH-02, MTCH-03, MTCH-04, MTCH-05, MTCH-06, MTCH-10, CANL-01, CANL-02, CANL-03, CANL-04

### Success Criteria
1. Processing the 765-event sample dataset produces canonical events where the same real-world event from different sources is grouped together, measured by F1 score against the ground truth dataset
2. Blocking reduces candidate comparisons by >95% (verified by comparing blocked vs. unblocked pair counts)
3. Canonical events contain the best field from each source (longest description, most precise location, richest highlights) with provenance tracking showing which source contributed each field
4. When new source events match an existing canonical event, the canonical is enriched with better information without losing existing good data
5. Similarity thresholds (high-confidence, ambiguous zone, auto-reject) can be changed via configuration without code changes

### Deferred to Later Phases
- AI-assisted matching (Phase 5) -- Phase 2 identifies the "ambiguous zone" but does not resolve it
- German dialect synonym dictionary (Phase 7) -- Phase 2 uses existing normalization from Phase 1
- Category-aware weights (Phase 7) -- Phase 2 uses uniform weights
- Source-type-aware weights (Phase 7) -- Phase 2 uses uniform weights
</user_constraints>

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MTCH-01 | Multi-signal scoring: date, geo, title, description | Signal scorers section: four independent scorers + weighted combiner |
| MTCH-02 | Blocking by date+city/geo grid for >95% reduction | Phase 1 blocking already implemented; candidate pair generator builds on it |
| MTCH-03 | Date matching with time tolerance + multi-day overlap | Date scoring section: Jaccard overlap + 30-min time tolerance |
| MTCH-04 | Geo-proximity with haversine weighted by confidence | Geo scoring section: math-based haversine + confidence weighting |
| MTCH-05 | Fuzzy title matching for German compound words | Title scoring section: token_sort_ratio + token_set_ratio combination |
| MTCH-06 | Configurable thresholds without code changes | Configuration section: YAML + Pydantic pattern |
| MTCH-10 | Graph-based clustering (connected components) | Clustering section: networkx connected_components + coherence validation |
| CANL-01 | Canonical synthesis: best field from each source | Canonical synthesis section: per-field strategies with selection rules |
| CANL-02 | Field-level provenance tracking | Provenance section: JSON dict mapping field->source_event_id |
| CANL-03 | Enrichment: update canonical when new sources arrive | Enrichment section: re-synthesis on new source addition |
| CANL-04 | Confidence score derived from signal scores | Combiner section: weighted sum produces 0-1 confidence |
</phase_requirements>

## Standard Stack

### Core (Phase 2 additions)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| networkx | >=3.4 | Graph clustering via connected_components | Standard graph library, O(n+m) connected components, pure Python, no compilation issues. At 765 events even worst-case is sub-millisecond. |
| pyyaml | >=6.0 | Matching config files | Already a dependency; used for prefixes.yaml and city_aliases.yaml |
| pydantic | >=2.9 | Config validation | Already a dependency; validates matching config at load time |

### Already Installed (from Phase 1)

| Library | Version | Purpose |
|---------|---------|---------|
| rapidfuzz | 3.14.3 | Fuzzy string matching (token_sort_ratio, token_set_ratio) |
| sqlalchemy | >=2.0 | ORM for new tables (canonical_events, match_decisions, etc.) |
| alembic | >=1.14 | Migrations for new tables |
| pydantic-settings | >=2.0 | Settings management |

### NOT Needed

| Library | Why Not |
|---------|---------|
| geopy | Math-based haversine is 2.6M pairs/sec, accurate to <1% error for <100km distances. No need for a dependency. |
| numpy | cdist is nice but we compare within blocking groups (5-50 events), not all-pairs. Loop-based comparison is 1.5M pairs/sec with rapidfuzz -- far more than needed. |
| scikit-learn | TF-IDF was considered for description matching but token_sort_ratio on normalized text is simpler, faster, and sufficient for 765 events. |

**Installation:**
```bash
uv add networkx
```

## Architecture Patterns

### Recommended Module Structure

```
src/event_dedup/
  matching/
    __init__.py
    config.py           # MatchingConfig (Pydantic model loaded from YAML)
    scorers/
      __init__.py
      date_scorer.py    # date_score(event_a, event_b) -> float
      geo_scorer.py     # geo_score(event_a, event_b) -> float
      title_scorer.py   # title_score(event_a, event_b) -> float
      desc_scorer.py    # description_score(event_a, event_b) -> float
    combiner.py         # weighted_score(signals, config) -> float
    candidate_pairs.py  # generate_candidate_pairs(events) -> list[tuple]
    pipeline.py         # run_matching_pipeline(events, config) -> MatchingResult
  clustering/
    __init__.py
    graph_cluster.py    # cluster_matches(match_pairs) -> list[set[str]]
    coherence.py        # validate_cluster(cluster, events) -> bool
  canonical/
    __init__.py
    synthesizer.py      # synthesize_canonical(cluster, events) -> CanonicalEvent
    enrichment.py       # enrich_canonical(canonical, new_source) -> CanonicalEvent
    provenance.py       # track_provenance(canonical, sources) -> dict
  models/
    canonical_event.py  # New SQLAlchemy model
    canonical_source.py # Linking table model
    match_decision.py   # Match decision audit model
config/
  matching.yaml         # Matching configuration file
```

### Pattern 1: Signal Scorer Protocol

**What:** Each signal scorer is an independent function returning a 0.0-1.0 similarity score.
**When to use:** Always -- this is the core abstraction for Phase 2.

```python
# Each scorer has the same signature for composability
def date_score(event_a: dict, event_b: dict) -> float:
    """Return 0.0-1.0 date similarity."""
    ...

def geo_score(event_a: dict, event_b: dict, config: GeoConfig) -> float:
    """Return 0.0-1.0 geo proximity similarity."""
    ...

def title_score(event_a: dict, event_b: dict) -> float:
    """Return 0.0-1.0 title similarity."""
    ...

def description_score(event_a: dict, event_b: dict) -> float:
    """Return 0.0-1.0 description similarity."""
    ...
```

### Pattern 2: Weighted Score Combiner

**What:** Combines individual signal scores using configurable weights from YAML.

```python
@dataclass
class SignalScores:
    date: float
    geo: float
    title: float
    description: float

def combined_score(signals: SignalScores, weights: dict[str, float]) -> float:
    """Weighted sum of signal scores, normalized to 0.0-1.0."""
    total = (
        signals.date * weights["date"]
        + signals.geo * weights["geo"]
        + signals.title * weights["title"]
        + signals.description * weights["description"]
    )
    weight_sum = sum(weights.values())
    return total / weight_sum if weight_sum > 0 else 0.0
```

### Pattern 3: Three-Tier Decision

**What:** Combined score maps to match/ambiguous/no_match using configurable thresholds.

```python
@dataclass
class MatchDecision:
    event_id_a: str
    event_id_b: str
    combined_score: float
    signals: SignalScores
    decision: str  # "match" | "ambiguous" | "no_match"
    tier: str = "deterministic"

def decide(score: float, config: ThresholdConfig) -> str:
    if score >= config.high_threshold:
        return "match"
    elif score <= config.low_threshold:
        return "no_match"
    else:
        return "ambiguous"
```

### Anti-Patterns to Avoid

- **Hardcoding thresholds in scorer functions:** All thresholds must come from configuration. Scorers return raw similarity; the combiner/decider applies thresholds.
- **Comparing events from the same source:** The blocking + candidate generation must enforce cross-source-only comparison (already done in Phase 1's harness).
- **Modifying source events during matching:** Source events are read-only inputs. All outputs go to new tables (canonical_events, match_decisions).
- **Re-comparing already-decided pairs:** Track which pairs have been scored and skip them. Use canonical pair ordering (id_a < id_b) as in Phase 1.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom edit distance | `rapidfuzz.fuzz.token_sort_ratio` + `token_set_ratio` | C++ core, 1.5M pairs/sec, handles Unicode/German correctly |
| Connected components | Union-find or BFS | `networkx.connected_components()` | O(n+m), tested, handles edge cases |
| YAML config parsing | Custom parser | `pyyaml` + `pydantic.BaseModel` | Type validation, defaults, error messages |
| Geodesic distance | geopy dependency | 5-line `math`-based haversine | 2.6M pairs/sec, <1% error at regional distances, zero deps |

## Signal Scorer Specifications

### 1. Date Scorer

**Goal:** Score date overlap between two events (MTCH-03).

**Algorithm:**
1. Expand each event's dates into a set of `date` objects (expanding date ranges via `end_date`)
2. Compute Jaccard overlap: `|intersection| / |union|`
3. If Jaccard > 0 AND both have start_time, apply time bonus/penalty:
   - Within 30 minutes: multiply by 1.0 (full credit)
   - 30-90 minutes apart: multiply by 0.7
   - >90 minutes apart on same day: multiply by 0.3 (likely different events at same venue)
4. If neither has time info, use Jaccard only (no penalty for missing data)

**Edge cases:**
- Event A has dates [Feb 12, Feb 13], event B has dates [Feb 12, Feb 13, Feb 14]: Jaccard = 2/3 = 0.67
- Event A has date [Feb 12 with end_date Feb 14], event B has [Feb 13]: overlap = {Feb 13}, union = {Feb 12, 13, 14} -> 1/3 = 0.33
- Events with no overlapping dates: 0.0 (this should not happen due to blocking, but handle defensively)

**Implementation:**
```python
import datetime as dt

def date_score(event_a: dict, event_b: dict) -> float:
    dates_a = _expand_dates(event_a["dates"])
    dates_b = _expand_dates(event_b["dates"])

    if not dates_a or not dates_b:
        return 0.0

    overlap = dates_a & dates_b
    union = dates_a | dates_b
    jaccard = len(overlap) / len(union)

    if jaccard == 0.0:
        return 0.0

    # Time bonus/penalty on overlapping dates
    time_factor = _time_proximity_factor(event_a["dates"], event_b["dates"], overlap)
    return jaccard * time_factor

def _expand_dates(date_list: list[dict]) -> set[dt.date]:
    result = set()
    for d in date_list:
        start = dt.date.fromisoformat(d["date"])
        end = dt.date.fromisoformat(d["end_date"]) if d.get("end_date") else start
        current = start
        while current <= end:
            result.add(current)
            current += dt.timedelta(days=1)
    return result

def _time_proximity_factor(
    dates_a: list[dict], dates_b: list[dict], overlap_dates: set[dt.date]
) -> float:
    """Compute time proximity factor for overlapping dates."""
    # Find earliest overlapping date with time info from both events
    for od in sorted(overlap_dates):
        time_a = _get_start_time_for_date(dates_a, od)
        time_b = _get_start_time_for_date(dates_b, od)
        if time_a and time_b:
            diff_min = abs(
                (dt.datetime.combine(od, time_a) - dt.datetime.combine(od, time_b))
                .total_seconds()
            ) / 60
            if diff_min <= 30:
                return 1.0
            elif diff_min <= 90:
                return 0.7
            else:
                return 0.3
    # No time data available on overlapping dates
    return 1.0
```

**Confidence:** HIGH -- empirically verified with test data.

### 2. Geo Scorer

**Goal:** Score geographic proximity weighted by confidence (MTCH-04).

**Algorithm:**
1. If either event lacks geo coordinates, return 0.5 (neutral -- don't penalize missing data)
2. Compute haversine distance in km
3. Apply confidence weighting: `effective_confidence = min(conf_a, conf_b)`
4. If effective confidence < 0.85, reduce the signal weight (return 0.5 = neutral)
5. Convert distance to similarity using `max(0.0, 1.0 - dist_km / max_distance_km)`

**Domain-calibrated thresholds:**
- 0 km: 1.0 (same coordinates -- likely same venue)
- 1 km: 0.9 (same village)
- 3 km: 0.7 (neighboring area)
- 5 km: 0.5 (nearby city)
- 10 km: 0.0 (different city -- Emmendingen to Kenzingen is ~10km)

The linear decay with `max_distance_km=10.0` fits the Breisgau region well:
- Emmendingen to Waldkirch: 8.9 km -> 0.11
- Emmendingen to Kenzingen: 9.9 km -> 0.01
- Emmendingen to Freiburg: 13.6 km -> 0.00

**Implementation:**
```python
import math

def geo_score(event_a: dict, event_b: dict, max_distance_km: float = 10.0) -> float:
    lat_a, lon_a = event_a.get("geo_latitude"), event_a.get("geo_longitude")
    lat_b, lon_b = event_b.get("geo_latitude"), event_b.get("geo_longitude")
    conf_a = event_a.get("geo_confidence") or 0.0
    conf_b = event_b.get("geo_confidence") or 0.0

    # Missing coordinates -> neutral score
    if lat_a is None or lon_a is None or lat_b is None or lon_b is None:
        return 0.5

    # Low confidence -> neutral score (don't trust village centroids)
    min_confidence = min(conf_a, conf_b)
    if min_confidence < 0.85:
        return 0.5

    dist_km = _haversine_km(lat_a, lon_a, lat_b, lon_b)
    return max(0.0, 1.0 - dist_km / max_distance_km)

def _haversine_km(lat1: float, lon1: float, lat2: float, lon2: float) -> float:
    R = 6371.0
    lat1_r, lon1_r = math.radians(lat1), math.radians(lon1)
    lat2_r, lon2_r = math.radians(lat2), math.radians(lon2)
    dlat = lat2_r - lat1_r
    dlon = lon2_r - lon1_r
    a = math.sin(dlat / 2) ** 2 + math.cos(lat1_r) * math.cos(lat2_r) * math.sin(dlon / 2) ** 2
    return R * 2 * math.asin(math.sqrt(a))
```

**Performance:** Math-based haversine benchmarked at 2.6M pairs/sec on this machine. Even comparing all 765 events pairwise (292,530 pairs) would take ~0.1 seconds.

**Confidence:** HIGH -- haversine formula is mathematically exact for great-circle distance, accuracy verified against known Breisgau city distances.

### 3. Title Scorer

**Goal:** Fuzzy title matching handling German compound words and prefix variations (MTCH-05).

**Key finding from empirical testing:** No single rapidfuzz function handles all German event title patterns optimally. The best approach is to combine `token_sort_ratio` and `token_set_ratio`, taking the maximum:

| Scenario | token_sort_ratio | token_set_ratio | max() |
|----------|-----------------|-----------------|-------|
| Primel-Aktion vs Valentinstags-Primeln (semantic overlap) | 60.8 | 65.8 | **65.8** |
| Kinderball Waldkirch vs Kinderball Krakeelia Waldkirch (subset match) | 80.0 | **100.0** | **100.0** -- DANGEROUS |
| Fasnetumzug Nordweil vs Nordwiler Narrenfahrplan Fasnetumzug (reorder+extra) | 67.9 | 71.0 | **71.0** |
| Preismaskenball Herrenberghalle vs Preismaskenball (short vs long) | 54.5 | **100.0** | **100.0** -- DANGEROUS |

**CRITICAL INSIGHT:** `token_set_ratio` returns 100.0 whenever all tokens of the shorter string appear in the longer string. This is dangerous for "same venue, different event" cases (row 2) and "terminliste vs artikel" comparisons (row 4). It should NOT be used as the primary scorer.

**Recommended approach:** Use `token_sort_ratio` as the primary scorer and `token_set_ratio` as a secondary signal only when `token_sort_ratio` is in the ambiguous range (40-80).

**Implementation:**
```python
from rapidfuzz.fuzz import token_sort_ratio, token_set_ratio

def title_score(event_a: dict, event_b: dict) -> float:
    title_a = event_a.get("title_normalized") or ""
    title_b = event_b.get("title_normalized") or ""

    if not title_a or not title_b:
        return 0.0

    # Primary: token_sort_ratio handles word reordering
    tsr = token_sort_ratio(title_a, title_b) / 100.0

    # Secondary: token_set_ratio for subset detection (boosted carefully)
    # Only use as a boost when primary is in the ambiguous range
    if 0.40 <= tsr <= 0.80:
        tset = token_set_ratio(title_a, title_b) / 100.0
        # Blend: weight token_sort more heavily to avoid false positives
        return tsr * 0.7 + tset * 0.3

    return tsr
```

**Why not WRatio:** WRatio internally uses `partial_ratio` with a length-dependent weight. For very short terminliste titles matched against long artikel titles, WRatio gives 85-90 (too high). It is designed for English "did you mean?" scenarios, not entity resolution. The empirical tests show:
- "Fasnetumzug Nordweil" vs "Nordwiler Narrenfahrplan Fasnetumzug": WRatio=85.5 vs token_sort=67.9
- The 85.5 would auto-match, but these are different events (Fasnetumzug is one of several events in the Narrenfahrplan)

**Confidence:** HIGH -- empirically tested with real German event title patterns from this dataset.

### 4. Description Scorer

**Goal:** Score description similarity as a supporting signal.

**Algorithm:** Use `token_sort_ratio` on normalized short descriptions. Many events lack descriptions (terminliste sources), so missing data should return 0.5 (neutral) not 0.0 (penalty).

```python
from rapidfuzz.fuzz import token_sort_ratio

def description_score(event_a: dict, event_b: dict) -> float:
    desc_a = event_a.get("short_description_normalized") or ""
    desc_b = event_b.get("short_description_normalized") or ""

    # Both missing -> neutral (don't penalize missing data)
    if not desc_a and not desc_b:
        return 0.5

    # One missing -> slightly below neutral
    if not desc_a or not desc_b:
        return 0.4

    return token_sort_ratio(desc_a, desc_b) / 100.0
```

**Confidence:** HIGH -- simple application of proven rapidfuzz scorer.

## Matching Configuration

### YAML Structure

```yaml
# config/matching.yaml
# Event deduplication matching configuration
# All thresholds and weights can be tuned without code changes

scoring:
  weights:
    date: 0.30
    geo: 0.25
    title: 0.30
    description: 0.15

thresholds:
  high: 0.75       # Auto-match above this
  low: 0.35        # Auto-reject below this
  # Between low and high = "ambiguous" (Phase 5 AI or manual review)

geo:
  max_distance_km: 10.0
  min_confidence: 0.85
  neutral_score: 0.5    # Score when geo data missing or low confidence

date:
  time_tolerance_minutes: 30
  time_close_minutes: 90
  close_factor: 0.7     # Score multiplier for 30-90 min difference
  far_factor: 0.3       # Score multiplier for >90 min difference

title:
  primary_weight: 0.7   # Weight for token_sort_ratio in blend
  secondary_weight: 0.3  # Weight for token_set_ratio in blend
  blend_lower: 0.40     # Below this, use primary only
  blend_upper: 0.80     # Above this, use primary only

cluster:
  max_cluster_size: 15           # Flag clusters larger than this
  min_internal_similarity: 0.40  # Minimum avg pairwise similarity within cluster

canonical:
  field_strategies:
    title: longest_non_generic
    short_description: longest
    description: longest
    highlights: union
    location_name: most_complete
    location_city: most_frequent
    location_street: most_complete
    geo: highest_confidence
    categories: union
    is_family_event: any_true
    is_child_focused: any_true
    admission_free: any_true
```

### Pydantic Config Model

```python
from pathlib import Path
from pydantic import BaseModel
import yaml

class ScoringWeights(BaseModel):
    date: float = 0.30
    geo: float = 0.25
    title: float = 0.30
    description: float = 0.15

class ThresholdConfig(BaseModel):
    high: float = 0.75
    low: float = 0.35

class GeoConfig(BaseModel):
    max_distance_km: float = 10.0
    min_confidence: float = 0.85
    neutral_score: float = 0.5

class DateConfig(BaseModel):
    time_tolerance_minutes: int = 30
    time_close_minutes: int = 90
    close_factor: float = 0.7
    far_factor: float = 0.3

class TitleConfig(BaseModel):
    primary_weight: float = 0.7
    secondary_weight: float = 0.3
    blend_lower: float = 0.40
    blend_upper: float = 0.80

class ClusterConfig(BaseModel):
    max_cluster_size: int = 15
    min_internal_similarity: float = 0.40

class FieldStrategies(BaseModel):
    title: str = "longest_non_generic"
    short_description: str = "longest"
    description: str = "longest"
    highlights: str = "union"
    location_name: str = "most_complete"
    location_city: str = "most_frequent"
    location_street: str = "most_complete"
    geo: str = "highest_confidence"
    categories: str = "union"
    is_family_event: str = "any_true"
    is_child_focused: str = "any_true"
    admission_free: str = "any_true"

class CanonicalConfig(BaseModel):
    field_strategies: FieldStrategies = FieldStrategies()

class MatchingConfig(BaseModel):
    scoring: ScoringWeights = ScoringWeights()
    thresholds: ThresholdConfig = ThresholdConfig()
    geo: GeoConfig = GeoConfig()
    date: DateConfig = DateConfig()
    title: TitleConfig = TitleConfig()
    cluster: ClusterConfig = ClusterConfig()
    canonical: CanonicalConfig = CanonicalConfig()

def load_matching_config(path: Path) -> MatchingConfig:
    if path.exists():
        with open(path) as f:
            data = yaml.safe_load(f) or {}
        return MatchingConfig(**data)
    return MatchingConfig()  # All defaults
```

**Confidence:** HIGH -- follows existing project patterns (Settings, city_aliases.yaml).

## Graph Clustering

### networkx Connected Components

**API:** `nx.connected_components(G)` returns a generator of sets of nodes.
**Complexity:** O(n + m) using BFS traversal, where n=nodes, m=edges.
**For 765 events:** Even if every event connects to every other (worst case), this is trivially fast.

**Implementation:**
```python
import networkx as nx
from dataclasses import dataclass

@dataclass
class ClusterResult:
    clusters: list[set[str]]         # Sets of event IDs
    flagged_clusters: list[set[str]]  # Over-large or incoherent clusters

def cluster_matches(
    match_decisions: list[MatchDecision],
    config: ClusterConfig,
    events_by_id: dict[str, dict],
) -> ClusterResult:
    G = nx.Graph()

    for decision in match_decisions:
        if decision.decision == "match":
            G.add_edge(
                decision.event_id_a,
                decision.event_id_b,
                weight=decision.combined_score,
            )

    # Add singleton nodes (events with no matches stay as their own cluster)
    for event_id in events_by_id:
        if event_id not in G:
            G.add_node(event_id)

    clusters = list(nx.connected_components(G))

    result = ClusterResult(clusters=[], flagged_clusters=[])
    for cluster in clusters:
        if len(cluster) == 1:
            result.clusters.append(cluster)
        elif _is_cluster_coherent(cluster, G, config, events_by_id):
            result.clusters.append(cluster)
        else:
            result.flagged_clusters.append(cluster)

    return result
```

### Cluster Coherence Validation

**What to check:**
1. **Size limit:** Clusters >15 events are suspicious (a single real-world event rarely appears in more than 11 sources given the 11 sources in this dataset)
2. **Internal similarity:** Average pairwise edge weight should be above a minimum threshold
3. **Date spread:** All events in a cluster should share at least one overlapping date
4. **City consistency:** Events in a cluster should not span more than 2-3 distinct cities

```python
def _is_cluster_coherent(
    cluster: set[str],
    graph: nx.Graph,
    config: ClusterConfig,
    events_by_id: dict[str, dict],
) -> bool:
    if len(cluster) > config.max_cluster_size:
        return False

    # Check average internal similarity
    subgraph = graph.subgraph(cluster)
    edge_weights = [d["weight"] for _, _, d in subgraph.edges(data=True)]
    if edge_weights:
        avg_weight = sum(edge_weights) / len(edge_weights)
        if avg_weight < config.min_internal_similarity:
            return False

    # Check date consistency
    all_dates = set()
    for event_id in cluster:
        event = events_by_id.get(event_id, {})
        for d in event.get("dates", []):
            all_dates.add(d.get("date"))
    # If cluster members span more than 3 distinct dates, flag it
    if len(all_dates) > 3:
        return False

    return True
```

**Handling flagged clusters:** In Phase 2, flagged clusters are marked with `needs_review=True` on the canonical event. Phase 6 (Manual Review) will provide the UI to split/merge them.

**Confidence:** HIGH -- connected_components is a well-understood algorithm; coherence checks are domain-specific heuristics that can be tuned.

## Canonical Event Synthesis

### Database Models (New)

```python
# canonical_events table
class CanonicalEvent(Base):
    __tablename__ = "canonical_events"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)

    # Best-of fields (selected from sources)
    title: Mapped[str] = mapped_column(sa.String)
    short_description: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    description: Mapped[str | None] = mapped_column(sa.Text, nullable=True)
    highlights: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)
    location_name: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_city: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_district: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_street: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    location_zipcode: Mapped[str | None] = mapped_column(sa.String, nullable=True)
    geo_latitude: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    geo_longitude: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    geo_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)

    # Unified dates (JSON: list of {date, start_time, end_time, end_date})
    dates: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)

    categories: Mapped[list | None] = mapped_column(sa.JSON, nullable=True)
    is_family_event: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    is_child_focused: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)
    admission_free: Mapped[bool | None] = mapped_column(sa.Boolean, nullable=True)

    # Provenance: maps field_name -> source_event_id
    field_provenance: Mapped[dict | None] = mapped_column(sa.JSON, nullable=True)

    # Metadata
    source_count: Mapped[int] = mapped_column(sa.Integer, default=1)
    match_confidence: Mapped[float | None] = mapped_column(sa.Float, nullable=True)
    needs_review: Mapped[bool] = mapped_column(sa.Boolean, default=False)
    version: Mapped[int] = mapped_column(sa.Integer, default=1)
    created_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))
    updated_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))

# canonical_event_sources linking table
class CanonicalEventSource(Base):
    __tablename__ = "canonical_event_sources"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    canonical_event_id: Mapped[int] = mapped_column(sa.ForeignKey("canonical_events.id"))
    source_event_id: Mapped[str] = mapped_column(sa.ForeignKey("source_events.id"))
    added_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))

# match_decisions audit table
class MatchDecision(Base):
    __tablename__ = "match_decisions"

    id: Mapped[int] = mapped_column(sa.Integer, primary_key=True, autoincrement=True)
    source_event_id_a: Mapped[str] = mapped_column(sa.ForeignKey("source_events.id"))
    source_event_id_b: Mapped[str] = mapped_column(sa.ForeignKey("source_events.id"))
    combined_score: Mapped[float] = mapped_column(sa.Float)
    date_score: Mapped[float] = mapped_column(sa.Float)
    geo_score: Mapped[float] = mapped_column(sa.Float)
    title_score: Mapped[float] = mapped_column(sa.Float)
    description_score: Mapped[float] = mapped_column(sa.Float)
    decision: Mapped[str] = mapped_column(sa.String)  # match/no_match/ambiguous
    tier: Mapped[str] = mapped_column(sa.String, default="deterministic")
    decided_at: Mapped[datetime] = mapped_column(sa.DateTime, server_default=sa.text("CURRENT_TIMESTAMP"))
```

### Field Selection Strategies

```python
def synthesize_canonical(
    source_events: list[dict],
    config: CanonicalConfig,
) -> dict:
    """Select best field from each source event based on strategy."""
    strategies = config.field_strategies

    result = {}
    provenance = {}

    # Title: longest non-generic (not just "Fasnacht" when a specific title exists)
    result["title"], provenance["title"] = _select_longest_non_generic(
        source_events, "title", min_length=10
    )

    # Descriptions: longest
    result["short_description"], provenance["short_description"] = _select_longest(
        source_events, "short_description"
    )
    result["description"], provenance["description"] = _select_longest(
        source_events, "description"
    )

    # Highlights: union of all
    result["highlights"], provenance["highlights"] = _select_union_lists(
        source_events, "highlights"
    )

    # Location: most complete (most non-null location fields)
    result.update(_select_most_complete_location(source_events, provenance))

    # Geo: highest confidence
    result.update(_select_best_geo(source_events, provenance))

    # Dates: union of all unique dates
    result["dates"] = _union_dates(source_events)
    provenance["dates"] = "union_all_sources"

    # Categories: union
    result["categories"], provenance["categories"] = _select_union_lists(
        source_events, "categories"
    )

    # Booleans: any_true
    for field in ["is_family_event", "is_child_focused", "admission_free"]:
        result[field] = any(e.get(field) for e in source_events)
        provenance[field] = next(
            (e["id"] for e in source_events if e.get(field)), source_events[0]["id"]
        )

    result["field_provenance"] = provenance
    return result

def _select_longest(events: list[dict], field: str) -> tuple[str | None, str]:
    best_val = None
    best_source = events[0]["id"]
    best_len = 0
    for e in events:
        val = e.get(field)
        if val and len(val) > best_len:
            best_val = val
            best_source = e["id"]
            best_len = len(val)
    return best_val, best_source

def _select_longest_non_generic(
    events: list[dict], field: str, min_length: int = 10
) -> tuple[str, str]:
    """Select longest title, preferring titles above min_length."""
    long_titles = [(e, e.get(field, "")) for e in events if len(e.get(field, "")) >= min_length]
    if long_titles:
        best = max(long_titles, key=lambda x: len(x[1]))
        return best[1], best[0]["id"]
    # Fallback: longest regardless
    best = max(events, key=lambda e: len(e.get(field, "")))
    return best.get(field, ""), best["id"]
```

### Enrichment (CANL-03)

When new source events match an existing canonical:

```python
def enrich_canonical(
    existing_canonical: dict,
    new_source: dict,
    all_sources: list[dict],  # Including the new source
    config: CanonicalConfig,
) -> dict:
    """Re-synthesize canonical event with the new source included.

    Never downgrades existing good data -- only upgrades or adds.
    """
    # Re-run full synthesis with all sources (including new)
    new_canonical = synthesize_canonical(all_sources, config)

    # Check for downgrades and prevent them
    for field in ["title", "short_description", "description"]:
        old_val = existing_canonical.get(field) or ""
        new_val = new_canonical.get(field) or ""
        # Keep existing if it was longer (prevent downgrade)
        if len(old_val) > len(new_val):
            new_canonical[field] = old_val
            new_canonical["field_provenance"][field] = existing_canonical["field_provenance"][field]

    new_canonical["version"] = existing_canonical.get("version", 1) + 1
    new_canonical["source_count"] = len(all_sources)
    return new_canonical
```

**Confidence:** HIGH -- straightforward field selection logic with clear rules.

## Common Pitfalls

### Pitfall 1: token_set_ratio False Positives

**What goes wrong:** Using `token_set_ratio` as the primary scorer returns 100.0 for "Kinderball Waldkirch" vs "Kinderball Krakeelia Waldkirch" because the shorter string's tokens are a subset of the longer one. This merges distinct events at the same venue.
**Why it happens:** `token_set_ratio` is designed for "is A a subset of B?" not "are A and B the same thing?"
**How to avoid:** Use `token_sort_ratio` as primary. Only blend in `token_set_ratio` when the primary score is in the ambiguous range (40-80), and with reduced weight (0.3 max).
**Warning signs:** Carnival events at the same venue all merge into one giant cluster.

### Pitfall 2: Neutral Score for Missing Data

**What goes wrong:** Returning 0.0 when geo coordinates or descriptions are missing penalizes events from sparse sources (terminliste). These events then never match anything because 25-30% of their score is zeroed out.
**Why it happens:** Intuitive to return 0.0 for "no match data available."
**How to avoid:** Return 0.5 (neutral) for missing data. This means "we have no evidence for or against" rather than "evidence against."
**Warning signs:** terminliste events consistently fail to match even when title and date are perfect matches.

### Pitfall 3: Time-of-Day as False Separator

**What goes wrong:** Two sources report the same event with start times of 19:11 (OCR artifact) and 19:30 (rounded). A strict time comparison marks them as different events.
**Why it happens:** Carnival events in this region traditionally start at odd times (19:11, 19:33 -- "Schnapszahlen"). OCR may garble exact minutes.
**How to avoid:** 30-minute tolerance window. Within 30 min = full credit. 30-90 min = partial. Only >90 min is a meaningful time difference.

### Pitfall 4: Over-Merging via Transitive Closure

**What goes wrong:** Event A matches B (score 0.76), B matches C (score 0.76), but A and C are actually different events (score 0.35). Connected components groups them all together.
**Why it happens:** Transitivity through a "bridge" event that shares partial features with both.
**How to avoid:** Cluster coherence validation. After clustering, check that the average internal pairwise similarity is above a threshold (0.40). Flag incoherent clusters for review.
**Warning signs:** Clusters with 8+ events from diverse sources, especially for generic event names.

### Pitfall 5: Canonical Field Inconsistency

**What goes wrong:** Title comes from source A (artikel format), description from source B (terminliste), and the description references details not in the canonical title.
**Why it happens:** Selecting "best per field" without considering cross-field consistency.
**How to avoid:** When possible, prefer a single source for related fields (title + short_description from same source). For independent fields (geo, categories, booleans), mixing is fine.

### Pitfall 6: Blocking Recall Check

**What goes wrong:** Blocking keys miss valid matches because events have different city names in different sources (one says "Nordweil", the other says "Kenzingen" before city alias resolution).
**Why it happens:** City aliases might not cover all variations; events might lack city data entirely.
**How to avoid:** Phase 1 already generates both dc| (date+city) and dg| (date+geo_grid) blocking keys. Verify blocking recall against ground truth: what percentage of true "same" pairs share at least one blocking key? Target >98%.

## Code Examples

### Full Matching Pipeline Flow

```python
async def run_matching_pipeline(
    session: AsyncSession,
    config: MatchingConfig,
) -> MatchingResult:
    """End-to-end matching pipeline."""

    # 1. Load all source events with dates
    events = await load_all_events(session)
    events_by_id = {e["id"]: e for e in events}

    # 2. Generate candidate pairs using blocking keys
    candidate_pairs = generate_candidate_pairs(events)

    # 3. Score each candidate pair
    match_decisions = []
    for id_a, id_b in candidate_pairs:
        evt_a = events_by_id[id_a]
        evt_b = events_by_id[id_b]

        signals = SignalScores(
            date=date_score(evt_a, evt_b),
            geo=geo_score(evt_a, evt_b, config.geo.max_distance_km),
            title=title_score(evt_a, evt_b),
            description=description_score(evt_a, evt_b),
        )

        score = combined_score(signals, config.scoring)
        decision = decide(score, config.thresholds)

        match_decisions.append(MatchDecision(
            event_id_a=id_a,
            event_id_b=id_b,
            combined_score=score,
            signals=signals,
            decision=decision,
        ))

    # 4. Cluster matches
    cluster_result = cluster_matches(match_decisions, config.cluster, events_by_id)

    # 5. Synthesize canonical events
    canonical_events = []
    for cluster in cluster_result.clusters:
        sources = [events_by_id[eid] for eid in cluster]
        canonical = synthesize_canonical(sources, config.canonical)
        canonical["needs_review"] = cluster in cluster_result.flagged_clusters
        canonical_events.append(canonical)

    # 6. Persist to database
    await persist_results(session, canonical_events, match_decisions)

    return MatchingResult(
        canonical_count=len(canonical_events),
        match_count=sum(1 for d in match_decisions if d.decision == "match"),
        ambiguous_count=sum(1 for d in match_decisions if d.decision == "ambiguous"),
        flagged_count=len(cluster_result.flagged_clusters),
    )
```

### Integration with Evaluation Harness

The existing evaluation harness (`harness.py`) uses `generate_predictions_from_events()` with single-signal title matching. Phase 2 must update this to use the multi-signal pipeline:

```python
def generate_predictions_from_events_v2(
    events: list[dict],
    config: MatchingConfig,
) -> set[tuple[str, str]]:
    """Phase 2 prediction generator using multi-signal scoring."""
    events_by_id = {e["id"]: e for e in events}
    candidate_pairs = generate_candidate_pairs(events)

    predicted_same = set()
    for id_a, id_b in candidate_pairs:
        evt_a = events_by_id[id_a]
        evt_b = events_by_id[id_b]

        signals = SignalScores(
            date=date_score(evt_a, evt_b),
            geo=geo_score(evt_a, evt_b),
            title=title_score(evt_a, evt_b),
            description=description_score(evt_a, evt_b),
        )

        score = combined_score(signals, config.scoring)
        if score >= config.thresholds.high:
            predicted_same.add((min(id_a, id_b), max(id_a, id_b)))

    return predicted_same
```

## State of the Art

| Old Approach | Current Approach | Impact |
|--------------|------------------|--------|
| `thefuzz` / `fuzzywuzzy` | `rapidfuzz` 3.14.3 | 10-100x faster, MIT license, better Unicode |
| `geopy.distance.geodesic` | Math-based haversine | No dependency, 2.6M/sec, <1% error at <100km |
| Pairwise match decisions | Graph connected components | Catches transitive duplicates, prevents split clusters |
| Single threshold | Three-tier (match/ambiguous/reject) | Prepares for Phase 5 AI on ambiguous cases |
| Hardcoded weights | YAML configuration | Tunable without code changes, threshold sweep support |

## Open Questions

1. **Threshold starting points:**
   - What we know: Combined score 0.75 for high, 0.35 for low are educated starting points based on similar entity resolution systems.
   - What is unclear: Optimal thresholds depend on the actual score distribution from the 765-event dataset.
   - Recommendation: Run the full pipeline once, analyze the score histogram, and adjust thresholds to maximize F1 against ground truth. The threshold sweep mechanism from Phase 1 should be extended for multi-signal scores.

2. **Description weight when mostly missing:**
   - What we know: terminliste events often lack descriptions entirely.
   - What is unclear: Whether 0.15 weight for description unfairly penalizes or benefits sparse-description events.
   - Recommendation: Start at 0.15, but if evaluation shows description weight hurts F1 more than helps, reduce to 0.10 or 0.05.

3. **Enrichment trigger:**
   - What we know: New source events should enrich existing canonicals.
   - What is unclear: Whether enrichment should run inline during the matching pipeline or as a separate post-processing step.
   - Recommendation: Inline during pipeline. When a new source matches an existing canonical cluster, re-synthesize immediately.

## Sources

### Primary (HIGH confidence)
- [rapidfuzz official docs](https://rapidfuzz.github.io/RapidFuzz/Usage/fuzz.html) -- fuzz.token_sort_ratio, token_set_ratio, WRatio API
- [rapidfuzz process docs](https://rapidfuzz.github.io/RapidFuzz/Usage/process.html) -- cdist batch processing API
- [networkx 3.6.1 docs](https://networkx.org/documentation/stable/reference/algorithms/generated/networkx.algorithms.components.connected_components.html) -- connected_components API
- [sklearn haversine_distances](https://scikit-learn.org/stable/modules/generated/sklearn.metrics.pairwise.haversine_distances.html) -- haversine formula reference
- Empirical testing with real event data from this project's eventdata/ directory

### Secondary (MEDIUM confidence)
- [Pydantic YAML configuration pattern](https://medium.com/@jonathan_b/a-simple-guide-to-configure-your-python-project-with-pydantic-and-a-yaml-file-bef76888f366)
- [networkx PyPI](https://pypi.org/project/networkx/) -- version 3.6.1 current
- Entity resolution literature (Fellegi-Sunter model, blocking strategies)

### Tertiary (LOW confidence)
- Weight starting points (date=0.30, geo=0.25, title=0.30, desc=0.15) are educated guesses; must be validated against ground truth

## Metadata

**Confidence breakdown:**
- Signal scorers: HIGH -- empirically tested with real German event titles, verified API docs
- Geo scoring: HIGH -- math formula verified, distances checked against known Breisgau geography
- Graph clustering: HIGH -- well-documented standard algorithm, trivial at this scale
- Configuration pattern: HIGH -- follows existing project patterns
- Canonical synthesis: MEDIUM -- field selection logic is straightforward but cross-field consistency needs validation during implementation
- Threshold values: LOW -- starting points only, require empirical validation against ground truth

**Research date:** 2026-02-27
**Valid until:** 2026-04-27 (libraries are stable; thresholds are data-dependent and may need tuning sooner)
