"""Structured JSON logging for Adhera services, built on structlog.

Every log line is a single JSON object carrying at least ``timestamp``,
``level``, ``service``, ``event`` and — when bound by the correlation
middleware — ``correlation_id``. The :func:`mask_sensitive` processor
redacts credentials and medication free-text fields before anything is
rendered, so sensitive values can never leak into log output.
"""

from __future__ import annotations

import logging
import sys
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from shared.config import BaseServiceSettings

REDACTED = "[REDACTED]"

# Substring matches (case-insensitive): catches password/password_hash,
# token/access_token/refresh_token, authorization headers, and secrets.
_SENSITIVE_SUBSTRINGS = ("password", "token", "authorization", "secret")
# Exact matches: medication free-text fields that may contain health details.
_SENSITIVE_EXACT = ("instructions", "user_note")


def _is_sensitive_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in _SENSITIVE_EXACT or any(s in lowered for s in _SENSITIVE_SUBSTRINGS)


def _mask(value: Any) -> Any:
    if isinstance(value, dict):
        return {
            key: REDACTED if isinstance(key, str) and _is_sensitive_key(key) else _mask(inner)
            for key, inner in value.items()
        }
    if isinstance(value, (list, tuple)):
        return [_mask(item) for item in value]
    return value


def mask_sensitive(
    logger: structlog.typing.WrappedLogger,
    method_name: str,
    event_dict: structlog.typing.EventDict,
) -> structlog.typing.EventDict:
    """structlog processor that redacts sensitive keys, recursively."""
    masked = _mask(event_dict)
    assert isinstance(masked, dict)  # noqa: S101 - event_dict is always a dict
    return masked


def _add_service(service_name: str) -> structlog.typing.Processor:
    def processor(
        logger: structlog.typing.WrappedLogger,
        method_name: str,
        event_dict: structlog.typing.EventDict,
    ) -> structlog.typing.EventDict:
        event_dict.setdefault("service", service_name)
        return event_dict

    return processor


def configure_logging(settings: BaseServiceSettings) -> None:
    """Configure structlog and stdlib logging to emit JSON lines on stdout.

    Call once at service startup (module import time in ``app.main``).
    stdlib loggers (uvicorn, sqlalchemy, alembic, …) are routed through the
    same processor chain so all output shares one format.
    """
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    shared_processors: list[structlog.typing.Processor] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True, key="timestamp"),
        _add_service(settings.service_name),
        mask_sensitive,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(level),
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    formatter = structlog.stdlib.ProcessorFormatter(
        foreign_pre_chain=shared_processors,
        processors=[
            structlog.stdlib.ProcessorFormatter.remove_processors_meta,
            structlog.processors.JSONRenderer(),
        ],
    )
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(formatter)
    root = logging.getLogger()
    root.handlers = [handler]
    root.setLevel(level)

    # uvicorn installs its own handlers; strip them so lines are not duplicated.
    for name in ("uvicorn", "uvicorn.access", "uvicorn.error"):
        uvicorn_logger = logging.getLogger(name)
        uvicorn_logger.handlers = []
        uvicorn_logger.propagate = True


def get_logger(name: str | None = None) -> structlog.typing.FilteringBoundLogger:
    """Return a bound structlog logger."""
    return structlog.get_logger(name)  # type: ignore[no-any-return]
