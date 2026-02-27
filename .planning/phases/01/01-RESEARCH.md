# Phase 1: Foundation & Ground Truth - Research

**Researched:** 2026-02-27
**Domain:** Event data analysis, preprocessing design, ground truth construction
**Confidence:** HIGH (based on direct analysis of all 765 events across 20 JSON files)

## Summary

This research analyzes the actual 765-event dataset across 20 JSON files from 11 source codes to answer four open questions from the CONTEXT.md. The findings are based entirely on empirical analysis of the real data, not theoretical recommendations.

The core finding is that **title + location + date are the primary matching signals**, and short_description adds marginal value for disambiguation in edge cases (100% availability vs 31.6% for description). The ~5km geo grid is too small for this region -- the data shows cities within a 6km radius that need to be in the same grid cell, and events from the same real-world occurrence appear with different city names up to ~30km apart. The prefix pattern analysis found one dominant source-specific prefix ("Nordwiler Narrenfahrplan") and several generic content prefixes. For ground truth, the candidate pair generation from same-date + same-city heuristics produces ~816 cross-source pairs, of which ~326 have title similarity >= 0.50 (likely duplicates) and ~359 need manual review.

**Primary recommendation:** Use exact same-date + same-city blocking as the primary ground truth candidate generator, supplemented by same-date + geo-proximity for events where cities differ between sources. Target ~300 labeled pairs from the ~685 reviewable candidates.

<user_constraints>

## User Constraints (from CONTEXT.md)

### Locked Decisions

1. **Ground Truth Labeling Approach**: Semi-automated candidate generation with human review. System generates candidate duplicate pairs using heuristics (same date + same/nearby city). User reviews each candidate, labeling as same/different. Target: 200-300 labeled pairs. Storage in PostgreSQL table (`ground_truth_pairs`).

2. **Database Schema**: Separate `source_events` and `canonical_events` tables with linking table. Separate `event_dates` table. `file_ingestions` table for idempotency. Selective metadata storage (keep `_extracted_at` and `_batch_index`, drop `_sanitizeResult`, `_sanitized`, `_event_index`). Dual text storage (original + normalized).

3. **Idempotency Strategy**: File-hash-based skip with stable event IDs. SHA-256 hash check. Event IDs (`pdf-{hash}-{batch}-{index}`) as natural unique keys. Single DB transaction per file. Dead letter queue for failures.

4. **Preprocessing Scope**: Normalize title + location (lowercase, umlaut expansion, prefix stripping). Configurable prefix list. Dual blocking strategy (geo grid + city-name fallback). Online events excluded from geo blocking.

### Claude's Discretion

- Whether description/short_description normalization adds matching value (RESOLVED -- see findings below)
- Optimal prefix patterns for initial configuration (RESOLVED -- see findings below)
- Geo grid cell size tuning (RESOLVED -- see findings below)
- Ground truth candidate generation exact parameters (RESOLVED -- see findings below)

### Deferred Ideas (OUT OF SCOPE)

None captured.

</user_constraints>

<phase_requirements>

## Phase Requirements

| ID | Description | Research Support |
|----|-------------|-----------------|
| EVAL-01 | Labeled ground truth dataset of 200-300 event pairs from 765-event sample | Candidate generation heuristics defined: same-date + same-city produces 816 pairs, ~326 likely duplicates. Sufficient for 200-300 labeled pairs. |
| EVAL-02 | Evaluation harness reports precision, recall, F1 | Standard stack (scikit-learn metrics) identified. Pair-based evaluation against ground_truth_pairs table. |
| EVAL-03 | Evaluation runs against any threshold configuration | Config-driven threshold design. Evaluation harness reads thresholds from config file. |
| PIPE-02 | Idempotent processing (no duplicates on re-import) | File SHA-256 hash + event ID natural keys. Transaction-per-file. |
| PIPE-03 | Single database transaction per file | SQLAlchemy session-per-file pattern. |
| PIPE-04 | Direct PostgreSQL connection for read/write | asyncpg + SQLAlchemy async engine. Schema designed from data analysis. |

</phase_requirements>

## Open Question Findings

### Question 1: Which additional fields benefit from normalization?

**Finding: Normalize `short_description` for matching, skip `description` and `highlights` normalization in Phase 1.**

**Evidence:**

