"""Matching signal scorers -- pure functions operating on event dicts."""

from event_dedup.matching.scorers.date_scorer import date_score
from event_dedup.matching.scorers.desc_scorer import description_score
from event_dedup.matching.scorers.geo_scorer import geo_score
from event_dedup.matching.scorers.title_scorer import title_score

__all__ = ["date_score", "description_score", "geo_score", "title_score"]
