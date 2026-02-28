# Phase 7: Accuracy Refinement - Research

**Researched:** 2026-02-28
**Domain:** German NLP, text matching, event deduplication accuracy
**Confidence:** HIGH

## Summary

Phase 7 improves matching accuracy for three specific edge-case categories: German dialect synonyms (MTCH-07), category-aware weight adjustment (MTCH-08), and source-type-aware title comparison (MTCH-09). The existing codebase is well-structured for these additions. The matching pipeline (`src/event_dedup/matching/`) uses a pure-function architecture where event dicts flow through signal scorers, a weighted combiner, and threshold-based decisions. All three requirements can be implemented by extending existing components without major refactoring.

Data analysis of the 765-event sample reveals 132 events containing "fasnet" variants, 23 with "fasnacht", 7 with "fastnacht", 2 with "fasching", and 2 with "karneval". The current fuzzy matching (RapidFuzz token_sort_ratio) handles some dialect variation well (0.94 for Hemdglunkerumzug vs Hemdklunkerumzug) but struggles with others (0.75 for Hemdglunki-Umzug vs Hemdklunkerumzug, 0.87 for Fasnet-Eröffnung vs Fasnachteröffnung). Synonym normalization before matching improves these scores by +0.04 to +0.22 points, which can push borderline pairs from "ambiguous" into "match" territory.

**Primary recommendation:** Implement synonym replacement as a preprocessing step applied to normalized titles before scoring, category-aware weight overrides as a config-driven lookup in the combiner, and source-type-aware comparison as an adjustment factor in the title scorer.

<phase_requirements>
## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| MTCH-07 | German dialect synonym dictionary maps equivalent terms | Synonym groups identified from 765-event sample data; architecture for synonym replacement in normalizer verified; measured +0.04 to +0.22 score improvement |
| MTCH-08 | Category-aware matching weights adjust calibration per event type | Category distribution analyzed (16 categories, "fasnacht" dominant); ScoringWeights Pydantic model and combiner support per-category overrides via config |
| MTCH-09 | Source-type-aware comparison adjusts for artikel vs terminliste formats | Source type distribution analyzed (475 artikel, 262 terminliste, 28 anzeige); title format differences documented; token_set_ratio already handles subset matching (0.48 sort vs 1.00 set for short vs long titles) |
</phase_requirements>

## Standard Stack

### Core (already installed)
| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| rapidfuzz | >=3.10 | Fuzzy string matching (token_sort_ratio, token_set_ratio) | Already in use; handles all fuzzy title matching |
| pydantic | >=2.9 | Config models for matching parameters | Already used for MatchingConfig hierarchy |
| pyyaml | >=6.0 | Config file loading | Already used for matching.yaml, prefixes.yaml |

### No New Dependencies Required
All three requirements can be implemented with existing libraries. Synonym dictionaries are small enough for in-memory dict lookups. Category-aware weights extend the existing Pydantic config. Source-type comparison uses existing RapidFuzz functions.

## Architecture Patterns

### Current Architecture (key integration points)

```
src/event_dedup/
├── preprocessing/
│   ├── normalizer.py         # normalize_text() - umlaut expansion, lowercasing
│   ├── prefix_stripper.py    # strip_prefixes() + normalize_title()
│   └── blocking.py           # generate_blocking_keys()
├── matching/
│   ├── config.py             # MatchingConfig (ScoringWeights, TitleConfig, etc.)
│   ├── scorers/
│   │   ├── title_scorer.py   # title_score() - RapidFuzz token_sort/set_ratio
│   │   ├── desc_scorer.py    # description_score()
│   │   ├── date_scorer.py    # date_score()
│   │   └── geo_scorer.py     # geo_score()
│   ├── combiner.py           # combined_score() + decide()
│   ├── candidate_pairs.py    # generate_candidate_pairs()
│   └── pipeline.py           # score_candidate_pairs() + run_full_pipeline()
├── config/
│   ├── city_aliases.yaml     # District -> municipality mapping
│   └── prefixes.yaml         # Source-specific title prefix patterns
├── evaluation/
│   ├── harness.py            # run_multisignal_evaluation(), run_ai_comparison_evaluation()
│   └── metrics.py            # compute_metrics() - precision/recall/F1
└── worker/
    ├── orchestrator.py       # process_new_file() - full pipeline
    └── persistence.py        # load_all_events_as_dicts() - event dict schema
```