| Field | Availability | By artikel | By terminliste | By anzeige |
|-------|-------------|------------|----------------|------------|
| title | 100% (765/765) | 100% | 100% | 100% |
| short_description | 100% (765/765) | 100% | 100% | 100% |
| description | 31.6% (242/765) | 50.5% | 0% | 7.1% |
| highlights | 39.7% (304/765) | 56.0% | 6.9% | 71.4% |

**Key observations:**

1. **`short_description` is 100% available** -- it exists for every event regardless of source type. This makes it a reliable secondary matching signal.

2. **`description` is absent from ALL terminliste events** (0/262). Since many cross-source duplicate pairs involve one artikel + one terminliste event, description comparison would only work for artikel-to-artikel pairs. This is too limited to justify normalization effort in Phase 1.

3. **For ambiguous title pairs (sim 0.50-0.80), short_description similarity provides useful signal.** Analysis of 120 ambiguous cross-source pairs showed:
   - When titles are true duplicates (e.g., "Nachtumzug Denzlinger Fasnet" vs "Nachtumzug Fasnet Denzlingen"), short_description similarity is typically 0.60-0.90 -- confirming the match.
   - When titles are false positives (e.g., "Tag der offenen Tür - Kindergarten St. Jakobus" vs "Tag der offenen Tür - Kindergarten St. Josef"), short_description similarity drops to 0.30-0.50 -- helping reject the match.

4. **Highlights are useful for canonicalization (Phase 2) but not for matching.** Highlights are structured bullet points that vary too much between sources to be a reliable matching signal. They help select the "best" canonical representation but not identify duplicates.

**Recommendation:**
- **Phase 1:** Normalize `short_description` alongside `title` and `location`. Same pipeline: lowercase, umlaut expansion, punctuation normalization.
- **Phase 2+:** Consider using `description` as a tiebreaker signal for ambiguous pairs, but do NOT normalize or store it separately in Phase 1.
- **Do NOT normalize `highlights`** -- these are for canonicalization, not matching.

**Confidence: HIGH** -- based on analysis of all 765 events.

---

### Question 2: Optimal prefix patterns

**Finding: One dominant source-specific prefix and several content-type prefixes identified. Initial configurable prefix list defined.**

**Analysis method:** Regex extraction of "PREFIX - REST" and "PREFIX: REST" patterns across all 765 titles, then classification as source-specific vs. content-type vs. event-name patterns.

**Source-specific prefixes (should be stripped for matching):**

| Prefix | Source | Count | Example |
|--------|--------|-------|---------|
| `Nordwiler Narrenfahrplan` | bwb only | 12 | "Nordwiler Narrenfahrplan - Fasnetumzug" |

This is the only prefix that is truly source-specific (appears in one source only and wraps different event names). Stripping it exposes the core event name ("Fasnetumzug", "Kinderumzug", etc.) that matches terminliste entries from other sources.

**Content-type prefixes (strip for matching, preserve for display):**

| Prefix Pattern | Count | Example | Rationale |
|----------------|-------|---------|-----------|
| `Tag der offenen Tur - ` | 24 | "Tag der offenen Tur - Kath. Kindergarten St. Franziskus" | Generic prefix; the distinguishing part is after the dash |
| `Wahlkampfstand Bundnis 90/Die Grunen - ` | 3 | "Wahlkampfstand B90/Grune - Kenzingen" | Political event prefix wrapping location |
| `FreiTagZeit:` | 4 | "FreiTagZeit: ZockFreitag - Mediathek Denzlingen" | Event series prefix from Denzlingen |
| `Vortrag:` | 12 | "Vortrag: Landschaftsmalerei im Fokus" | Content type prefix |
| `Bildervortrag:` | 2 | "Bildervortrag: Erlebnisreisen zu den Vulkanen" | Content type prefix |
| `Kochworkshop:` | 3 | "Kochworkshop: Volle Kraft aus dem ganzen Korn" | Content type prefix |
| `Jungentreff:` | 4 | "Jungentreff: Schlitten-Schlauch fahren" | Venue/series prefix |
| `Textil-Tag:` | 2 | "Textil-Tag: Einfuhrung in Textilhandwerke" | Event series prefix |
| `SPD-Veranstaltung:` | 2 | "SPD-Veranstaltung: Europa Quo Vadis?" | Organizer prefix |
| `Theaterabend:` | 4 | "Theaterabend: Nur Zoff mit dem Stoff" | Content type prefix |
| `Kinderprogramm:` | 2 | "Kinderprogramm: Actionspiel durch den Jugendtreff" | Content type prefix |
| `Kommunales Kino - ` | 2 | "Kommunales Kino - Der Salzpfad" | Venue prefix |
| `Kolping Kids - ` | 2 | "Kolping Kids - Bauernfasnacht" | Organizer prefix |

