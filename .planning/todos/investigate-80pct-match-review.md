---
title: Investigate why near-identical events show only 80% match in review
area: matching
priority: high
status: resolved
created: 2026-02-28
---

# Investigate 80% Match for Near-Identical Events

## Problem

Two events that appear to be the same real-world event are showing only ~80% match and landing in the review tab instead of being auto-merged.

## Event Details

**Event A** (source: `pdf-9a2c5acd-2-2`, city: Elt):
- Title: Grünen-Gespräch zur Landtagswahl
- Description: Gesprächsveranstaltung mit Landtagskandidat Rüdiger Tonojan von Bündnis 90 / Die Grünen.
- Location: Pferdestall, alter Gutshof, Gutach im Breisgau (Gutach)
- Date: 26.02.2026 19:00:00
- Category: versammlung

**Event B** (source: `pdf-da34be0e-1-2`, city: Elz):
- Title: Grünen-Gespräch zur Landtagswahl
- Description: Gesprächsveranstaltung mit Landtagskandidat Rüdiger Tonojan von Bündnis 90 / Die Grünen
- Location: Pferdestall, alter Gutshof, Gutach im Breisgau (Gutach)
- Date: 26.02.2026 19:00:00
- Category: versammlung

## Observable Differences

- Source city: "elt" vs "elz" (different source PDFs / Terminliste origin)
- Description: trailing period present in A, absent in B
- Otherwise identical: same title, location, date, category

## Investigation Steps

1. Check which scorer(s) are producing the penalty — the city field difference ("elt" vs "elz") likely reduces the score
2. Determine if source city vs event location city is being compared (Gutach im Breisgau is the actual venue for both)
3. Review if the trailing period in description affects text similarity score
4. Check current auto-merge threshold vs the 80% score
5. Consider whether source PDF city should even factor into matching (the venue location is what matters)

## Resolution (2026-02-28)

**Root cause:** Two neutral 0.5 scores were dragging the combined score to 0.80:

1. **Geo scorer (0.5 → 1.0):** Both events had identical coordinates (48.117019, 7.986537) but `geo_confidence=0.7422 < min_confidence=0.85`. The confidence gate returned neutral 0.5 even though identical coordinates prove the location is the same. **Fix:** Skip confidence gate when coordinates are identical (within 1e-6 epsilon).

2. **Description scorer (0.5 → 0.99):** The scorer only used `event.get("description")` which was empty for both terminliste events. The actual text was in `short_description`. **Fix:** Fall back to `short_description` when `description` is empty.

**Note:** City field ("elt" vs "elz") was NOT the culprit — city is only used for blocking, not scoring.

**Result:** Combined score improved from 0.80 to 0.9991, well above the 0.75 auto-merge threshold.