### Data Flow (where changes integrate)

```
JSON file
  -> FileProcessor.process_file()
     -> strip_prefixes(title, prefix_config)
     -> normalize_text(stripped_title)          # <-- MTCH-07: add synonym_replace() here
     -> stored as title_normalized in DB
  -> load_all_events_as_dicts()
     -> dict includes: title, title_normalized, source_type, categories
  -> score_candidate_pairs(events, config)
     -> for each pair:
        -> title_score(evt_a, evt_b, config.title)   # <-- MTCH-07: use title_normalized (now with synonyms)
                                                       # <-- MTCH-09: adjust for source_type pair
        -> date_score(evt_a, evt_b)
        -> geo_score(evt_a, evt_b)
        -> description_score(evt_a, evt_b)
        -> combined_score(signals, config.scoring)    # <-- MTCH-08: use category-aware weights
        -> decide(score, config.thresholds)
```

### Pattern 1: Synonym Replacement (MTCH-07)

**What:** Replace dialect terms with canonical forms before fuzzy matching.
**When to use:** During text normalization, after prefix stripping and before storing `title_normalized`.
**Architecture decision:** Apply at normalization time (in `normalize_text` or a new `apply_synonyms` step) so that:
1. Synonyms are resolved once at ingestion time, not per-comparison
2. The normalized title stored in DB already has canonical forms
3. RapidFuzz operates on synonym-resolved text

**Integration point:** `src/event_dedup/preprocessing/normalizer.py` or a new `synonyms.py` module.

**Example:**
```python
# src/event_dedup/config/synonyms.yaml
synonym_groups:
  fastnacht:
    - fasnet
    - fasnacht
    - fasching
    - karneval
    - fasent
    - fasend
    - fasnets   # as in "Fasnetsumzug"
  hemdglunker:
    - hemdklunker
    - hemdglunki
    - hendglunki  # typo variant found in data: "Hendglunki-Umzug Tunsel"

# src/event_dedup/preprocessing/synonyms.py
def apply_synonyms(text: str, synonym_map: dict[str, str]) -> str:
    """Replace dialect variants with canonical forms.

    synonym_map is a flat dict: variant -> canonical
    e.g. {"fasnet": "fastnacht", "fasching": "fastnacht", ...}
    """
    for variant, canonical in sorted(synonym_map.items(), key=lambda x: -len(x[0])):
        text = text.replace(variant, canonical)
    return text
```

**Critical detail:** Sort replacements by length (longest first) to avoid partial matches. "fasnets" must match before "fasnet" to handle compound words like "Fasnetsumzug" correctly.

### Pattern 2: Category-Aware Weights (MTCH-08)

**What:** Override default scoring weights based on event categories.
**When to use:** In the combiner, when computing `combined_score` for a pair.
**Architecture decision:** Add a `category_weights` dict to `MatchingConfig` that maps category names to `ScoringWeights` overrides. The combiner checks if both events share a category and uses the override if present.

**Integration point:** `src/event_dedup/matching/config.py` and `src/event_dedup/matching/combiner.py` or `pipeline.py`.

**Example:**
```yaml
# config/matching.yaml (additions)
category_weights:
  fasnacht:
    date: 0.35
    geo: 0.30
    title: 0.20    # Lower: carnival titles vary wildly
    description: 0.15
  versammlung:
    date: 0.25
    geo: 0.20
    title: 0.40    # Higher: political events have consistent titles
    description: 0.15
```

```python
# In pipeline.py or a new resolver:
def resolve_weights(evt_a: dict, evt_b: dict, config: MatchingConfig) -> ScoringWeights:
    """Select scoring weights based on shared event categories."""
    cats_a = set(evt_a.get("categories") or [])
    cats_b = set(evt_b.get("categories") or [])
    shared = cats_a & cats_b

    for cat in config.category_weights_priority:
        if cat in shared:
            return config.category_weights[cat]

    return config.scoring  # default
```

### Pattern 3: Source-Type-Aware Comparison (MTCH-09)

**What:** Adjust title scoring when comparing events from different source types.
**When to use:** In `title_score()` when one event is `artikel` and the other is `terminliste`.
**Architecture decision:** When source types differ, blend in `token_set_ratio` more heavily because terminliste titles tend to be short subsets of longer artikel titles.

**Integration point:** `src/event_dedup/matching/scorers/title_scorer.py`

