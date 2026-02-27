# Domain Pitfalls

**Domain:** Event deduplication from regional PDF magazine sources (German-language)
**Researched:** 2026-02-27
**Confidence:** MEDIUM (training data only -- WebSearch/WebFetch unavailable; findings based on established entity resolution literature and direct analysis of project event data)

---

## Critical Pitfalls

Mistakes that cause rewrites, accuracy collapse, or systemic failures.

### Pitfall 1: Treating Deduplication as a Pairwise Problem Instead of a Clustering Problem

**What goes wrong:** You compare event A to event B and decide "match" or "no match" for each pair independently. This leads to transitive inconsistencies: A matches B, B matches C, but A does not match C. You end up with overlapping groups, split clusters, or contradictory canonical events. The 65% accuracy in the current system likely stems partly from this.

**Why it happens:** Pairwise comparison is the intuitive first approach. It is easy to implement: for each incoming event, scan the DB for matches. But deduplication is fundamentally a clustering problem -- you need to decide which events form a *group*, not just which pairs match.

**Consequences:**
- Canonical events that represent partial views of the real event
- Same real-world event split across 2-3 canonical events because the chain of similarity was broken at one link
- Merging cascades where fixing one grouping causes a chain of re-evaluations
- Manual review UI becomes overwhelmed with split/merge corrections

**Warning signs:**
- You find canonical events with 2-3 sources when you expected 5-6
- Two canonical events share a date and location but have different titles
- Manual review corrections cluster around "merge these two groups"

**Prevention:**
- Model deduplication as connected-component discovery or clustering, not pairwise yes/no
- Use union-find (disjoint set) data structure for grouping: when A matches B and B matches C, they automatically land in the same group
- After clustering, validate the group: does every member plausibly belong? Flag over-large clusters for review
- Implement group coherence scoring: all members should be within reasonable similarity of the group centroid

**Phase mapping:** Must be addressed in core deduplication engine design (Phase 1/2). Retrofitting clustering onto a pairwise system is a near-complete rewrite.

---

### Pitfall 2: String Similarity Alone for German-Language Title Matching

**What goes wrong:** You use Levenshtein distance, Jaro-Winkler, or cosine similarity on raw titles and get terrible recall for German event names. German compound words, regional dialect variations, and abbreviation patterns defeat character-level similarity.

**Why it happens:** String similarity works well in English demos. But German has specific challenges:
- Compound nouns: "Fasnetumzug" vs "Fasnachtsumzug" vs "Fastnachtsumzug" (same concept, 3 different spellings)
- Title structure variation: "Nordwiler Narrenfahrplan - Fasnetumzug" (article title format) vs "Fasnetumzug Nordweil" (calendar listing format)
- Regional dialect: "Fasnet" (Alemannic) vs "Fasching" (Bavarian/Austrian) vs "Fastnacht" (standard German) -- all mean carnival
- Abbreviations and club names: "NZO" vs "Narrenzunft Oberhausen"
- OCR artifacts: PDF extraction may introduce character-level errors

**Consequences:**
- Low recall: same events with different title structures score below threshold
- The Primel-Aktion example from the data appears in 6 sources -- some may title it "Primel-Aktion Emmendingen", others "Valentinstags-Primeln der AGL", others "Primeln verschenkt am Valentinstag". Pure string similarity misses the semantic link.
- Title-similarity false positives: "Kinderball Waldkirch" vs "Kinderball Krakeelia" have high string similarity but are different events

**Warning signs:**
- Match rate drops sharply for events from "artikel" sources (longer, more varied titles) vs "terminliste" sources (shorter, standardized)
- Fasnet/carnival events have disproportionately low match rates
- High false positive rate for events with common prefixes ("Wahlkampfstand Bundnis 90/Die Grunen - [Location]")

