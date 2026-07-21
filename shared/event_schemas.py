"""Loader and validator for Adhera's versioned event JSON Schemas.

Schemas live in ``shared/event-schemas/`` as ``<event_type>.v<version>.json``
(snake_case file names, e.g. ``dose_due.v1.json`` for event type ``DoseDue``).
Events travel on the wire as flat JSON objects: the envelope fields
(``event_id``, ``event_type``, ``event_version``, ``occurred_at``,
``correlation_id``) plus the event-specific payload fields at the top level —
exactly the shape the JSON Schemas describe. :class:`EventEnvelope` is the
typed producer/consumer view of that message.
"""

from __future__ import annotations

import json
import re
from datetime import UTC, datetime
from functools import cache
from pathlib import Path
from typing import Any
from uuid import UUID, uuid4

import jsonschema
from pydantic import BaseModel, Field

SCHEMA_DIR = Path(__file__).resolve().parent / "event-schemas"


class UnknownEventTypeError(KeyError):
    """Raised when no schema file exists for an event type + version."""


class EventValidationError(ValueError):
    """Raised when an event message does not match its JSON Schema."""


def _snake_case(event_type: str) -> str:
    return re.sub(r"(?<!^)(?=[A-Z])", "_", event_type).lower()


@cache
def load_schema(event_type: str, version: int = 1) -> dict[str, Any]:
    """Load the JSON Schema for ``event_type`` (CamelCase) at ``version``."""
    path = SCHEMA_DIR / f"{_snake_case(event_type)}.v{version}.json"
    if not path.is_file():
        raise UnknownEventTypeError(
            f"No schema for event type {event_type!r} version {version} (expected {path.name})"
        )
    schema: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return schema


def validate_event(message: dict[str, Any]) -> None:
    """Validate a flat event message against its versioned schema.

    Raises :class:`UnknownEventTypeError` for unregistered event types and
    :class:`EventValidationError` when the message violates its schema.
    """
    event_type = message.get("event_type")
    if not isinstance(event_type, str) or not event_type:
        raise EventValidationError("Event message is missing 'event_type'")
    version = message.get("event_version", 1)
    if not isinstance(version, int):
        raise EventValidationError("'event_version' must be an integer")

    schema = load_schema(event_type, version)
    validator_cls = jsonschema.validators.validator_for(schema)
    validator = validator_cls(schema, format_checker=validator_cls.FORMAT_CHECKER)
    errors = sorted(validator.iter_errors(message), key=lambda e: list(e.absolute_path))
    if errors:
        details = "; ".join(error.message for error in errors)
        raise EventValidationError(f"Event {event_type} v{version} failed validation: {details}")


class EventEnvelope(BaseModel):
    """Typed envelope for domain events; ``to_message`` produces the wire shape."""

    event_id: UUID = Field(default_factory=uuid4)
    event_type: str
    event_version: int = 1
    occurred_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    correlation_id: UUID = Field(default_factory=uuid4)
    payload: dict[str, Any] = Field(default_factory=dict)

    def to_message(self, validate: bool = True) -> dict[str, Any]:
        """Flatten the envelope + payload into the on-the-wire dict."""
        message: dict[str, Any] = {
            "event_id": str(self.event_id),
            "event_type": self.event_type,
            "event_version": self.event_version,
            "occurred_at": self.occurred_at.isoformat(),
            "correlation_id": str(self.correlation_id),
            **self.payload,
        }
        if validate:
            validate_event(message)
        return message

    @classmethod
    def from_message(cls, message: dict[str, Any], validate: bool = True) -> EventEnvelope:
        """Parse a wire message back into an envelope (payload = non-envelope keys)."""
        if validate:
            validate_event(message)
        envelope_keys = {"event_id", "event_type", "event_version", "occurred_at", "correlation_id"}
        payload = {key: value for key, value in message.items() if key not in envelope_keys}
        return cls(
            event_id=UUID(message["event_id"]),
            event_type=message["event_type"],
            event_version=message["event_version"],
            occurred_at=datetime.fromisoformat(message["occurred_at"]),
            correlation_id=UUID(message["correlation_id"]),
            payload=payload,
        )