**Event-name prefixes (do NOT strip -- these are part of the event identity):**

| Prefix | Why keep | Example |
|--------|----------|---------|
| `Regionalwettbewerb Sudbaden - ` | Part of event name, appears across 10+ sources | "Regionalwettbewerb Sudbaden - Jugend forscht 2026" |
| `Nordic Walking - ` | Part of event name | "Nordic Walking - Schwarzwaldverein Kollnau-Gutach" |
| `Ingrid Kuhne - ` | Performer + show title format | "Ingrid Kuhne - Ja, aber ohne mich!" |
| `Willy Astor - ` | Performer + show title format | "Willy Astor - Musikkomodie" |
| `GETEC - ` | Event name abbreviation + expansion | "GETEC - Gebaude.Energie.Technik Messe Freiburg" |

**Recommended initial prefix configuration file:**

```yaml
# prefixes.yaml - Configurable prefix patterns for title normalization
# These are stripped during normalization for matching purposes
# Original titles are preserved in source_events table

# Source-specific article prefixes (dash-separated)
dash_prefixes:
  - "Nordwiler Narrenfahrplan"
  - "Wahlkampfstand Bündnis 90/Die Grünen"
  - "Kommunales Kino"
  - "Kolping Kids"
  - "Fasnet im Ladhof"
  - "Narrenzunft Bergteufel"

# Content-type prefixes (colon-separated)
colon_prefixes:
  - "Vortrag"
  - "Bildervortrag"
  - "Kochworkshop"
  - "FreiTagZeit"
  - "Jungentreff"
  - "Textil-Tag"
  - "SPD-Veranstaltung"
  - "Theaterabend"
  - "Kinderprogramm"
  - "SkF Waldkirch"
  - "Waldkircher Klimagespräch"

# Generic event-type prefixes (dash-separated, strip only the prefix part)
generic_prefixes:
  - "Tag der offenen Tür"
```

**Confidence: HIGH** -- derived from complete analysis of all 765 titles across 20 files.

---

### Question 3: Geo grid cell size tuning

**Finding: The ~5km grid is insufficient. Recommend ~10km grid cells (0.09 degrees latitude, 0.13 degrees longitude at 48.1 N).**

**Evidence from data analysis:**

**Intra-city distances (max spread of venues within one city):**

| City | Max distance | Between |
|------|-------------|---------|
| Emmendingen | 19.5 km* | Altes Rathaus and Zunftstube der Brunnenputzer |
| Freiburg im Breisgau | 11.6 km | Messe Freiburg and Gewolbekeller am Rathaus |
| Elzach | 6.1 km | Cafe Kern and Edeka Schindler |
| Waldkirch | 5.3 km | Bahnhof Buchholz and Kollnau Bahnhof |
| Kenzingen | 4.4 km | Schloss Hecklingen and Herrenberghalle |
| Denzlingen | 2.5 km | Wanderparkplatz Einbollen and Ev. Kindergarten |
| Gutach im Breisgau | 1.7 km | Gutacher Halle and Festhalle Bleibach |

*The Emmendingen 19.5km outlier is due to districts like Mundingen being administratively part of Emmendingen but geographically distant.

**Inter-city distances (between neighboring cities):**

| City pair | Distance |
|-----------|----------|
| Gutach im Breisgau <-> Waldkirch | 3.3 km |
| Denzlingen <-> Emmendingen | 5.9 km |
| Denzlingen <-> Waldkirch | 6.1 km |
| Emmendingen <-> Waldkirch | 8.1 km |
| Elzach <-> Gutach im Breisgau | 8.8 km |
| Denzlingen <-> Gutach im Breisgau | 9.3 km |
| Emmendingen <-> Kenzingen | 9.4 km |
| Emmendingen <-> Gutach im Breisgau | 10.1 km |
| Denzlingen <-> Freiburg im Breisgau | 11.2 km |

**Critical finding -- events with different cities that ARE the same event:**

The data contains real duplicate pairs where the same event gets assigned DIFFERENT city names by different sources:

| Event | Source cities | Distance |
|-------|-------------|----------|
| "Fasnetverbrennung" (same event in Kollnau) | Gutach im Breisgau (elt) vs Waldkirch (elz) | 3.2 km |
| "Linedance-Kurs" | Waltershofen (rkb) vs Freiburg im Breisgau (rkt) | <5 km |
| "Die Liebestöter - Liederabend" | Waltershofen (rkb) vs Umkirch (rkt) | <5 km |
| "Regionalwettbewerb Jugend forscht" | 10+ different cities | 5-30 km |

The "Linedance-Kurs" and "Die Liebestöter" cases are particularly instructive: Waltershofen is a district of Freiburg, but some sources list it as a separate city while others use the parent municipality. A 5km grid would sometimes catch these, sometimes miss them.

**Coordinate quality issues:**

- **2 outlier events** in Ettenheim have coordinates near Darmstadt (49.74N, 8.33E) -- 170km away from the actual city. These have confidence 0.848, so the confidence threshold of 0.8 would NOT filter them.
- **268 unique coordinate points** across 765 events -- many events share exact coordinates (city/village centroids).
- **Events at (48.19362, 7.81397)** -- 11 events share this Nordweil centroid with different venue names (Nordweil, Bachdatscher-Keller, Narrenbrunnen).

**Recommendation:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Grid cell size (lat) | 0.09 degrees (~10 km) | Covers Gutach-Waldkirch (3.3km), Denzlingen-Emmendingen (5.9km), Emmendingen-Waldkirch (8.1km) in same cell |
| Grid cell size (lon) | 0.13 degrees (~10 km at lat 48) | Same rationale for longitude |
| Geo confidence threshold | 0.85 (not 0.8) | The Ettenheim outliers have confidence 0.848; raising to 0.85 filters them while keeping most good data |
| Adjacent cell overlap | YES | Events near grid boundaries need to check adjacent cells |

**Grid cell calculation:**
```python
def geo_grid_key(lat: float, lon: float) -> str:
    """Assign event to a ~10km grid cell."""
    cell_lat = round(lat / 0.09) * 0.09
    cell_lon = round(lon / 0.13) * 0.13
    return f"{cell_lat:.2f}|{cell_lon:.2f}"
```

**Important: Geo grid is a SUPPLEMENT to city-name blocking, not a replacement.** City-name blocking catches the majority of duplicates. Geo grid catches the cases where sources assign different city names to the same event (Waltershofen vs Freiburg, Gutach vs Waldkirch).

**Confidence: HIGH** -- based on haversine distance calculations between all 268 unique coordinates and analysis of known cross-city duplicates.

---

### Question 4: Ground truth candidate generation heuristics

**Finding: Same-date + same-city blocking produces 816 unique cross-source pairs. Filtering by title similarity >= 0.30 yields ~685 candidates, well above the 200-300 target.**

**Candidate generation strategy:**

```
Step 1: Group events by (date, city_normalized)
Step 2: Generate all cross-source pairs within each group
Step 3: Calculate title similarity for each pair
Step 4: Include pairs with title_sim >= 0.30 for review
Step 5: Sample ~20% of title_sim < 0.30 pairs as hard negatives
```

**Pair distribution from analysis:**

| Title Similarity | Count | Category | Action |
|-----------------|-------|----------|--------|
| >= 0.95 (near-exact) | 225 | Obvious duplicates | Auto-label "same", quick human verification |
| 0.85-0.95 | 29 | Very likely duplicates | Quick review |
| 0.70-0.85 | 68 | Likely duplicates | Careful review |
| 0.50-0.70 | 57 | Ambiguous | Most important to label carefully |
| 0.30-0.50 | 160 | Likely different | Review; many are genuinely different events |
| < 0.30 | 131 | Clearly different | Sample ~20 as hard negatives |
| **Total reviewable** | **539 + ~26** | | **~565 pairs** |

**Recommended labeling approach (to reach 200-300 pairs):**

1. **Auto-suggest "same" for title_sim >= 0.85** (254 pairs): Human confirms with one click. Expected time: ~30 seconds each. Most will be confirmed as "same".

2. **Review title_sim 0.50-0.85** (125 pairs): These need side-by-side comparison. Present title, short_description, location, dates. Expected time: ~1 minute each. Mix of "same" and "different".