**Key finding from data analysis:**

| Pattern | token_sort_ratio | token_set_ratio | Explanation |
|---------|-----------------|-----------------|-------------|
| "Preismaskenball" vs "Preismaskenball mit Hemdglunker und Musikverein" | 0.48 | 1.00 | Terminliste title is subset of artikel |
| "Schiebeschlage" vs "Traditionelles Schiebeschlage mit glühenden Holzscheiben" | 0.40 | 1.00 | Same pattern |
| "Landschaftspflegetag" vs "Landschaftspflegetag Sexau" | 0.87 | 1.00 | Short city suffix |

The current scorer only blends in `token_set_ratio` when the primary (sort) score is in [0.40, 0.80]. For cross-source-type pairs, we should increase `secondary_weight` (set_ratio) or lower the blend range to catch more of these asymmetric title matches.

**Example:**
```python
def title_score(
    event_a: dict, event_b: dict, config: TitleConfig | None = None
) -> float:
    # ... existing logic ...

    # Source-type-aware adjustment
    st_a = event_a.get("source_type", "")
    st_b = event_b.get("source_type", "")
    cross_source_type = st_a != st_b and st_a in ("artikel", "terminliste") and st_b in ("artikel", "terminliste")

    if cross_source_type:
        # Use different blend config for cross-type comparison
        effective_config = config.cross_source_type or TitleConfig(
            primary_weight=0.4,   # Less weight on sort (penalizes length diff)
            secondary_weight=0.6, # More weight on set (rewards token overlap)
            blend_lower=0.30,     # Wider blend range
            blend_upper=0.90,
        )
    else:
        effective_config = config
```

### Anti-Patterns to Avoid

- **Synonym replacement at scoring time:** Would run O(pairs * synonyms) replacements instead of O(events * synonyms) at ingestion. Always normalize at ingestion time.
- **Category-specific thresholds instead of weights:** Changing thresholds per category creates discontinuities; changing weights adjusts how signals combine, which is smoother.
- **Hardcoded synonym lists:** Use YAML config like existing city_aliases.yaml and prefixes.yaml patterns.
- **Applying synonyms to raw text before normalization:** Apply AFTER lowercasing and umlaut expansion to ensure consistent matching. The normalizer pipeline should be: lowercase -> umlaut expansion -> synonym replacement -> whitespace cleanup.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom edit distance | RapidFuzz (already installed) | Optimized C++ impl, handles token-based matching |
| Synonym matching | Regex-based NLP pipeline | Simple dict replacement on normalized text | Synonym groups are small (<20 groups), known in advance, and domain-specific |
| Category detection | ML classifier | Direct use of `categories` field from source JSON | Events already have extracted categories |
| Weight optimization | Grid search / ML tuning | Manual calibration against ground truth F1 | Only 16 categories, 3 source types -- too few dimensions for automated tuning |

**Key insight:** The synonym groups are small, well-defined, and domain-specific (Alemannic/Baden carnival terminology). A simple dict-based replacement is the right tool -- no NLP libraries needed.

## Common Pitfalls

### Pitfall 1: Partial Synonym Matches
**What goes wrong:** Replacing "fasnet" in "fasnetsumzug" incorrectly yields "fastnachtsumzug" instead of "fastnachtumzug" (or it works but creates inconsistency with "fastnachtsumzug" in other sources).
**Why it happens:** Substring replacement on compound words can create unexpected forms.
**How to avoid:** Accept minor variation (RapidFuzz handles "fastnachtumzug" vs "fastnachtsumzug" at 0.98 similarity). Sort replacements longest-first. Test with actual event titles from the sample data.
**Warning signs:** New false negatives appearing in ground truth evaluation after synonym deployment.

### Pitfall 2: Category-Aware Weights Creating New False Positives
**What goes wrong:** Lowering title weight for "fasnacht" events causes unrelated carnival events in the same city to match (e.g., "Kinderball" matches "Hexensabbat" because geo+date scores dominate).
**Why it happens:** Carnival season concentrates many events in the same city on the same dates.
**How to avoid:** Only lower title weight moderately (e.g., 0.20-0.25, not below 0.15). Validate against ground truth subsets. Monitor false positive rate per category.
**Warning signs:** F1 drops on fasnacht subset despite recall improving.

