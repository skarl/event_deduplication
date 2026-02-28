# Event Deduplication Service

## What This Is

A Dockerized service that watches for incoming JSON files of events (extracted from PDF magazines via OCR/AI), deduplicates them against each other and against a PostgreSQL database, and maintains a canonical event database. Includes a frontend for browsing, searching, and manually reviewing event groupings. Events are extracted from regional newspapers/magazines and the same real-world event often appears across multiple sources with different titles, descriptions, and detail levels.

## Core Value

Accurate event deduplication -- the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.

## Current State (v0.1 shipped)

All v0.1 requirements delivered. The system is fully operational:

- **Pipeline**: File watcher ingests JSON, preprocesses (normalization, synonyms, blocking keys), matches via 4-signal scoring + graph clustering, synthesizes canonical events, persists to PostgreSQL
- **AI Matching**: Gemini Flash resolves ambiguous pairs with caching and cost tracking
- **Frontend**: React UI for browsing, searching, source comparison, split/merge review, audit trail, processing dashboard
- **Deployment**: Docker containers (worker, API, frontend, PostgreSQL) via docker-compose
- **Accuracy**: German dialect synonyms, category-aware weights, source-type-aware title comparison
- **Tests**: 371 tests passing, 39/39 requirements complete

## Requirements

### Validated (v0.1)

- [x] Multi-signal deduplication (date + location + title similarity + geo proximity)
- [x] Tiered matching: fast deterministic matching first, AI-assisted matching for ambiguous cases
- [x] Canonical event creation from grouped sources (best title, longest description, richest highlights, most precise location)
- [x] All original source events preserved and linked to their canonical event
- [x] Enrichment: when new sources arrive for an existing canonical event, update it with any better information
- [x] Direct PostgreSQL integration (read existing events, write canonical events + source links)
- [x] Docker container that watches a directory for new JSON files
- [x] Frontend: searchable event list showing canonical events with all fields
- [x] Frontend: drill-down from canonical event to its source events
- [x] Frontend: manual review UI to correct grouping decisions (split wrong groups, merge missed ones)

### Future (v2 candidates)

- Feedback loop: manual review decisions inform threshold tuning recommendations
- Duplicate cluster visualization (network graph)
- Incremental blocking key indexing for datasets >10K events/week

### Out of Scope

- Modifying the upstream PDF extraction pipeline -- we receive JSON as-is
- Real-time event streaming -- batch processing via file watch is sufficient
- User authentication for the frontend -- internal tool, no auth needed
- Mobile-optimized frontend -- desktop-first internal tool

## Context

**Data characteristics (from 20 sample files, 765 events):**
- Events come from ~10 regional PDF magazine sources (bwb, emt, rks, rkt, del, den, elt, elz, ets, rkb, rkm)
- Sources have overlapping geographic coverage -- the same event (e.g. "Primel-Aktion Emmendingen") appeared across 6 different source files
- Title variations range from identical (100% match) to substantially different wording (60-75% match) for the same event
- Location names vary between sources ("Marktplatz" vs "Marktplatz Waldkirch" vs "Marktplatz und Kirchstrasse")
- Times can differ slightly between sources (19:11 vs 19:30 for same event)
- Events have geo coordinates with confidence scores, categories, family/child flags, registration info
- Some false positive risk: different events at same venue and time (e.g. "Kinderball Waldkirch" vs "Kinderball Krakeelia")
- Volume: 2000+ events per week across all sources

## Constraints

- **Cost**: AI-assisted matching used sparingly -- only for ambiguous cases. Budget stays minimal per 1000 events.
- **Deployment**: Docker containers
- **Database**: PostgreSQL (existing, tool connects directly)
- **Input format**: JSON files matching the existing extraction pipeline output format
- **Performance**: Must handle 2000+ events/week without excessive processing time

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tiered matching (fast + AI) | Minimize AI costs while maximizing accuracy | Validated -- Gemini Flash resolves ambiguous pairs |
| Group, don't destroy | All source events preserved, canonical event synthesized from best fields | Validated -- field provenance tracks contributions |
| Docker + directory watch | Fits existing pipeline, decoupled architecture | Validated -- watchfiles + docker-compose |
| Direct PG connection | Simpler than export/import cycles, enables enrichment | Validated -- asyncpg for async operations |
| Frontend included | Need visibility into events and manual review capability | Validated -- React + TanStack Query |
| Auto-generated ground truth | Manual labeling too slow for automation-focused project | Validated -- 1181 pairs via conservative heuristics |
| Synonym normalization at ingestion time | O(events) vs O(pairs), stored in title_normalized | Validated -- +0.04 to +0.22 score improvement |

---
*Last updated: 2026-02-28 after v0.1 milestone completion*
