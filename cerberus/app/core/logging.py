"""
Logging Configuration

Structured logging setup using structlog.
"""

import logging
import sys
from typing import Any

import structlog
from structlog.typing import Processor

from app.config.settings import settings


def setup_logging() -> None:
    """Configure structured logging for the application."""
    # Determine if we're in development mode (local or development)
    is_dev = settings.APP_ENV in ("development", "local")

    # Shared processors for structlog (run before final rendering)
    # Note: Using PrintLoggerFactory so we don't use add_logger_name (requires stdlib logger)
    shared_processors: list[Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.PositionalArgumentsFormatter(),
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if is_dev:
        # Development: colored console output
        final_processors: list[Processor] = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]
    else:
        # Production: JSON output
        final_processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]

    # Configure structlog with PrintLoggerFactory for direct stdout output
    # This ensures logs appear in Docker without additional logging configuration
    structlog.configure(
        processors=final_processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Also configure standard logging to capture SQLAlchemy and other library logs
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, settings.LOG_LEVEL.upper()),
        force=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance.

    Args:
        name: Logger name, defaults to module name

    Returns:
        Configured structlog logger
    """
    return structlog.get_logger(name)


def log_context(**kwargs: Any) -> None:
    """Add context variables to all subsequent log calls.

    Args:
        **kwargs: Key-value pairs to add to log context
    """
    structlog.contextvars.bind_contextvars(**kwargs)


def clear_log_context() -> None:
    """Clear all context variables."""
    structlog.contextvars.clear_contextvars()


# Initialize logging on module import
setup_logging()

# Default logger instance
logger = get_logger("cerberus")
