"""Structured logging setup.

One ``configure_logging`` call at boot wires structlog to emit JSON (prod) or a
colourised console renderer (dev), and injects the request-context ids into every
event. Modules obtain a logger with ``get_logger(__name__)`` and log with
key/value pairs (``log.info("sql.executed", rows=n, ms=elapsed)``) — never
f-string prose — so logs are queryable in the observability stack (LangSmith /
CloudWatch).
"""
from __future__ import annotations

import logging
import sys

import structlog

from bi_base.context import get_request_id, get_user_id


def _inject_context(_logger, _method, event_dict):
    rid = get_request_id()
    if rid:
        event_dict.setdefault("request_id", rid)
    uid = get_user_id()
    if uid:
        event_dict.setdefault("user_id", uid)
    return event_dict


def configure_logging(*, level: str = "INFO", json_logs: bool = True) -> None:
    """Configure structlog + stdlib logging once, at process boot."""
    logging.basicConfig(format="%(message)s", stream=sys.stdout, level=level.upper())

    processors: list = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        _inject_context,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]
    processors.append(
        structlog.processors.JSONRenderer()
        if json_logs
        else structlog.dev.ConsoleRenderer()
    )

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.getLevelName(level.upper())
        ),
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger (configure_logging must have run)."""
    return structlog.get_logger(name)
