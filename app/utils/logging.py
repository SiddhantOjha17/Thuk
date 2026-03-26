"""Structured logging utility."""

import logging
import sys
from typing import Any

import structlog

from app.config import get_settings


def setup_logging(debug: bool = False) -> None:
    """Initialize structured logging config.
    
    Call this once at application startup.
    """
    if debug:
        # Human-readable output for local development
        renderer = structlog.dev.ConsoleRenderer()
    else:
        # JSON output for production (e.g., Fly.io / Render logs)
        renderer = structlog.processors.JSONRenderer()

    structlog.configure(
        processors=[
            structlog.stdlib.add_log_level,
            structlog.stdlib.add_logger_name,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            renderer,
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    log_level = logging.DEBUG if debug else logging.INFO
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )


def get_logger(name: str | None = None) -> structlog.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)
