"""Unit tests for the correlation-ID ASGI middleware."""

import uuid

from fastapi import FastAPI
from fastapi.testclient import TestClient
from structlog.contextvars import get_contextvars

from shared.logging.middleware import CORRELATION_ID_HEADER, CorrelationIdMiddleware


def _build_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(CorrelationIdMiddleware)

    @app.get("/echo")
    async def echo() -> dict[str, str | None]:
        return {"bound_correlation_id": get_contextvars().get("correlation_id")}

    return app


def test_generates_correlation_id_when_absent() -> None:
    client = TestClient(_build_app())
    response = client.get("/echo")
    header = response.headers[CORRELATION_ID_HEADER]
    uuid.UUID(header)  # generated IDs are UUIDs
    assert response.json()["bound_correlation_id"] == header


def test_echoes_provided_correlation_id() -> None:
    client = TestClient(_build_app())
    response = client.get("/echo", headers={CORRELATION_ID_HEADER: "client-supplied-id"})
    assert response.headers[CORRELATION_ID_HEADER] == "client-supplied-id"
    assert response.json()["bound_correlation_id"] == "client-supplied-id"


def test_rejects_oversized_correlation_id() -> None:
    client = TestClient(_build_app())
    response = client.get("/echo", headers={CORRELATION_ID_HEADER: "x" * 200})
    header = response.headers[CORRELATION_ID_HEADER]
    assert header != "x" * 200
    uuid.UUID(header)
