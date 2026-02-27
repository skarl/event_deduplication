"""File processor for ingesting JSON event files with idempotency and transaction safety."""

import datetime as dt
import logging
import shutil
from dataclasses import dataclass, field
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker

from event_dedup.ingestion.json_loader import (
    EventData,
    compute_file_hash,
    extract_source_code,
    load_event_file,
)
from event_dedup.models.event_date import EventDate
from event_dedup.models.file_ingestion import FileIngestion
from event_dedup.models.source_event import SourceEvent
from event_dedup.preprocessing.blocking import generate_blocking_keys
from event_dedup.preprocessing.normalizer import load_city_aliases, normalize_city, normalize_text
from event_dedup.preprocessing.prefix_stripper import PrefixConfig, load_prefix_config, strip_prefixes

logger = logging.getLogger(__name__)


@dataclass
class FileProcessResult:
    status: str
    event_count: int = 0
    file_hash: str = ""
    reason: str = ""


def parse_time(time_str: str | None) -> dt.time | None:
    """Parse a time string in HH:MM or HH:MM:SS format.

    Args:
        time_str: Time string like "10:11" or "09:15:30", or None.

    Returns:
        Python time object, or None if input is None/empty.
    """
    if not time_str:
        return None
    parts = time_str.strip().split(":")
    if len(parts) == 2:
        return dt.time(int(parts[0]), int(parts[1]))
    elif len(parts) == 3:
        return dt.time(int(parts[0]), int(parts[1]), int(parts[2]))
    return None


def parse_date(date_str: str) -> dt.date:
    """Parse a date string in YYYY-MM-DD format.

    Args:
        date_str: Date string like "2026-02-12".

    Returns:
        Python date object.
    """
    return dt.date.fromisoformat(date_str)


def _build_source_event(event: EventData, source_code: str, file_ingestion_id: int) -> SourceEvent:
    """Build a SourceEvent model from parsed event data."""
    # Determine location fields
    location_name = None
    location_city = None
    location_district = None
    location_street = None
    location_street_no = None
    location_zipcode = None
    geo_latitude = None
    geo_longitude = None
    geo_confidence = None
    geo_country = None

    if event.location:
        location_name = event.location.name
        location_district = event.location.district
        location_street = event.location.street
        location_street_no = event.location.street_no
        location_zipcode = event.location.zipcode

        # CRITICAL: Use _sanitizeResult.city as authoritative city value
        if event.location.sanitize_result and event.location.sanitize_result.city:
            location_city = event.location.sanitize_result.city
        else:
            location_city = event.location.city

        # Geo fields
        if event.location.geo:
            geo_latitude = event.location.geo.latitude
            geo_longitude = event.location.geo.longitude
            geo_confidence = event.location.geo.confidence
            geo_country = event.location.geo.country

    return SourceEvent(
        id=event.id,
        file_ingestion_id=file_ingestion_id,
        title=event.title,
        short_description=event.short_description,
        description=event.description,
        highlights=event.highlights,
        location_name=location_name,
        location_city=location_city,
        location_district=location_district,
        location_street=location_street,
        location_street_no=location_street_no,
        location_zipcode=location_zipcode,
        geo_latitude=geo_latitude,
        geo_longitude=geo_longitude,
        geo_confidence=geo_confidence,
        geo_country=geo_country,
        source_type=event.source_type,
        source_code=source_code,
        categories=event.categories,
        is_family_event=event.is_family_event,
        is_child_focused=event.is_child_focused,
        admission_free=event.admission_free,
        registration_required=event.registration_required,
        registration_contact=event.registration_contact,
        confidence_score=event.confidence_score,
        batch_index=event.batch_index,
        extracted_at=event.extracted_at,
    )


def _build_event_dates(event: EventData, event_id: str) -> list[EventDate]:
    """Build EventDate models from parsed event data."""
    dates = []
    for date_entry in event.event_dates:
        dates.append(
            EventDate(
                event_id=event_id,
                date=parse_date(date_entry.date),
                start_time=parse_time(date_entry.start_time),
                end_time=parse_time(date_entry.end_time),
                end_date=parse_date(date_entry.end_date) if date_entry.end_date else None,
            )
        )
    return dates


