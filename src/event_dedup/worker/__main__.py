"""Pipeline worker entry point: python -m event_dedup.worker"""

import asyncio
import signal

import structlog

from event_dedup.config.settings import get_settings
from event_dedup.db.session import get_session_factory
from event_dedup.ingestion.file_processor import FileProcessor
from event_dedup.logging_config import configure_logging
from event_dedup.matching.config import load_matching_config
from event_dedup.worker.orchestrator import process_existing_files
from event_dedup.worker.watcher import watch_and_process


async def main() -> None:
    settings = get_settings()
    configure_logging(json_output=settings.log_json, log_level=settings.log_level)
    log = structlog.get_logger()

    session_factory = get_session_factory()
    matching_config = load_matching_config(settings.matching_config_path)

    # Override AI config from environment
    if settings.gemini_api_key:
        matching_config.ai.enabled = True
        matching_config.ai.api_key = settings.gemini_api_key

    file_processor = FileProcessor(
        session_factory=session_factory,
        dead_letter_dir=settings.dead_letter_dir,
    )

    data_dir = settings.event_data_dir
    data_dir.mkdir(parents=True, exist_ok=True)

    log.info(
        "worker_starting",
        watch_dir=str(data_dir),
        database=settings.database_url.split("@")[-1],
    )

    # Graceful shutdown via SIGTERM/SIGINT
    stop_event = asyncio.Event()
    loop = asyncio.get_running_loop()
    for sig in (signal.SIGTERM, signal.SIGINT):
        loop.add_signal_handler(sig, stop_event.set)

    # Process existing unprocessed files on startup
    processed = await process_existing_files(
        data_dir, file_processor, session_factory, matching_config
    )
    log.info("startup_complete", existing_files_processed=processed)

    # Watch for new files
    await watch_and_process(
        data_dir, file_processor, session_factory, matching_config, stop_event=stop_event
    )
    log.info("worker_shutdown")


if __name__ == "__main__":
    asyncio.run(main())
