---
title: Prevent false merging of different movies at the same cinema
area: matching
priority: high
status: resolved
created: 2026-02-28
---

# Prevent False Merging of Different Movies at Same Cinema

## Problem

Different movies showing at the same cinema are being merged into a single canonical event. The matcher over-weights venue/location similarity and date overlap, causing distinct films to be treated as duplicates.

## Example: 4 Events Merged Into 1 (Should Be 3 Groups)

All four events share the same venue (Scala Haslach/Scala Kino, Neue Eisenbahnstraße 8) and similar date ranges (Feb 20-22, 2026), but they are **three different movies**:

### Movie 1: G.O.A.T. - Bock auf große Sprünge (2 events → should merge)

**Event A** (source: `...a2c5acd-12-3`, city: elt):
- Title: G.O.A.T. - Bock auf große Sprünge
- Description: Kinderfilm im Scala Haslach
- Location: Scala Haslach, Neue Eisenbahnstraße 8, Haslach im Kinzigtal
- Dates: 20.02 15:15, 21.02 15:15, 22.02 14:15
- Category: kinder

**Event B** (source: `...a34be0e-11-3`, city: elz):
- Title: G.O.A.T. - BOCK AUF GROSSE SPRÜNGE
- Description: Kinderfilm G.O.A.T. - BOCK AUF GROSSE SPRÜNGE im Scala Kino Haslach
- Location: Scala Kino, Neue Eisenbahnstraße 8, Haslach im Kinzigtal
- Dates: 20.02 15:15, 21.02 15:15, 22.02 14:15
- Category: kinder, buehne

→ **These two ARE the same event** (identical title, times, venue). Should merge.

### Movie 2: Woodwalkers 2 (1 event → should stay separate)

**Event C** (source: `...a2c5acd-12-4`, city: elt):
- Title: Woodwalkers 2
- Description: Kinderfilm im Scala Haslach
- Location: Scala Haslach, Neue Eisenbahnstraße 8, Haslach im Kinzigtal
- Dates: 20.02 15:00, 21.02 15:00, 22.02 14:00
- Category: kinder

→ **Different movie**, should NOT merge with G.O.A.T. or Checker Tobi.

### Movie 3: Checker Tobi und die heimliche Herrscherin der Erde (1 event → should stay separate)

**Event D** (source: `...a2c5acd-12-5`, city: elt):
- Title: Checker Tobi und die heimliche Herrscherin der Erde
- Description: Kinderfilm im Scala Haslach
- Location: Scala Haslach, Neue Eisenbahnstraße 8, Haslach im Kinzigtal
- Dates: 20.02 15:30, 21.02 15:30, 22.02 14:00
- Category: kinder

→ **Different movie**, should NOT merge with G.O.A.T. or Woodwalkers 2.

## Why They Match Incorrectly

The current scoring likely produces high similarity because:
1. **Location:** Identical venue and address → high geo/venue score
2. **Dates:** Nearly identical date ranges (same days, times within 15-30min) → high time score
3. **Category:** All "kinder" → category match
4. **Description:** All share "Kinderfilm im Scala Haslach" → high description similarity
5. **Title:** The only distinguishing factor, but it may not carry enough weight to prevent merging

## Key Insight

For cinema/theater/concert venues, the **title is the primary differentiator**. Multiple events can share everything (venue, dates, category, description template) except the title. The title scorer needs to be strong enough to prevent merging when titles clearly differ.

## Resolution (2026-02-28)

**Root cause:** When date (1.0), geo (1.0), and description (1.0) all score perfectly — as happens for different movies at the same cinema with template descriptions like "Kinderfilm im Scala Haslach" — even a title score of 0.22 produces a combined score of 0.765, just above the 0.75 auto-merge threshold. The weighted average has no mechanism to prevent a match when one signal strongly disagrees.

**Fix: Title veto threshold** (`thresholds.title_veto: 0.30`)

Added a configurable title veto to the `decide()` function. When the title score falls below the veto threshold, the decision is capped at "ambiguous" regardless of the combined score. This prevents auto-merge while still allowing human review.

**Verified results:**
- G.O.A.T.(elt) vs Woodwalkers: title=0.22 < 0.30 → VETOED to ambiguous (was match)
- G.O.A.T.(elt) vs Checker Tobi: title=0.24 < 0.30 → VETOED to ambiguous (was match)
- G.O.A.T.(elt) vs G.O.A.T.(elz): title=0.45 > 0.30 → match (correct, same movie)

**Files changed:**
- `src/event_dedup/matching/config.py` — Added `title_veto` to ThresholdConfig
- `src/event_dedup/matching/combiner.py` — Updated `decide()` with veto logic
- `src/event_dedup/matching/pipeline.py` — Pass title_score to decide()
- `config/matching.yaml` — Added `title_veto: 0.30`
- `tests/test_combiner.py` — 8 new tests for veto behavior
