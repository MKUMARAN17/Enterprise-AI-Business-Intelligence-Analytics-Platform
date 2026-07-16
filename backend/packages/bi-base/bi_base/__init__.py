"""bi-base — the Enterprise BI platform foundation layer.

Everything below the app depends on this and nothing else in the platform. It
provides four things and no domain logic:

    from bi_base import get_logger, configure_logging   # structured logging
    from bi_base import bind_request, get_request_id     # correlation context
    from bi_base import extract_json, require_keys        # LLM structured output
    from bi_base import BiError, SqlSafetyError, ...      # error hierarchy

Kept deliberately small and framework-free (only structlog) so it can be imported
and unit-tested without the web stack, mirroring the reference platform's
vendored-foundation split.
"""
from __future__ import annotations

from bi_base.context import (
    bind_request,
    clear,
    get_request_id,
    get_user_id,
    new_request_id,
)
from bi_base.errors import (
    AgentError,
    AuthError,
    AuthorizationError,
    BiError,
    ConfigError,
    GuardrailError,
    ProblemDetail,
    QueryExecutionError,
    SqlSafetyError,
)
from bi_base.logging import configure_logging, get_logger
from bi_base.structured import (
    StructuredOutputError,
    extract_json,
    require_keys,
)
from bi_base.timing import Elapsed, stopwatch

__version__ = "0.1.0"

__all__ = [
    # logging
    "configure_logging",
    "get_logger",
    # context
    "bind_request",
    "get_request_id",
    "get_user_id",
    "new_request_id",
    "clear",
    # structured output
    "extract_json",
    "require_keys",
    "StructuredOutputError",
    # timing
    "stopwatch",
    "Elapsed",
    # errors
    "BiError",
    "ConfigError",
    "AuthError",
    "AuthorizationError",
    "GuardrailError",
    "SqlSafetyError",
    "QueryExecutionError",
    "AgentError",
    "ProblemDetail",
    "__version__",
]
