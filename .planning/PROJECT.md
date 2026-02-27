# Event Deduplication Service

## What This Is

A Dockerized service that watches for incoming JSON files of events (extracted from PDF magazines via OCR/AI), deduplicates them against each other and against a PostgreSQL database, and maintains a canonical event database. Includes a frontend for browsing, searching, and manually reviewing event groupings. Events are extracted from regional newspapers/magazines and the same real-world event often appears across multiple sources with different titles, descriptions, and detail levels.

## Core Value

Accurate event deduplication — the same real-world event appearing across multiple source PDFs must be reliably grouped, with the best information from all sources combined into a single canonical event.

## Requirements

### Validated

(None yet — ship to validate)

### Active

- [ ] Multi-signal deduplication (date + location + title similarity + geo proximity)
- [ ] Tiered matching: fast deterministic matching first, AI-assisted matching for ambiguous cases
- [ ] Canonical event creation from grouped sources (best title, longest description, richest highlights, most precise location)
- [ ] All original source events preserved and linked to their canonical event
- [ ] Enrichment: when new sources arrive for an existing canonical event, update it with any better information
- [ ] Direct PostgreSQL integration (read existing events, write canonical events + source links)
- [ ] Docker container that watches a directory for new JSON files
- [ ] Frontend: searchable event list showing canonical events with all fields
- [ ] Frontend: drill-down from canonical event to its source events
- [ ] Frontend: manual review UI to correct grouping decisions (split wrong groups, merge missed ones)

### Out of Scope

- Modifying the upstream PDF extraction pipeline — we receive JSON as-is
- Real-time event streaming — batch processing via file watch is sufficient
- User authentication for the frontend — internal tool, no auth needed
- Mobile-optimized frontend — desktop-first internal tool

## Context

**Data characteristics (from 20 sample files, 765 events):**
- Events come from ~10 regional PDF magazine sources (bwb, emt, rks, rkt, del, den, elt, elz, ets, rkb, rkm)
- Sources have overlapping geographic coverage — the same event (e.g. "Primel-Aktion Emmendingen") appeared across 6 different source files
- Title variations range from identical (100% match) to substantially different wording (60-75% match) for the same event
- Location names vary between sources ("Marktplatz" vs "Marktplatz Waldkirch" vs "Marktplatz und Kirchstra\u00dfe")
- Times can differ slightly between sources (19:11 vs 19:30 for same event)
- Events have geo coordinates with confidence scores, categories, family/child flags, registration info
- Some false positive risk: different events at same venue and time (e.g. "Kinderball Waldkirch" vs "Kinderball Krakeelia")
- Volume: 2000+ events per week across all sources

**Current approach:**
- Export DB before each file import, match on location + time + title similarity
- ~65% accuracy — too many missed duplicates and some false merges

**Event data fields:**
- title, short_description, description, highlights
- event_dates (date, start_time, end_time)
- location (name, city, district, street, street_no, zipcode, geo coordinates with confidence)
- source_type, categories, is_family_event, is_child_focused
- admission_free, registration_required, registration_contact
- confidence_score, batch metadata, unique id

## Constraints

- **Cost**: AI-assisted matching should be used sparingly — only for ambiguous cases that fast matching can't resolve. Budget should stay minimal per 1000 events.
- **Deployment**: Must run as Docker container(s)
- **Database**: PostgreSQL (existing, tool connects directly)
- **Input format**: JSON files matching the existing extraction pipeline output format
- **Performance**: Must handle 2000+ events/week without excessive processing time

## Key Decisions

| Decision | Rationale | Outcome |
|----------|-----------|---------|
| Tiered matching (fast + AI) | Minimize AI costs while maximizing accuracy | — Pending |
| Group, don't destroy | All source events preserved, canonical event synthesized from best fields | — Pending |
| Docker + directory watch | Fits existing pipeline, decoupled architecture | — Pending |
| Direct PG connection | Simpler than export/import cycles, enables enrichment | — Pending |
| Frontend included | Need visibility into events and manual review capability | — Pending |

---
*Last updated: 2026-02-27 after initialization*
