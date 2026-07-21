"""ASGI middleware that reads or creates the ``X-Correlation-ID`` header.

The correlation ID is bound to structlog contextvars for the lifetime of
the request (so every log line carries it) and echoed back on the
response, letting clients and downstream services join up traces.
"""

from __future__ import annotations

import uuid
from collections.abc import Awaitable, Callable, MutableMapping
from typing import Any

from structlog.contextvars import bind_contextvars, clear_contextvars

Scope = MutableMapping[str, Any]
Message = MutableMapping[str, Any]
Receive = Callable[[], Awaitable[Message]]
Send = Callable[[Message], Awaitable[None]]

CORRELATION_ID_HEADER = "X-Correlation-ID"
_HEADER_BYTES = CORRELATION_ID_HEADER.lower().encode("latin-1")
_MAX_LENGTH = 128


def _incoming_correlation_id(scope: Scope) -> str | None:
    for name, value in scope.get("headers") or []:
        if name == _HEADER_BYTES:
            candidate: str = value.decode("latin-1").strip()
            if 0 < len(candidate) <= _MAX_LENGTH:
                return candidate
    return None


class CorrelationIdMiddleware:
    """Pure ASGI middleware — register in every service with ``add_middleware``."""

    def __init__(self, app: Callable[[Scope, Receive, Send], Awaitable[None]]) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        correlation_id = _incoming_correlation_id(scope) or str(uuid.uuid4())
        scope.setdefault("state", {})["correlation_id"] = correlation_id
        clear_contextvars()
        bind_contextvars(correlation_id=correlation_id)

        async def send_with_header(message: Message) -> None:
            if message["type"] == "http.response.start":
                headers = message.setdefault("headers", [])
                headers.append((_HEADER_BYTES, correlation_id.encode("latin-1")))
            await send(message)

        try:
            await self.app(scope, receive, send_with_header)
        finally:
            clear_contextvars()