**Prevention:**
- Use multi-signal matching where title is ONE signal, not THE signal. Combine: date overlap + geo proximity + title similarity + category match
- For title comparison, normalize first: strip common prefixes ("Nordwiler Narrenfahrplan - "), lowercase, normalize umlauts (ae/oe/ue), strip punctuation
- Build a domain-specific synonym dictionary: Fasnet=Fasching=Fastnacht=Karneval, Umzug=Zug=Parade
- Consider token-based similarity (Jaccard on word tokens) in addition to character-level similarity -- "Fasnetumzug Nordweil" and "Nordwiler Fasnetumzug" share key tokens even though character order differs
- Reserve AI matching for the cases where title similarity is ambiguous but other signals are strong

**Phase mapping:** Title normalization and multi-signal scoring belong in Phase 1. Domain synonym dictionary is Phase 2 enhancement. AI fallback is Phase 2/3.

---

### Pitfall 3: Ignoring the Temporal Dimension of Deduplication

**What goes wrong:** You match against the entire database instead of scoping matches to a relevant time window. Performance degrades as the database grows, and you get false positives between recurring events (same event happening weekly/monthly at the same venue).

**Why it happens:** The database will accumulate events over weeks and months. A "Kinderball" happens every year during Fasnet. Without temporal scoping, this year's event matches last year's, or this week's recurring market matches next week's.

