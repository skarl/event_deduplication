"""Unified structlog + stdlib JSON logging configuration.

Ensures BOTH ``structlog.get_logger()`` and existing
``logging.getLogger(__name__)`` calls produce uniform output -- either
JSON (production) or colored console (development).
"""

import logging
import sys

import structlog


def configure_logging(json_output: bool = True, log_level: str = "INFO") -> None:
    """Configure unified logging for both structlog and stdlib.

    Args:
        json_output: If ``True``, render logs as JSON lines. If ``False``,
            use structlog's coloured console renderer for development.
        log_level: Root log level (``"DEBUG"``, ``"INFO"``, ``"WARNING"``, etc.).
    """
    shared_processors: list[structlog.types.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if json_output:
        renderer: structlog.types.Processor = structlog.processors.JSONRenderer()
    else:
        renderer = structlog.dev.ConsoleRenderer()

    # Configure structlog
    structlog.configure(
        processors=shared_processors
        + [
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    # Configure stdlib root logger to use structlog's ProcessorFormatter
    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            renderer,
        ],
    )

    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(handler)
    root.setLevel(getattr(logging, log_level.upper()))
