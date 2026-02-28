"""Pydantic response schemas for the Event Deduplication API."""

from __future__ import annotations

import datetime as dt
from typing import Annotated, Generic, TypeVar

from pydantic import BaseModel, BeforeValidator, ConfigDict


def _coerce_to_str(v: object) -> str | None:
    """Coerce date/time objects to ISO string for schema output."""
    if v is None:
        return None
    if isinstance(v, (dt.date, dt.time)):
        return v.isoformat()
    return str(v)


DateStr = Annotated[str, BeforeValidator(_coerce_to_str)]
OptDateStr = Annotated[str | None, BeforeValidator(_coerce_to_str)]

T = TypeVar("T")


class EventDateSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    date: DateStr
    start_time: OptDateStr = None
    end_time: OptDateStr = None
    end_date: OptDateStr = None


class SourceEventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    source_type: str
    source_code: str
    location_city: str | None = None


class SourceEventDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    title: str
    short_description: str | None = None
    description: str | None = None
    highlights: list | None = None
    location_name: str | None = None
    location_city: str | None = None
    location_district: str | None = None
    location_street: str | None = None
    location_street_no: str | None = None
    location_zipcode: str | None = None
    geo_latitude: float | None = None
    geo_longitude: float | None = None
    geo_confidence: float | None = None
    source_type: str
    source_code: str
    categories: list | None = None
    is_family_event: bool | None = None
    is_child_focused: bool | None = None
    admission_free: bool | None = None
    dates: list[EventDateSchema] = []


class MatchDecisionSchema(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_event_id_a: str
    source_event_id_b: str
    combined_score: float
    date_score: float
    geo_score: float
    title_score: float
    description_score: float
    decision: str
    tier: str


class CanonicalEventSummary(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    location_city: str | None = None
    dates: list | None = None
    categories: list | None = None
    source_count: int
    match_confidence: float | None = None
    needs_review: bool


class CanonicalEventDetail(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    title: str
    short_description: str | None = None
    description: str | None = None
    highlights: list | None = None
    location_name: str | None = None
    location_city: str | None = None
    location_district: str | None = None
    location_street: str | None = None
    location_zipcode: str | None = None
    geo_latitude: float | None = None
    geo_longitude: float | None = None
    geo_confidence: float | None = None
    dates: list | None = None
    categories: list | None = None
    is_family_event: bool | None = None
    is_child_focused: bool | None = None
    admission_free: bool | None = None
    field_provenance: dict | None = None
    source_count: int
    match_confidence: float | None = None
    needs_review: bool
    first_date: OptDateStr = None
    last_date: OptDateStr = None
    sources: list[SourceEventDetail] = []
    match_decisions: list[MatchDecisionSchema] = []


class PaginatedResponse(BaseModel, Generic[T]):
    items: list[T]
    total: int
    page: int
    size: int
    pages: int


# --- Review operation schemas ---


class SplitRequest(BaseModel):
    canonical_event_id: int
    source_event_id: str
    target_canonical_id: int | None = None  # None = create new canonical
    operator: str = "anonymous"


class MergeRequest(BaseModel):
    source_canonical_id: int  # donor -- gets deleted
    target_canonical_id: int  # survivor -- keeps all sources
    operator: str = "anonymous"


class SplitResponse(BaseModel):
    original_canonical_id: int
    new_canonical_id: int | None = None  # if new canonical was created
    target_canonical_id: int | None = None  # if assigned to existing
    original_deleted: bool = False


class MergeResponse(BaseModel):
    surviving_canonical_id: int
    deleted_canonical_id: int
    new_source_count: int


class DismissRequest(BaseModel):
    operator: str = "anonymous"
    reason: str | None = None


class AuditLogEntry(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    action_type: str
    canonical_event_id: int | None
    source_event_id: str | None
    operator: str
    details: dict | None
    created_at: str  # ISO string


# --- Dashboard schemas ---


class FileProcessingStats(BaseModel):
    total_files: int
    total_events: int
    completed: int
    errors: int


class MatchDistribution(BaseModel):
    match: int = 0
    no_match: int = 0
    ambiguous: int = 0


class CanonicalStats(BaseModel):
    total: int
    needs_review: int
    avg_confidence: float | None


class DashboardStats(BaseModel):
    files: FileProcessingStats
    matches: MatchDistribution
    canonicals: CanonicalStats


class ProcessingHistoryEntry(BaseModel):
    date: str
    files_processed: int
    events_ingested: int
    errors: int