### Pitfall 3: Re-processing Existing Data After Normalization Change
**What goes wrong:** Synonym replacement changes `title_normalized` values, but existing DB records still have old normalized forms.
**Why it happens:** Normalization runs at ingestion time; already-ingested events are not re-normalized.
**How to avoid:** Provide a migration script or CLI command to re-normalize all existing source events. Or apply synonyms at scoring time as a fallback (slower but avoids migration).
**Warning signs:** Inconsistent matching results between old and new events.

### Pitfall 4: Circular Synonym Replacement
**What goes wrong:** If "fasnet" -> "fastnacht" and "fastnacht" -> something else, cascading replacements corrupt text.
**Why it happens:** Synonym groups where the canonical form contains a variant substring.
**How to avoid:** Canonical form should NOT be a variant of another group. Use atomic replacement: scan text for all variants, replace each with canonical in a single pass.
**Warning signs:** Normalized text that doesn't match any expected form.

### Pitfall 5: Source-Type-Aware Scoring Breaks Same-Type Matching
**What goes wrong:** Changing title_score signature to require source_type breaks existing callers or changes scoring for same-type pairs.
**Why it happens:** title_score is called from pipeline.py which passes event dicts. If source_type isn't in the dict, scoring fails.
**How to avoid:** Make source_type handling optional with graceful fallback. Event dicts from `load_all_events_as_dicts()` already include `source_type`. Only apply cross-type adjustment when both types are present AND different.
**Warning signs:** Test failures in existing title_score tests.

## Code Examples

### Event Dict Schema (from persistence.py)
```python
# Fields available on every event dict in the pipeline:
{
    "id": "pdf-9d58bea1-1-6",
    "title": "Nordwiler Narrenfahrplan - Kita-Gizig-Umzug",
    "title_normalized": "kita-gizig-umzug",  # After prefix stripping + normalization
    "source_type": "artikel",                 # "artikel", "terminliste", or "anzeige"
    "source_code": "bwb",                     # Source publication code
    "categories": ["fasnacht", "kinder"],     # List of category strings
    "blocking_keys": ["dc|2026-02-12|kenzingen", "dg|2026-02-12|48.15|7.80"],
    # ... plus geo, dates, description, location fields
}
```

### Current Title Scorer Integration Point
```python
# src/event_dedup/matching/scorers/title_scorer.py
# Current: uses event_a["title"] and event_b["title"] directly
# For MTCH-07: scorer can optionally use title_normalized (with synonyms applied)
# For MTCH-09: scorer can check source_type to adjust blend weights
```

### Current Combiner Integration Point
```python
# src/event_dedup/matching/combiner.py
# combined_score(signals, weights) is called from pipeline.py
# For MTCH-08: pipeline.py resolves category-aware weights before calling combined_score
# The combiner itself doesn't need to change -- weight resolution happens upstream
```

### Evaluation Harness Integration
```python
# src/event_dedup/evaluation/harness.py
# run_multisignal_evaluation() already:
# - Loads all source events with full fields (including source_type, categories)
# - Runs generate_predictions_multisignal() with MatchingConfig
# - Computes F1 against ground truth
#
# For category-specific F1: filter ground truth pairs by category before computing metrics
# Example:
def evaluate_category_subset(
    gt_same: set, gt_diff: set, predicted: set,
    events_by_id: dict, category: str,
) -> MetricsResult:
    """Compute metrics for a specific category subset."""
    def has_category(pair, cat):
        a, b = pair
        cats_a = set(events_by_id.get(a, {}).get("categories") or [])
        cats_b = set(events_by_id.get(b, {}).get("categories") or [])
        return cat in cats_a or cat in cats_b

    gt_same_cat = {p for p in gt_same if has_category(p, category)}
    gt_diff_cat = {p for p in gt_diff if has_category(p, category)}
    pred_cat = {p for p in predicted if has_category(p, category)}

    return compute_metrics(pred_cat, gt_same_cat, gt_diff_cat)
```

## Detailed Findings by Requirement

### MTCH-07: German Dialect Synonym Dictionary

**Data analysis results:**

| Term | Occurrences in 765-event dataset | Found in |
|------|----------------------------------|----------|
| fasnet | 132 | Titles, descriptions (dominant local term) |
| narren | 102 | Compound words: Narrenzunft, Narrenbaum, etc. |
| fasnacht | 23 | Used by some sources |
| hemdglunker | 25 | Waldkirch/Gutach area term |
| fastnacht | 7 | More formal/standard term |
| hemdglunki | 4 | Shortened variant |
| hemdklunker | 3 | Kenzingen area variant |
| fasching | 2 | Standard German (rare in this region) |
| karneval | 2 | Rhineland term (very rare here) |
| fasent | 12 | Ettenheim local dialect |
| buurefasnet | 1 | Rural/farmer carnival |