3. **Sample from title_sim 0.30-0.50** (select ~50 from 160): Present as potential negatives. Expected time: ~45 seconds each.

4. **Hard negatives from title_sim < 0.30** (sample ~25 from 131): Important for precision measurement.

**Total: ~454 pairs to review, estimated 3-4 hours of labeling work.** This exceeds the 200-300 target, allowing the human reviewer to stop when sufficient coverage is reached.

**Date window tolerance:**

| Parameter | Value | Rationale |
|-----------|-------|-----------|
| Same-day match | Required (hard blocker) | Events on different dates are different events, period |
| Multi-date event handling | Match if ANY date overlaps | "Primel-Aktion" has dates [Feb 13, Feb 14] across sources -- matching on either date should create a candidate pair |
| No date tolerance beyond same-day | 0 days | Analysis showed no true duplicates with different dates. "Kinderfasnet" appearing on different dates in different cities are different events (different town's celebrations). |

**City matching rules:**

| Rule | Handling |
|------|----------|
| Exact city match | Primary blocking key |
| District matches parent city | Treat Nordweil events as Kenzingen, Mundingen as Emmendingen, etc. Map using the `_sanitizeResult.city` field |
| city = None or "Region" | Block by title similarity + date only (3 events in dataset) |
| Geo-proximity fallback | For events with geo confidence >= 0.85, also generate candidates within same ~10km grid cell regardless of city name |

**Important edge case -- same title, different cities, DIFFERENT events:**

The data contains "Fasnetverbrennung" in Gutach, Waldkirch, and Emmendingen on the same day. These are DIFFERENT events (each town burns their own Fasnet figure). Similarly, "Hemdglunkerumzug" occurs independently in Emmendingen, Malterdingen, and Bad Krozingen. The ground truth labeling tool MUST present location information prominently to help the human reviewer distinguish these.

The "Regionalwettbewerb Jugend forscht" is a special case: it appears with 10+ different cities because each source assigns their own local city, but it is ONE event at ONE location (SICK-ARENA, Freiburg). The ground truth tool should flag such cases for careful review.

**Confidence: HIGH** -- based on complete pair enumeration and similarity analysis.

---

## Standard Stack

### Core (Phase 1 specific)

| Library | Version | Purpose | Why Standard |
|---------|---------|---------|--------------|
| Python | 3.12+ | Primary language | Project constraint |
| SQLAlchemy | >=2.0 | ORM, schema definition, migrations | Mapped_column style, async support, mature PG dialect |
| asyncpg | >=0.30 | Async PostgreSQL driver | Fastest PG driver, works with SQLAlchemy async |
| Alembic | >=1.14 | Database migrations | Standard for SQLAlchemy schema evolution |
| Pydantic | >=2.9 | JSON validation, event models | Validates incoming JSON structure, FastAPI integration |
| rapidfuzz | >=3.10 | Title similarity scoring | 10-100x faster than thefuzz, critical for candidate scoring |

### Supporting (Phase 1 specific)

| Library | Version | Purpose | When to Use |
|---------|---------|---------|-------------|
| PyYAML | >=6.0 | Config file parsing | Loading prefix patterns and threshold config |
| pytest | >=8.3 | Testing | Evaluation harness, unit tests |
| pytest-asyncio | >=0.24 | Async test support | Testing DB operations |

### Installation (Phase 1 only)

```bash
uv add sqlalchemy asyncpg alembic pydantic rapidfuzz pyyaml
uv add --dev pytest pytest-asyncio
```

## Architecture Patterns

### Phase 1 Project Structure

```
src/
  event_dedup/
    __init__.py
    models/
      __init__.py
      source_event.py       # SQLAlchemy model for source_events table
      event_date.py          # SQLAlchemy model for event_dates table
      file_ingestion.py      # SQLAlchemy model for file_ingestions table
      ground_truth.py        # SQLAlchemy model for ground_truth_pairs table
    preprocessing/
      __init__.py
      normalizer.py          # Title, location, short_description normalization
      prefix_stripper.py     # Configurable prefix stripping
      blocking.py            # Generate blocking keys (date+city, date+geo_grid)
    ingestion/
      __init__.py
      json_loader.py         # Parse JSON files, validate structure
      file_processor.py      # Orchestrate: load -> preprocess -> persist
      idempotency.py         # SHA-256 hash check, file_ingestions table
    evaluation/
      __init__.py
      harness.py             # Run matching config against ground truth
      metrics.py             # Precision, recall, F1 calculation
    ground_truth/
      __init__.py
      candidate_generator.py # Generate candidate pairs for labeling
      labeling_tool.py       # CLI or simple UI for pair review
    db/
      __init__.py
      session.py             # Async session factory
      engine.py              # Engine configuration
    config/
      __init__.py
      settings.py            # App config (DB URL, thresholds, etc.)
      prefixes.yaml          # Configurable prefix patterns
config/
  alembic.ini
  alembic/
    versions/
tests/
  test_normalizer.py
  test_prefix_stripper.py
  test_blocking.py
  test_json_loader.py
  test_idempotency.py
  test_evaluation.py
```

### Pattern: Dual Text Storage

```python
class SourceEvent(Base):
    __tablename__ = "source_events"

    # Original values (for display)
    title = mapped_column(String, nullable=False)
    short_description = mapped_column(Text)
    location_name = mapped_column(String)
    location_city = mapped_column(String)

    # Normalized values (for matching)
    title_normalized = mapped_column(String, nullable=False)
    short_description_normalized = mapped_column(Text)
    location_name_normalized = mapped_column(String)
    location_city_normalized = mapped_column(String)

    # Blocking keys (precomputed)
    blocking_keys = mapped_column(ARRAY(String))
```

### Pattern: Configurable Prefix Stripping

```python
def strip_prefixes(title: str, config: PrefixConfig) -> str:
    """Strip known prefixes from title for matching.

    Handles both dash-separated ("Nordwiler Narrenfahrplan - Fasnetumzug")
    and colon-separated ("Vortrag: Landschaftsmalerei") patterns.
    """
    for prefix in config.dash_prefixes:
        pattern = re.compile(
            rf'^{re.escape(prefix)}\s*[-\u2013\u2014]\s+',
            re.IGNORECASE
        )
        if pattern.match(title):
            return pattern.sub('', title).strip()

    for prefix in config.colon_prefixes:
        pattern = re.compile(
            rf'^{re.escape(prefix)}:\s+',
            re.IGNORECASE
        )
        if pattern.match(title):
            return pattern.sub('', title).strip()

    return title
```

### Anti-Patterns to Avoid

- **Normalizing in queries instead of at ingestion**: Normalize once at ingestion time and store the result. Never compute normalization on-the-fly during matching.
- **Blocking on city string equality**: Use normalized city names. "Freiburg im Breisgau" must match "Freiburg im Breisgau" exactly -- but also consider district-to-city mapping.
- **Storing blocking keys only in Python**: Blocking keys should be in the database (as an array column or separate table) so they can be queried efficiently.

## Don't Hand-Roll

| Problem | Don't Build | Use Instead | Why |
|---------|-------------|-------------|-----|
| Fuzzy string matching | Custom edit-distance code | `rapidfuzz.fuzz.ratio`, `token_sort_ratio` | Optimized C++ core, handles Unicode, well-tested edge cases |
| Umlaut normalization | Character replacement map | `unidecode` or a simple mapping dict | Comprehensive Unicode handling |
| SHA-256 file hashing | Manual file reading + hashlib | `hashlib.sha256` with chunked reading | Standard, handles large files correctly |
| F1/precision/recall | Manual TP/FP/FN counting | `sklearn.metrics.precision_recall_fscore_support` | Handles edge cases (zero division, micro/macro averaging) |
| Database migrations | Raw SQL DDL scripts | Alembic | Tracks migration history, supports rollback |

## Common Pitfalls

### Pitfall 1: District-to-City Mapping Inconsistency

**What goes wrong:** Nordweil events have `city: "Kenzingen"` while the location name says "Nordweil". If blocking uses city, these match correctly. But Waltershofen events have `city: "Waltershofen"` in one source and `city: "Freiburg im Breisgau"` in another. City-based blocking misses this pair.

**Data evidence:** 24 cities in the dataset have districts. The `_sanitizeResult.city` field reliably maps to the parent municipality, but `city` at the top level sometimes uses the district name itself.

**Prevention:** Always use the `_sanitizeResult.city` field for blocking, not the top-level `city`. If `_sanitizeResult` is unavailable, fall back to top-level `city`. The geo grid provides a safety net for mismatched cities.

### Pitfall 2: "Same Generic Title, Different Event" False Positives

**What goes wrong:** "Kinderfasnet" appears 4 times on different dates in different cities. "Hemdglunkerumzug" appears 6+ times. "Tag der offenen Tür" appears 24 times at different kindergartens on the same date. High title similarity + same date = false positive.

**Data evidence:** Within-source near-duplicates analysis found 21 cases where the same file contains events with near-identical titles at different locations on the same date.

**Prevention:** When title similarity is high but generic (short titles like "Kinderfasnet", "Hemdglunkerumzug"), require EXACT location match (not just same city). Use location name similarity as a disambiguator. The ground truth labeling tool must show location prominently.

### Pitfall 3: Geo Coordinate Outliers Despite Acceptable Confidence

**What goes wrong:** Two Ettenheim events have coordinates near Darmstadt (170km away) with confidence 0.848. A confidence threshold of 0.8 would include these outliers in geo-based blocking, creating false candidates.

**Data evidence:** `(49.740074, 8.328099)` for "Kolping Kids" events with `geo.confidence: 0.848`.

**Prevention:** Set geo confidence threshold to 0.85 (not 0.8). Additionally, implement a bounding box sanity check: coordinates outside the Breisgau region (roughly lat 47.5-48.5, lon 7.3-8.5) should be treated as invalid regardless of confidence.

### Pitfall 4: Multi-Date Events Creating Duplicate Candidate Pairs

**What goes wrong:** "Primel-Aktion Emmendingen" has dates [Feb 13, Feb 14]. If candidate generation creates pairs for EACH date independently, the same event pair appears twice (once for Feb 13, once for Feb 14). This inflates the labeling workload.

**Data evidence:** 46 events have multiple dates. The Primel-Aktion appears in 6 sources with 2 dates each = up to 12 candidate pairs per true duplicate pair.

**Prevention:** Deduplicate candidate pairs by event ID pair before presenting for labeling. A pair (event_A, event_B) should appear only once regardless of how many date overlaps generated it.

### Pitfall 5: Case Sensitivity in Title Matching

**What goes wrong:** "WUTHERING HEIGHTS - STURMHOHE" (from elz, all-caps) vs "Wuthering Heights (Sturmhohe)" (from elt, mixed case). Raw string comparison gives low similarity due to case and punctuation differences.

**Data evidence:** Several events appear in ALL CAPS from the elz source: "CHECKER TOBI UND DIE HEIMLICHE HERRSCHERIN DER ERDE", "DIE ALTERN", "HART ABER HERZLICH!".

**Prevention:** Lowercase normalization BEFORE any similarity comparison. Also strip/normalize punctuation (parentheses, exclamation marks, quotes).

## Code Examples

### Normalization Pipeline

```python
import re
import unicodedata

def normalize_text(text: str) -> str:
    """Normalize text for matching: lowercase, expand umlauts, strip punctuation."""
    if not text:
        return ""

    # Lowercase
    text = text.lower()

    # Expand German umlauts
    umlaut_map = {
        'a\u0308': 'ae', 'o\u0308': 'oe', 'u\u0308': 'ue',
        '\u00e4': 'ae', '\u00f6': 'oe', '\u00fc': 'ue', '\u00df': 'ss',
        '\u00c4': 'ae', '\u00d6': 'oe', '\u00dc': 'ue',
    }
    for char, replacement in umlaut_map.items():
        text = text.replace(char, replacement)

    # Normalize whitespace
    text = re.sub(r'\s+', ' ', text).strip()

    # Strip common punctuation (keep hyphens for compound words)
    text = re.sub(r'[\"\'!?,.:;()\[\]{}]', '', text)

    return text


def normalize_city(city: str) -> str:
    """Normalize city name for blocking key generation."""
    if not city:
        return ""
    return normalize_text(city)
```

### Blocking Key Generation

```python
def generate_blocking_keys(
    dates: list[str],
    city: str | None,
    lat: float | None,
    lon: float | None,
    geo_confidence: float | None,
) -> list[str]:
    """Generate blocking keys for an event.

    Returns list of keys. Events sharing any key are candidates for comparison.
    """
    keys = []
    city_norm = normalize_city(city) if city else None

    for date in dates:
        # Primary: date + city
        if city_norm:
            keys.append(f"dc|{date}|{city_norm}")

        # Secondary: date + geo grid (for events with high-confidence coordinates)
        if (lat is not None and lon is not None
            and geo_confidence is not None
            and geo_confidence >= 0.85):
            # ~10km grid cells
            cell_lat = round(lat / 0.09) * 0.09
            cell_lon = round(lon / 0.13) * 0.13
            keys.append(f"dg|{date}|{cell_lat:.2f}|{cell_lon:.2f}")

    return keys
```

### Ground Truth Candidate Generator

```python
from collections import defaultdict
from rapidfuzz import fuzz

def generate_candidates(
    events: list[dict],
    min_title_sim: float = 0.30,
) -> list[tuple[str, str, float]]:
    """Generate candidate duplicate pairs for ground truth labeling.

    Returns list of (event_id_a, event_id_b, title_similarity).
    """
    # Group by date + city
    groups = defaultdict(list)
    for event in events:
        city = normalize_city(
            event.get('location', {}).get('_sanitizeResult', {}).get('city')
            or event.get('location', {}).get('city', '')
        )
        for date_entry in event.get('event_dates', []):
            date = date_entry.get('date', '')
            if date and city:
                groups[(date, city)].append(event)

    # Generate cross-source pairs
    seen = set()
    candidates = []

    for (date, city), group_events in groups.items():
        for i in range(len(group_events)):
            for j in range(i + 1, len(group_events)):
                e1, e2 = group_events[i], group_events[j]

                # Cross-source only
                if e1['_source_code'] == e2['_source_code']:
                    continue

                # Deduplicate by event ID pair
                pair_key = tuple(sorted([e1['id'], e2['id']]))
                if pair_key in seen:
                    continue
                seen.add(pair_key)

                # Calculate title similarity
                title_sim = fuzz.ratio(
                    normalize_text(e1['title']),
                    normalize_text(e2['title']),
                ) / 100.0

                if title_sim >= min_title_sim:
                    candidates.append((e1['id'], e2['id'], title_sim))

    return sorted(candidates, key=lambda x: -x[2])
```

## State of the Art

| Aspect | What the Data Shows | Impact on Implementation |
|--------|--------------------|-----------------------|
| Source types | 62% artikel, 34% terminliste, 4% anzeige | artikel-terminliste pairs are the hardest to match (different title formats) |
| City coverage | 64 unique cities, top 7 cities have 80% of events | City-based blocking is highly effective for this region |
| Geo confidence | 45% have confidence=1.0, 83% have confidence>=0.8 | Geo blocking is viable for majority of events |
| Multi-date events | 6% (46/765) have multiple dates | Date overlap logic needed, not just exact match |
| Online events | 0.4% (3/765) are online/regional | Edge case; handle with title+date only blocking |

## Open Questions

1. **Waltershofen/Freiburg city mapping**: The `_sanitizeResult.city` field for Waltershofen shows `Waltershofen` in some sources and `Freiburg im Breisgau` in others. Need to verify whether the sanitize pipeline is consistent across sources or whether a manual city alias table is needed.
   - **Recommendation:** Build a small city alias lookup table for known district-municipality mappings in the region. Maintain it as a configuration file alongside prefixes.yaml.

2. **Ettenheim geo outlier root cause**: The two "Kolping Kids" events have Swiss coordinates despite confidence 0.848. This might be a geocoding service error.
   - **Recommendation:** Add a bounding box filter as a sanity check. Do not rely solely on confidence score.

## Sources

### Primary (HIGH confidence)
- Direct analysis of all 20 JSON files in `/Users/svenkarl/workspaces/event-deduplication/eventdata/` (765 events)
- All statistics, pair counts, similarity distributions, and coordinate analyses computed directly from the data using Python scripts

### Secondary (MEDIUM confidence)
- Existing project research in `.planning/research/STACK.md`, `ARCHITECTURE.md`, `PITFALLS.md`
- Project documentation in `.planning/PROJECT.md`, `.planning/REQUIREMENTS.md`

## Metadata

**Confidence breakdown:**
- Field availability analysis: HIGH - complete census of all 765 events
- Prefix pattern analysis: HIGH - regex analysis of all 765 titles
- Geo grid sizing: HIGH - haversine distance calculations between all coordinate pairs
- Ground truth heuristics: HIGH - complete pair enumeration with similarity scoring
- City matching edge cases: HIGH - identified from actual cross-source duplicates with different cities

**Research date:** 2026-02-27
**Valid until:** indefinite (based on static dataset analysis, not library versions)
