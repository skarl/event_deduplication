"""CLI entry point: python -m event_dedup.cli export"""

import argparse
import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

import structlog

from event_dedup.config.settings import get_settings
from event_dedup.db.session import get_session_factory
from event_dedup.export.service import chunk_events, query_and_export
from event_dedup.logging_config import configure_logging


async def run_export(
    created_after: datetime | None,
    modified_after: datetime | None,
    output_dir: Path,
) -> None:
    """Execute the export and write files to output_dir."""
    log = structlog.get_logger()
    session_factory = get_session_factory()

    async with session_factory() as session:
        events = await query_and_export(session, created_after, modified_after)

    log.info("export_queried", event_count=len(events))

    filters = {
        "created_after": created_after.isoformat() if created_after else None,
        "modified_after": modified_after.isoformat() if modified_after else None,
    }
    chunks = chunk_events(events, filters=filters)

    output_dir.mkdir(parents=True, exist_ok=True)
    for filename, content in chunks:
        filepath = output_dir / filename
        filepath.write_text(content, encoding="utf-8")
        log.info(
            "export_file_written",
            path=str(filepath),
            events=json.loads(content)["metadata"]["eventCount"],
        )

    log.info("export_complete", files=len(chunks), directory=str(output_dir))


def main() -> None:
    parser = argparse.ArgumentParser(
        prog="event_dedup.cli",
        description="Event Deduplication CLI",
    )
    subparsers = parser.add_subparsers(dest="command")

    export_parser = subparsers.add_parser("export", help="Export canonical events as JSON")
    export_parser.add_argument(
        "--created-after",
        type=str,
        default=None,
        help="ISO datetime filter for created_at (e.g., 2026-02-28T16:00)",
    )
    export_parser.add_argument(
        "--modified-after",
        type=str,
        default=None,
        help="ISO datetime filter for updated_at (e.g., 2026-02-28T16:00)",
    )
    export_parser.add_argument(
        "--output-dir",
        type=str,
        default="./export",
        help="Output directory (default: ./export)",
    )

    args = parser.parse_args()

    if args.command is None:
        parser.print_help()
        sys.exit(1)

    if args.command == "export":
        settings = get_settings()
        configure_logging(json_output=settings.log_json, log_level=settings.log_level)

        created_after = datetime.fromisoformat(args.created_after) if args.created_after else None
        modified_after = datetime.fromisoformat(args.modified_after) if args.modified_after else None
        output_dir = Path(args.output_dir)

        asyncio.run(run_export(created_after, modified_after, output_dir))


if __name__ == "__main__":
    main()