**Identified synonym groups:**

1. **Carnival general:** fasnet, fasnacht, fasching, fastnacht, karneval, fasent, fasend -> canonical: `fastnacht`
2. **Hemdglunker variants:** hemdglunker, hemdklunker, hemdglunki, hendglunki -> canonical: `hemdglunker`
3. **Compound forms to handle:** fasnets (as in Fasnetsumzug), fasnet- (hyphenated)

**Measured impact of synonym replacement:**

| Pair | Before | After | Delta |
|------|--------|-------|-------|
| Fasnet-Eröffnung / Fasnachteröffnung Waldkirch | 0.87 | 0.98 | +0.11 |
| Fasnetumzug / Fasnachtsumzug Denzlingen | 0.89 | 0.98 | +0.09 |
| Hemdglunkerumzug / Hemdklunkerumzug | 0.94 | 1.00 | +0.06 |
| Hemdglunki-Umzug / Hemdklunkerumzug | 0.75 | 0.97 | +0.22 |
| Fasent-Eröffnung / Fasnet-Eröffnung Ettenheim | 0.96 | 1.00 | +0.04 |

**Recommendation:** Implement as YAML-configured synonym groups loaded at init, applied during text normalization (after umlaut expansion, before final cleanup). Use longest-match-first replacement to handle compound words correctly.

### MTCH-08: Category-Aware Matching Weights

**Category distribution in 765-event dataset:**

| Category | Count | Notes |
|----------|-------|-------|
| fasnacht | ~200+ | Most common; events cluster by date+city |
| fest | ~150 | Generic "celebration" |
| kinder | ~50 | Children's events |
| versammlung | ~40 | Political meetings -- very consistent titles |
| musik | ~35 | Concerts |
| bildung | ~30 | Educational events |
| kreativ | ~25 | Creative workshops |
| natur | ~20 | Nature/hiking |
| sport | ~15 | Sports events |
| tanz | ~12 | Dance events |
| buehne | ~10 | Theater/stage |
| hock | ~10 | Social gatherings |
| kirche | ~8 | Church events |
| markt | ~5 | Markets |
| shopping | ~5 | Shopping events |
| weinfest | ~3 | Wine festivals |

**Why default weights don't work well for all categories:**

- **fasnacht events:** Title weight should be LOWER because:
  - Many carnival events in the same city on the same day (high geo+date overlap between DIFFERENT events)
  - Titles use dialect terms that reduce fuzzy match scores
  - But: descriptions are often similar too, so description weight doesn't help distinguish
  - Better: increase geo weight (different venue = different event) and keep date high

- **versammlung (political) events:** Title weight should be HIGHER because:
  - Titles are very consistent across sources ("Wahlkampfstand Bündnis 90/Die Grünen - Kenzingen")
  - Geo data may vary (event location vs city center)
  - Dates are reliable

**Ground truth source-type distribution:**

| Label | artikel-artikel | terminliste-artikel | terminliste-terminliste | with anzeige |
|-------|----------------|--------------------|-----------------------|--------------|
| same | 148 | 19 | 37 | 44 |
| different | 365 | 386 | 90 | 92 |

The 19 terminliste-artikel "same" pairs and 386 "different" pairs are the key target for MTCH-09 improvement.

**Recommendation:** Add `category_weights` section to matching.yaml with overrides for `fasnacht` and `versammlung` categories. Use a priority list to determine which category override applies when events share multiple categories. Start conservative (small weight adjustments) and validate against ground truth F1.

### MTCH-09: Source-Type-Aware Comparison

**Source type characteristics observed in data:**

| Source Type | Count | Title Pattern | Description Pattern |
|-------------|-------|---------------|---------------------|
| artikel | 475 (62%) | Descriptive, includes context: "Nordwiler Narrenfahrplan - Kita-Gizig-Umzug" | Full journalistic description |
| terminliste | 262 (34%) | Short, name-only: "Preismaskenball", "Schiebeschlage" | Brief, factual |
| anzeige | 28 (4%) | Promotional: "SC Freiburg vs. Borussia Mönchengladbach" | Marketing copy |

