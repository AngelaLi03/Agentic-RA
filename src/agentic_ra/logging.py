import logging
import sys
from typing import cast

import structlog


def configure_logging(level: str = "INFO") -> None:
    """JSON structured logs to stdout. Bind `run_id` on the logger so every
    line in a research run is correlatable."""

    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(
            getattr(logging, level.upper(), logging.INFO)
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str = "agentic_ra") -> structlog.stdlib.BoundLogger:
    return cast(structlog.stdlib.BoundLogger, structlog.get_logger(name))


def bind_request(run_id: str, **extra: str) -> None:
    """Bind run/request identity into the structlog contextvar scope so
    every log line in the request — across modules and tasks — carries it
    without being threaded through call signatures (T-1.7)."""
    structlog.contextvars.bind_contextvars(run_id=run_id, **extra)


def clear_request() -> None:
    structlog.contextvars.clear_contextvars()
