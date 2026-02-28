# Requirements: Event Deduplication Service v0.2

**Milestone:** v0.2 — Configuration, AI Verification, UX & Export
**Created:** 2026-02-28
**Status:** Draft

## Summary

v0.2 adds a dynamic configuration system (frontend-editable, immediate effect), verifies and surfaces AI matching, improves frontend UX (filter chips, sorting, page sizing), adds a time-gap penalty for false positives, and provides a canonical event export function.

---

## CFG — Dynamic Configuration System

- [x] **CFG-01**: Store all matching configuration in the database with a REST API for reading and updating values. Config changes take effect on the next pipeline run without restart.
- [ ] **CFG-02**: Frontend configuration page where operators can view and edit all matching parameters (thresholds, weights, time tolerances, geo settings, cluster limits).
- [x] **CFG-03**: Gemini API key stored securely in the config — write-only field in the frontend (value is masked/hidden after saving, never returned in GET responses).
- [x] **CFG-04**: AI matching on/off toggle in the config, visible and editable from the frontend config page.
- [x] **CFG-05**: Config values that were previously hardcoded in YAML or Python defaults are now editable: scoring weights, match thresholds, date time tolerances/factors, geo max distance, title blend parameters, cluster limits, AI model/temperature/confidence threshold.

## AIM — AI Matching Verification & Indicators

- [ ] **AIM-01**: End-to-end verification that AI matching works correctly — integration test that processes ambiguous pairs through Gemini and validates the response flow (cache, cost tracking, decision application).
- [ ] **AIM-02**: AI involvement indicator persisted on canonical events — a boolean/flag field (`ai_assisted`) on `CanonicalEvent` that is `true` when any source pair in its cluster was resolved by AI.
- [ ] **AIM-03**: AI indicator displayed in the frontend event list as a visible badge/icon, and in the event detail page showing which specific pairs were AI-resolved.
- [ ] **AIM-04**: MatchDecision `tier` field values `"ai"` and `"ai_low_confidence"` are visually distinguished in the ConfidenceIndicator component.

## TGP — Time Gap Penalty

- [ ] **TGP-01**: Events on the same date but 2+ hours apart receive a steeper time penalty (far_factor reduced from 0.3 to ~0.15), making false-positive matches of sequential events at the same location significantly less likely.
- [ ] **TGP-02**: Time gap penalty parameters (threshold hours, penalty factor) are configurable via the dynamic config system (CFG).

## UIX — Frontend UX Improvements

- [ ] **UIX-01**: Category filter as chip/tag selector — dropdown or autocomplete populated from existing categories in the database, selected categories appear as removable chips with an "x" button.
- [ ] **UIX-02**: City filter as chip/tag selector — same behavior as categories: autocomplete from existing cities, removable chips with "x" button.
- [ ] **UIX-03**: Column sorting on all columns in the canonical event list (title, city, first date, categories, source count, confidence, review status). Clicking a column header toggles ascending/descending sort.
- [ ] **UIX-04**: Configurable rows per page with options: 25, 50, 100, 200, ALL. Selector visible in the event list pagination area.

## EXP — Export Function

- [x] **EXP-01**: API endpoint to export canonical events as JSON in the same structure as the input format (`{"events": [...], "metadata": {...}}`). Each event object mirrors the input event schema (title, description, dates, location with geo, categories, flags).
- [x] **EXP-02**: Export date filter — optional `created_after` and/or `modified_after` datetime parameters. If both empty, export the full database. If set (e.g., "2026-02-28 16:00"), only events created/modified at or after that timestamp are included.
- [x] **EXP-03**: Export output split into files of max 200 events each, with clear naming: `export_{timestamp}_{part_N}.json` (e.g., `export_2026-02-28T16-00_part_1.json`).
- [ ] **EXP-04**: Frontend export UI — page or dialog where operators select the date filter and trigger export. Download as ZIP if multiple files, or single JSON if ≤200 events.
- [ ] **EXP-05**: CLI export command (`uv run python -m event_dedup.cli export`) with the same date filter options (`--created-after`, `--modified-after`) and file splitting behavior. Writes output files to a specified directory (`--output-dir`, defaults to `./export/`).

---

## Requirement Count

| Category | Count |
|----------|-------|
| CFG (Configuration) | 5 |
| AIM (AI Matching) | 4 |
| TGP (Time Gap Penalty) | 2 |
| UIX (Frontend UX) | 4 |
| EXP (Export) | 5 |
| **Total** | **20** |