**Key mismatch patterns between terminliste and artikel:**

1. **Short vs long titles:** Terminliste "Preismaskenball" (1 word) vs Artikel "Preismaskenball mit Hemdglunker und Musikverein in der Herrenberghalle" (8 words). token_sort_ratio: 0.48, token_set_ratio: 1.00

2. **Different naming conventions:** Terminliste "Hemdglunki-Umzug" vs Artikel "Hemdglunker Umzug und Ball Bad Krozingen". token_sort_ratio: 0.52, token_set_ratio: 0.58

3. **City name inclusion:** Terminliste "Landschaftspflegetag" vs Artikel "Landschaftspflegetag Sexau". token_sort_ratio: 0.87, token_set_ratio: 1.00

**Current title_score behavior:**
- Uses `token_sort_ratio` as primary (weight 0.7)
- Blends `token_set_ratio` only when primary is in [0.40, 0.80]
- For terminliste "Preismaskenball" vs artikel with same word + more: primary=0.48 (in blend range), so secondary (1.00) is blended: 0.7*0.48 + 0.3*1.00 = 0.636
- This is decent but could be improved by increasing set_ratio weight for cross-type pairs

**Recommendation:** When `source_type` differs between events in a pair (specifically artikel vs terminliste), use a modified `TitleConfig` with:
- Higher `secondary_weight` (token_set_ratio): 0.5-0.6 (from 0.3)
- Wider blend range: [0.25, 0.95] (from [0.40, 0.80])
- This captures the "short title is subset of long title" pattern

Add `cross_source_type` config as a nested `TitleConfig` within the main `TitleConfig`.

## State of the Art

| Old Approach | Current Approach | When Changed | Impact |
|--------------|------------------|--------------|--------|
| No synonyms | Synonym replacement before matching | Phase 7 | +0.04 to +0.22 title score improvement |
| Fixed weights for all events | Category-aware weight selection | Phase 7 | Better F1 on category-specific subsets |
| Same title scoring for all source types | Source-type-aware blend adjustment | Phase 7 | Captures terminliste-artikel asymmetric title matches |

## Validation Architecture

### Test Framework
| Property | Value |
|----------|-------|
| Framework | pytest 8.3+ with pytest-asyncio |
| Config file | `pyproject.toml` [tool.pytest.ini_options] |
| Quick run command | `.venv/bin/python -m pytest tests/ -x --tb=short -q` |
| Full suite command | `.venv/bin/python -m pytest tests/ -v` |

### Phase Requirements -> Test Map
| Req ID | Behavior | Test Type | Automated Command | File Exists? |
|--------|----------|-----------|-------------------|-------------|
| MTCH-07 | Synonym groups loaded from YAML | unit | `.venv/bin/python -m pytest tests/test_synonyms.py -x` | No - Wave 0 |
| MTCH-07 | Synonym replacement applied during normalization | unit | `.venv/bin/python -m pytest tests/test_normalizer.py -x` | Yes (extend) |
| MTCH-07 | Title matching with synonyms improves scores | unit | `.venv/bin/python -m pytest tests/test_scorers.py -x` | Yes (extend) |
| MTCH-08 | Category-aware weights loaded from config | unit | `.venv/bin/python -m pytest tests/test_matching_config.py -x` | Yes (extend) |
| MTCH-08 | Category weight resolution for event pairs | unit | `.venv/bin/python -m pytest tests/test_combiner.py -x` | Yes (extend) |
| MTCH-08 | Pipeline uses resolved weights | integration | `.venv/bin/python -m pytest tests/test_pipeline.py -x` | Yes (extend) |
| MTCH-09 | Cross-source-type title scoring uses different config | unit | `.venv/bin/python -m pytest tests/test_scorers.py -x` | Yes (extend) |
| MTCH-09 | Source type passed through pipeline to scorer | integration | `.venv/bin/python -m pytest tests/test_pipeline.py -x` | Yes (extend) |
| ALL | F1 on ground truth does not regress | evaluation | `.venv/bin/python -m pytest tests/test_harness.py -x` | Yes (extend) |

### Sampling Rate
- **Per task commit:** `.venv/bin/python -m pytest tests/ -x --tb=short -q`
- **Per wave merge:** `.venv/bin/python -m pytest tests/ -v`
- **Phase gate:** Full suite green + F1 evaluation on ground truth

