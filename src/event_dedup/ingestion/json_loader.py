"""JSON file loader and validator for event data files."""

import hashlib
import json
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field


class GeoData(BaseModel):
    longitude: float | None = None
    latitude: float | None = None
    confidence: float | None = None
    country: str | None = None


class SanitizeResult(BaseModel):
    city: str | None = None
    district: str | None = None
    confidence: float | None = None
    # Allow extra fields (matchType, requiresReview)
    model_config = ConfigDict(extra="allow")


class LocationData(BaseModel):
    name: str | None = None
    city: str | None = None
    district: str | None = None
    street: str | None = None
    street_no: str | None = None
    zipcode: str | None = None
    sanitize_result: SanitizeResult | None = Field(None, alias="_sanitizeResult")
    geo: GeoData | None = None
    # Allow extra fields (_sanitized)
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class EventDateData(BaseModel):
    date: str
    start_time: str | None = None
    end_time: str | None = None
    end_date: str | None = None


class EventData(BaseModel):
    id: str
    title: str
    short_description: str | None = None
    description: str | None = None
    highlights: list[str] | None = None
    event_dates: list[EventDateData] = []
    location: LocationData | None = None
    source_type: str
    categories: list[str] | None = None
    is_family_event: bool | None = None
    is_child_focused: bool | None = None
    admission_free: bool | None = None
    registration_required: bool | None = None
    registration_contact: str | None = None
    confidence_score: float | None = None
    batch_index: int | None = Field(None, alias="_batch_index")
    extracted_at: str | None = Field(None, alias="_extracted_at")
    # Allow extra fields we explicitly ignore (_event_index, _sanitized, etc.)
    model_config = ConfigDict(extra="allow", populate_by_name=True)


class FileMetadata(BaseModel):
    processedAt: str | None = None
    sourceKey: str | None = None
    # Allow all other metadata fields
    model_config = ConfigDict(extra="allow")


class EventFileData(BaseModel):
    events: list[EventData]
    rejected: list = []
    metadata: FileMetadata | None = None


def load_event_file(file_path: Path) -> EventFileData:
    """Read and validate a JSON event file.

    Args:
        file_path: Path to the JSON event file.

    Returns:
        Validated EventFileData instance.

    Raises:
        ValueError: If the file contains invalid JSON or fails validation.
    """
    try:
        with open(file_path, encoding="utf-8") as f:
            raw_data = json.load(f)
    except json.JSONDecodeError as e:
        raise ValueError(f"Invalid JSON in {file_path}: {e}") from e

    try:
        return EventFileData.model_validate(raw_data)
    except Exception as e:
        raise ValueError(f"Validation error for {file_path}: {e}") from e


def compute_file_hash(file_path: Path) -> str:
    """Compute SHA-256 hash of a file in 64KB chunks.

    Args:
        file_path: Path to the file.

    Returns:
        Hex digest string (64 characters).
    """
    sha256 = hashlib.sha256()
    with open(file_path, "rb") as f:
        while chunk := f.read(65536):  # 64KB chunks
            sha256.update(chunk)
    return sha256.hexdigest()


def extract_source_code(filename: str) -> str:
    """Extract source code from filename.

    Pattern: everything before the first underscore.
    Example: 'bwb_11.02.2026_2026-02-11T20-46-41-776Z.json' -> 'bwb'

    Args:
        filename: The filename (not full path).

    Returns:
        Source code string.
    """
    return filename.split("_")[0]