class FileProcessor:
    """Process JSON event files with idempotency and transaction safety."""

    def __init__(
        self,
        session_factory: async_sessionmaker[AsyncSession],
        dead_letter_dir: Path,
        prefix_config_path: Path | None = None,
        city_aliases_path: Path | None = None,
    ) -> None:
        self.session_factory = session_factory
        self.dead_letter_dir = dead_letter_dir

        # Load preprocessing configs at init time (not per-file)
        config_dir = Path(__file__).resolve().parents[1] / "config"
        prefix_path = prefix_config_path or config_dir / "prefixes.yaml"
        aliases_path = city_aliases_path or config_dir / "city_aliases.yaml"

        self.prefix_config: PrefixConfig = load_prefix_config(prefix_path)
        self.city_aliases: dict[str, str] = load_city_aliases(aliases_path)

    async def process_file(self, file_path: Path) -> FileProcessResult:
        """Process a single JSON event file.

        1. Compute file hash for idempotency check.
        2. Skip if already processed.
        3. Parse JSON and create database records in a single transaction.
        4. On failure, move file to dead letter directory.

        Args:
            file_path: Path to the JSON event file.

        Returns:
            FileProcessResult with status, event count, and file hash.
        """
        file_hash = compute_file_hash(file_path)
        filename = file_path.name
        source_code = extract_source_code(filename)

        # Check idempotency: skip if file hash already exists
        async with self.session_factory() as session:
            result = await session.execute(select(FileIngestion).where(FileIngestion.file_hash == file_hash))
            existing = result.scalar_one_or_none()
            if existing is not None:
                return FileProcessResult(status="skipped", file_hash=file_hash, reason="already processed")

        try:
            # Parse JSON
            file_data = load_event_file(file_path)

            # Single transaction for all database writes
            async with self.session_factory() as session, session.begin():
                # Create FileIngestion record
                file_ingestion = FileIngestion(
                    filename=filename,
                    file_hash=file_hash,
                    source_code=source_code,
                    event_count=len(file_data.events),
                    status="completed",
                    file_metadata=file_data.metadata.model_dump() if file_data.metadata else None,
                )
                session.add(file_ingestion)
                await session.flush()  # Get the auto-generated id

                # Create SourceEvent and EventDate records
                all_models: list[SourceEvent | EventDate] = []
                for event in file_data.events:
                    source_event = _build_source_event(event, source_code, file_ingestion.id)

                    # Populate normalized fields
                    stripped_title = strip_prefixes(event.title, self.prefix_config)
                    source_event.title_normalized = normalize_text(stripped_title)
                    source_event.short_description_normalized = (
                        normalize_text(event.short_description) if event.short_description else None
                    )
                    source_event.location_name_normalized = (
                        normalize_text(source_event.location_name) if source_event.location_name else None
                    )
                    source_event.location_city_normalized = (
                        normalize_city(source_event.location_city, self.city_aliases)
                        if source_event.location_city
                        else None
                    )

                    # Generate blocking keys from event dates and location
                    dates_as_date = [parse_date(d.date) for d in event.event_dates]
                    source_event.blocking_keys = generate_blocking_keys(
                        dates=dates_as_date,
                        city_normalized=source_event.location_city_normalized,
                        lat=source_event.geo_latitude,
                        lon=source_event.geo_longitude,
                        geo_confidence=source_event.geo_confidence,
                    )

                    all_models.append(source_event)
                    all_models.extend(_build_event_dates(event, event.id))

                session.add_all(all_models)

            return FileProcessResult(
                status="completed",
                event_count=len(file_data.events),
                file_hash=file_hash,
            )

        except Exception as e:
            logger.error("Failed to process %s: %s", file_path, e)

            # Move to dead letter directory
            self.dead_letter_dir.mkdir(parents=True, exist_ok=True)
            dead_letter_path = self.dead_letter_dir / filename
            try:
                shutil.move(str(file_path), str(dead_letter_path))
            except Exception as move_err:
                logger.error("Failed to move %s to dead letter: %s", file_path, move_err)

            # Log failure in a separate transaction
            try:
                async with self.session_factory() as session, session.begin():
                    failed_ingestion = FileIngestion(
                        filename=filename,
                        file_hash=file_hash,
                        source_code=source_code,
                        event_count=0,
                        status="failed",
                        error_message=str(e),
                    )
                    session.add(failed_ingestion)
            except Exception as log_err:
                logger.error("Failed to log ingestion failure: %s", log_err)

            return FileProcessResult(
                status="failed",
                file_hash=file_hash,
                reason=str(e),
            )
