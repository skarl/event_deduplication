---
title: Investigate why near-identical events show only 80% match in review
area: matching
priority: high
status: open
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

## Context

Docker is running — can query the API or database directly to inspect scoring details.