### Wave 0 Gaps
- [ ] `tests/test_synonyms.py` -- covers MTCH-07 synonym loading and application
- [ ] `src/event_dedup/config/synonyms.yaml` -- synonym group definitions
- [ ] Extension of `test_normalizer.py` with synonym-aware normalization tests
- [ ] Extension of `test_scorers.py` with source-type-aware and synonym-aware title scoring
- [ ] Extension of `test_matching_config.py` with category_weights config loading
- [ ] Extension of `test_combiner.py` with category-aware weight resolution
- [ ] Extension of `test_harness.py` with category-specific F1 evaluation

## Open Questions

1. **Synonym application: normalization time vs scoring time?**
   - What we know: Normalization time is O(events), scoring time is O(pairs). Normalization is cleaner.
   - What's unclear: Applying at normalization changes stored `title_normalized` values. Existing events in DB won't have synonyms applied unless re-processed.
   - Recommendation: Apply at normalization time (in `normalize_text` flow). Provide a one-time re-normalization script for existing data. This aligns with how prefix stripping already works.

2. **Category weight priority when events share multiple categories**
   - What we know: Events can have multiple categories (e.g., ["fasnacht", "kinder"]). Different categories may want different weight overrides.
   - What's unclear: Which override takes precedence?
   - Recommendation: Use a priority list in config (ordered). First matching shared category wins. E.g., `category_weights_priority: [fasnacht, versammlung]` means fasnacht overrides apply when both events have it, even if they also have other categories.

3. **How to validate that changes don't regress overall F1**
   - What we know: Ground truth has 248 same-pairs and 933 different-pairs. Evaluation harness exists.
   - What's unclear: What is the current F1 baseline to compare against?
   - Recommendation: Run the evaluation harness before AND after each change. Document baseline F1 and per-change deltas. Add category-specific F1 reporting to the harness.

4. **Anzeige source type handling**
   - What we know: 28 anzeige events exist. 44 ground truth pairs involve anzeige. Anzeige titles tend to be promotional.
   - What's unclear: Whether anzeige needs its own source-type adjustments or can be treated like artikel.
   - Recommendation: Start by treating anzeige like artikel (no special handling). Monitor anzeige-specific F1. Add anzeige-specific logic only if needed.

## Risks and Mitigations

| Risk | Impact | Mitigation |
|------|--------|------------|
| Synonym replacement creates false positives (unrelated events with same carnival term match) | Medium | Synonyms only affect substring replacement, not scoring weights. Combined score still requires geo+date agreement. |
| Category-aware weights decrease overall F1 while improving category-specific F1 | High | Validate on full ground truth, not just target category. Use conservative weight adjustments. |
| Re-normalization of existing data causes inconsistencies | Low | Provide migration script. Or: apply synonyms at both normalization and scoring time for belt-and-suspenders. |
| Title scorer changes break existing tests | Low | 329 tests currently pass. Run full suite after each change. |

## Sources

### Primary (HIGH confidence)
- Direct code analysis of `src/event_dedup/matching/` (all scorer, config, pipeline files)
- Direct code analysis of `src/event_dedup/preprocessing/` (normalizer, prefix_stripper, blocking)
- Direct data analysis of all 20 JSON files in `eventdata/` (765 events total)
- Ground truth database analysis (248 same pairs, 933 different pairs)
- RapidFuzz score measurements on actual event title pairs

### Secondary (MEDIUM confidence)
- Category frequency analysis (approximate counts from event data scan)
- Synonym group completeness (based on terms found in 765-event sample; more groups may emerge with larger datasets)

### Tertiary (LOW confidence)
- Optimal weight values for category-aware scoring (needs empirical validation against ground truth)
- Whether anzeige source type needs special treatment (small sample size: 28 events)

## Metadata

**Confidence breakdown:**
- Standard stack: HIGH - No new dependencies needed, all extensions to existing Pydantic config + pure functions
- Architecture: HIGH - Clear integration points identified through code analysis, follows established patterns
- Pitfalls: HIGH - Based on direct measurement of fuzzy matching scores on real data
- Synonym groups: MEDIUM - Based on 765-event sample; larger datasets may reveal more variants
- Weight values: LOW - Need empirical tuning against ground truth; starting values are educated guesses

**Research date:** 2026-02-28
**Valid until:** Stable domain -- valid until codebase architecture changes significantly