**Consequences:**
- Merging distinct occurrences of recurring events (every Tuesday's "Wochenmarkt Emmendingen" gets collapsed into one canonical event)
- Performance: comparing against 50,000 historical events when only the last 2-4 weeks are relevant
- False positives spike for long-running series events (weekly lectures, monthly club meetings)

**Warning signs:**
- Canonical events accumulate more and more source events over time beyond what makes sense
- "Wochenmarkt" or "Probe Musikverein" events have 20+ source events merged
- Deduplication processing time grows linearly with database size

**Prevention:**
- Implement a date-window filter as the FIRST blocking pass: only compare events whose dates overlap or are within 1-2 days of each other
- For events without end_date, infer a reasonable window (single-day events: same day only; multi-day events: within the date range)
- Treat date matching as a hard blocker, not a soft signal -- events on different dates are never the same event (exception: date extraction errors, handled separately)
- Index events by date for O(1) candidate retrieval instead of full-table scan
- For recurring events, each occurrence is a distinct canonical event

**Phase mapping:** Date-windowed blocking must be in Phase 1. It is both a correctness and performance requirement. Without it, the system breaks as data accumulates.

---

### Pitfall 4: Threshold Tuning Without a Ground Truth Dataset

**What goes wrong:** You pick similarity thresholds (e.g., "title similarity > 0.7 AND geo distance < 5km") by intuition, deploy, and discover the thresholds are wrong for your data distribution. You adjust, break other cases, and enter an endless tuning loop with no way to measure improvement.

**Why it happens:** Deduplication accuracy depends entirely on threshold calibration. Without labeled data (pairs of events marked as "same" or "different"), you cannot measure precision/recall, and every change is a guess.

**Consequences:**
- The current 65% accuracy is unmeasurable -- is it 65% precision? Recall? F1? For which event types?
- Threshold changes improve one category (Fasnet events) while breaking another (political events)
- No regression detection: you cannot tell if a code change made things better or worse
- AI-assisted matching has no baseline to beat

**Warning signs:**
- You cannot answer "what is our current precision and recall?"
- Arguments about thresholds devolve into "I found this one event that..." anecdotes
- Every threshold change feels like whack-a-mole

**Prevention:**
- Before building the deduplication engine, create a labeled ground truth dataset from the 20 sample files (765 events). Manually identify which events across sources are the same real-world event. This is ~2-4 hours of work and is the single highest-ROI task.
- Structure the ground truth as: `{event_id_1, event_id_2, label: same|different}` for at least 200-300 pairs covering easy matches, hard matches, and tricky non-matches
- Build an evaluation harness that runs deduplication against ground truth and reports precision, recall, F1, and per-category breakdowns
- Use the ground truth to tune thresholds empirically, not by intuition
- Refresh the ground truth as new source patterns emerge

**Phase mapping:** Ground truth creation should be Phase 0 (before building the engine) or the very first task of Phase 1. The evaluation harness should be built alongside the first matching algorithm. Everything else depends on this.

---

### Pitfall 5: The "Best Field" Merge Trap -- Canonical Event Field Conflicts

**What goes wrong:** When merging source events into a canonical event, you implement "pick the best field from all sources" and discover that "best" is ambiguous, contradictory, or destructive. Source A says start_time is 19:11, source B says 19:30. Source A says location is "Marktplatz", source B says "Marktplatz Waldkirch". Which is "best"?

**Why it happens:** The PROJECT.md specifies "best title, longest description, richest highlights, most precise location." This sounds simple but the real data is messy:
- Times differ slightly (OCR error? Rounded? Different sources have different actual times?)
- Locations at different specificity (both valid, but "Marktplatz Waldkirch" is more complete than "Marktplatz")
- Descriptions contain source-specific framing that does not compose
- Categories and boolean flags disagree across sources

**Consequences:**
- Canonical events with internally inconsistent data (start_time from source A, description from source B that references a different time)
- Information loss: "longest description" is not always "best description" -- a shorter, more accurate description beats a longer, AI-hallucinated one
- Location merging creates Frankenstein addresses (street from A, city from B, geo from C)
- is_family_event: source A says true, source B says false -- which wins?

**Warning signs:**
- Canonical events with descriptions that mention times/details inconsistent with their own date/time fields
- Location fields that do not form a coherent address
- Frequent manual corrections to canonical event fields (not groupings)

**Prevention:**
- Define explicit merge rules per field type:
  - **Times:** Use the source with the highest confidence_score, or the most precise time (19:30 over 19:11 if 19:11 looks like an OCR artifact with the unusual minute value)
  - **Location:** Pick the most complete location object (most non-null fields), not mix-and-match fields from different sources
  - **Description:** Prefer "artikel" source_type over "terminliste" (articles have richer descriptions), then longest among those
  - **Booleans (is_family_event, etc.):** If any source says true, mark as true (false may just mean "not specified")
  - **Categories:** Union of all source categories
- Track provenance: for each field in the canonical event, record which source it came from
- When conflicts exist, flag for manual review rather than silently picking one
- Never cross-pollinate fields between sources (do not mix location from A with time from B into a single record without explicit rules)

**Phase mapping:** Merge strategy design is Phase 1 (core engine). Provenance tracking and conflict detection are Phase 2. Manual review of field conflicts is Phase 3 (frontend).

---

## Moderate Pitfalls

### Pitfall 6: Geo Coordinate False Confidence

**What goes wrong:** You rely on geo proximity as a strong deduplication signal, but the geo coordinates in the data have varying confidence levels and many default to city centroids rather than actual venue locations.

**Why it happens:** Looking at the actual event data, many events geolocate to the same coordinates (e.g., 7.813966088, 48.19361781 appears for multiple distinct venues in Nordweil because it is the village centroid). When geo confidence is < 1.0, the coordinates are often approximations. Two events at the same city centroid appear to be at "the same location" when they might be at different venues.

**Prevention:**
- Weight geo proximity by the confidence scores of BOTH events: if either has confidence < 0.85, reduce the weight of the geo signal
- Set a minimum confidence threshold (e.g., 0.9) below which geo is treated as "unknown location" rather than a matching signal
- Use location name matching as the primary location signal; geo proximity as secondary confirmation
- Be aware that small German villages (Nordweil, Sexau) may have all events geocode to the same centroid

**Detection:** Plot geo coordinates of matched pairs -- if many matches rely on coordinates that cluster at round numbers or city centroids, the geo signal is providing false confidence.

**Phase mapping:** Phase 1 (matching algorithm design). Must account for geo confidence from the start.

---

### Pitfall 7: Blocking Strategy Too Aggressive or Too Loose

**What goes wrong:** To avoid O(n^2) pairwise comparisons, you implement "blocking" -- only comparing events that share a key (same date, same city, etc.). If blocking is too aggressive (same date AND same city), you miss events where the city name differs between sources. If blocking is too loose (same week), you compare too many pairs and performance suffers.

**Prevention:**
- Use multiple blocking passes with different keys:
  1. Same date + same city (catches most matches)
  2. Same date + geo proximity within 10km (catches city name variations)
  3. Same date + high title similarity on first pass (catches everything else)
- Each blocking pass feeds candidates to the full comparison pipeline
- Monitor blocking recall: what percentage of known matches (from ground truth) are captured by each blocking strategy?
- Log blocked-out pairs periodically to check for systematic misses

**Detection:** After building the ground truth dataset, measure how many true matches survive each blocking pass. If blocking recall < 95%, it is too aggressive.

**Phase mapping:** Phase 1 (core matching). Blocking strategy must be designed alongside the matching pipeline.

---

### Pitfall 8: Treating AI-Assisted Matching as a Black Box

**What goes wrong:** You send ambiguous event pairs to an LLM with a prompt like "Are these the same event?" and accept the yes/no answer. The LLM hallucinates reasoning, gives inconsistent answers for similar cases, and you cannot debug or improve it because the decision is opaque.

**Prevention:**
- Provide structured input to the LLM: both events' normalized fields side by side, the similarity scores from the deterministic pass, and the specific reason this pair is ambiguous
- Require structured output: not just yes/no but confidence score + reasoning + which fields matched/conflicted
- Log all AI decisions with full prompt/response for review and improvement
- Set a confidence threshold for AI decisions: if the AI is uncertain, route to manual review rather than auto-deciding
- Test AI decisions against the ground truth dataset to measure its accuracy separately from the deterministic matcher
- Cache AI decisions: if the same pair is re-evaluated (e.g., on re-import), use the cached decision

**Detection:** Track AI match rate over time. If it is consistently saying "yes" or consistently saying "no," the selection of pairs sent to AI is poorly calibrated (too easy or too hard).

**Phase mapping:** Phase 2/3 (AI-assisted matching). But the logging/evaluation infrastructure should be designed in Phase 1 as part of the evaluation harness.

---

### Pitfall 9: Incremental Processing Without Idempotency

**What goes wrong:** The system watches a directory for new JSON files. A file is processed, events are deduplicated and stored. Then the same file is re-dropped (re-extraction, pipeline retry, operator error). Without idempotency, you get duplicate canonical events or duplicate source linkages.

**Prevention:**
- Track processed files by filename + hash in the database. If a file with the same hash has been processed, skip it. If same filename but different hash (re-extraction), handle as an update.
- Use the source event's `id` field (e.g., "pdf-9d58bea1-1-6") as a natural key. If a source event with the same ID already exists, update rather than insert.
- Make the deduplication pipeline idempotent: running the same input twice produces the same result
- Handle the "updated source" case: when a source event is re-extracted with different data, re-evaluate its canonical group membership

**Detection:** Count source events per canonical event. If any have suspiciously high counts, check for duplicated source processing.

**Phase mapping:** Phase 1 (file watcher + ingestion pipeline).

---

### Pitfall 10: Not Handling Multi-Date Events Correctly

**What goes wrong:** Some events span multiple dates (e.g., "Aubach Festival" has date 2026-08-21 with end_date 2026-08-22). The deduplication system treats each date independently or only matches on the first date, causing split duplicates or missed matches.

**Why it happens:** The event_dates field is an array. Some sources list a multi-day event as a single entry with start/end dates, others list it as multiple entries with individual dates (the Primel-Aktion has two dates: 2026-02-13 and 2026-02-14). Different sources may list different subsets of the dates.

**Prevention:**
- Normalize date ranges into a canonical format before matching: convert both `[{date: "2026-02-13"}, {date: "2026-02-14"}]` and `[{date: "2026-02-13", end_date: "2026-02-14"}]` into the same representation
- For date matching, use date range overlap rather than exact date equality
- Handle the case where source A lists 3 dates and source B lists 2 of those 3 -- they should still match
- In the canonical event, union all dates from all sources

**Detection:** Search for canonical events with nearly identical titles/locations but adjacent dates -- these are likely split multi-day events.

**Phase mapping:** Phase 1 (date normalization in the matching pipeline).

---

### Pitfall 11: Neglecting the "Same Venue, Different Event" Problem

**What goes wrong:** Two genuinely different events at the same venue on the same date are incorrectly merged because date + location match strongly, and title similarity is moderate. Example from PROJECT.md: "Kinderball Waldkirch" vs "Kinderball Krakeelia" -- same venue, same day, similar title prefix, but organized by different clubs and are distinct events.

**Prevention:**
- When date + location match strongly, require HIGHER title similarity, not lower, to confirm a match. Strong location match is necessary but not sufficient.
- Use the description and highlights fields as tie-breakers: different organizers, different programs = different events
- Look for differentiating tokens in titles: club names, specific event names after common prefixes ("Kinderball" is generic, "Krakeelia" is specific)
- Consider time-of-day as an additional signal: same venue, same day, but 14:00 vs 20:00 = likely different events

**Detection:** Monitor false positive rate for venues that host many events (Hallen, Buergerhaus, Marktplatz). These are over-represented in false merges.

**Phase mapping:** Phase 1/2 (matching algorithm refinement, especially after initial testing against ground truth).

---

### Pitfall 12: Source-Type Bias in Matching

**What goes wrong:** Events from "artikel" sources have rich titles, descriptions, and highlights. Events from "terminliste" sources have minimal titles and no descriptions. Matching an artikel event to a terminliste event fails because the title formats are completely different, even for the same real-world event.

**Why it happens:** In the actual data, the same "Preismaskenball" event appears as a full article (with organizer names, program details) in one source and as a bare "Preismaskenball, Herrenberghalle, 19:01" in a terminliste. Title similarity between the two representations may be low.

**Prevention:**
- When comparing events of different source_types, adjust comparison strategy: rely more on date + location + key token extraction, less on full-title similarity
- Extract "core event name" from artikel titles by stripping prefix patterns ("Nordwiler Narrenfahrplan - " prefix, source attribution text)
- Build source-type-aware comparison weights: for artikel-vs-terminliste pairs, boost location and date weight, reduce title weight

**Detection:** Measure match rate stratified by source_type pair. If artikel-terminliste matches are significantly lower than artikel-artikel matches, you have this bias.

**Phase mapping:** Phase 2 (after initial matching works for same-type pairs).

---

## Minor Pitfalls

### Pitfall 13: Unicode and Umlaut Normalization Inconsistencies

**What goes wrong:** "Burgerhaus" vs "Buergerhaus" vs "Buergerhaus" (the u-umlaut may appear as u, ue, or the actual Unicode character depending on OCR quality). String comparison treats these as different strings.

**Prevention:**
- Normalize all text before comparison: convert umlauts to two-letter equivalents (ae, oe, ue, ss) OR normalize to full Unicode -- pick one and be consistent
- Normalize common OCR artifacts: straight quotes vs curly quotes, en-dash vs hyphen, non-breaking spaces
- Apply normalization at ingestion time so it only happens once

**Phase mapping:** Phase 1 (text normalization utilities, applied before any comparison).

---

### Pitfall 14: Over-Relying on AI for Cost Reasons Leading to Under-Using It

**What goes wrong:** Fear of AI costs leads to such restrictive escalation criteria that the AI path is almost never triggered. The system effectively becomes a deterministic-only matcher, missing all the hard cases that justified the tiered approach.

**Prevention:**
- Define a clear "ambiguity zone" with measured thresholds: events that score between, say, 0.4 and 0.75 on the deterministic matcher go to AI. Above 0.75 = auto-match. Below 0.4 = auto-reject.
- Monitor the volume of events hitting the AI tier. If it is <5% of comparisons, the zone may be too narrow. If >30%, too wide.
- Calculate actual cost: at 2000 events/week with perhaps 10% needing AI review, that is 200 AI calls/week. At ~$0.01-0.05 per call with a small model, that is $2-10/week. Likely negligible.
- Consider using a small, fast model (Claude Haiku, GPT-4o-mini) for routine AI matching and reserve larger models for edge cases

**Phase mapping:** Phase 2/3 (AI tier implementation). Cost modeling should be done during Phase 1 design.

---

### Pitfall 15: Canonical Event Staleness After Source Updates

**What goes wrong:** A canonical event is created from 3 sources. Later, a 4th source arrives with better data. The system adds the source link but does not re-evaluate which fields are "best" for the canonical event. The canonical event's description stays as the inferior version from the first source.

**Prevention:**
- Implement re-synthesis: when a new source is added to an existing canonical group, re-run the field selection logic across all sources (including the new one)
- Track canonical event "version" -- each re-synthesis increments the version
- In the frontend, show when a canonical event was last updated and from how many sources

**Phase mapping:** Phase 2 (enrichment pipeline).

---

### Pitfall 16: Ignoring Confidence Score Propagation

**What goes wrong:** Source events have confidence_score fields (0.72 to 0.92 in the sample data). The deduplication system ignores these when making match decisions and when selecting "best" fields for canonical events.

**Prevention:**
- Use source confidence_score as a weight in field selection: prefer fields from higher-confidence sources
- Factor source confidence into match decisions: a match involving two high-confidence sources is more trustworthy than one involving a low-confidence source
- Set a minimum confidence threshold below which source events are flagged for review rather than auto-processed

**Phase mapping:** Phase 1 (matching) and Phase 2 (canonical field selection).

---

### Pitfall 17: Testing Only With Current Data Distribution

**What goes wrong:** You test with Fasnet-season data (heavy on carnival events, parade events, club events). The system works great. Then spring/summer comes with a completely different event distribution (outdoor festivals, markets, concerts) and accuracy drops because the matching rules were tuned for Fasnet patterns.

**Prevention:**
- If historical data from other seasons exists, include it in the ground truth dataset
- Design matching rules that are category-agnostic where possible
- Monitor accuracy metrics over time, per category, with automated alerts when precision or recall drops
- Plan for quarterly threshold re-evaluation as event types shift seasonally

**Phase mapping:** Ongoing concern. Ground truth should include seasonal variety if available. Monitoring is Phase 3 (operational).

---

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Ground truth / evaluation | Skipping this to "move faster" | This is the single highest-value task. Without it, everything else is guesswork. 2-4 hours of manual labeling saves weeks of blind tuning. |
| Core matching engine | Pairwise instead of clustering (#1) | Design for clustering from day one. Use union-find or graph-based grouping. |
| Core matching engine | String similarity as primary signal (#2) | Multi-signal matching from the start. Title is one of 4-5 signals. |
| Core matching engine | No date windowing (#3) | Date overlap as first blocking pass. Required for both correctness and performance. |
| Title normalization | German-specific normalization (#2, #13) | Build a normalization pipeline: lowercase, umlaut normalization, prefix stripping, synonym dictionary. |
| Geo matching | False confidence from centroids (#6) | Weight by confidence scores. Treat low-confidence geo as unknown. |
| Canonical event creation | Field conflict resolution (#5) | Explicit per-field merge rules. Provenance tracking. Never mix fields between sources without rules. |
| AI-assisted matching | Black box decisions (#8) | Structured I/O, logging, evaluation against ground truth. |
| File ingestion | Non-idempotent processing (#9) | Source event ID as natural key. File hash tracking. |
| Multi-date events | Split duplicates (#10) | Date range normalization. Overlap-based matching. |
| Same-venue differentiation | False merges (#11) | Require higher title similarity when location matches strongly. Use time-of-day as signal. |
| Source-type handling | Artikel vs terminliste bias (#12) | Source-type-aware comparison weights. Core token extraction. |
| AI cost management | Under-using AI out of cost fear (#14) | Model actual cost. Define ambiguity zone with measured thresholds. |
| Enrichment | Stale canonical events (#15) | Re-synthesis on new source addition. |
| Seasonal robustness | Overfitting to Fasnet data (#17) | Category-agnostic rules. Ongoing monitoring. Diverse ground truth. |

---

## Sources

- Direct analysis of project event data files (bwb_11.02.2026, emt_11.02.2026, etc.) -- HIGH confidence for data-specific observations
- PROJECT.md project context and stated 65% current accuracy -- HIGH confidence
- Entity resolution and record linkage literature (training data, established field) -- MEDIUM confidence for general patterns
- Deduplication best practices from dedupe.io, academic record linkage research -- MEDIUM confidence (training data, not verified against current versions)

**Note:** WebSearch and WebFetch were unavailable during this research session. Findings are based on direct data analysis and established entity resolution principles. Confidence would increase with verification against current community discussions and library documentation.
