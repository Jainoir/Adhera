"""Adhera API Gateway — FastAPI application entry point."""

from collections.abc import Coroutine
from typing import Any

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from prometheus_fastapi_instrumentator import Instrumentator

from app.config import settings
from shared.logging import configure_logging
from shared.logging.middleware import CorrelationIdMiddleware
from shared.readiness import ping_redis, readiness_report

configure_logging(settings)

app = FastAPI(
    title="Adhera API Gateway",
    version="0.1.0",
    description="Part of the Adhera medication adherence platform.",
)
app.add_middleware(CorrelationIdMiddleware)
Instrumentator().instrument(app).expose(app, tags=["observability"])


@app.get("/health", tags=["observability"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready", tags=["observability"])
async def ready() -> JSONResponse:
    """Readiness probe: pings every configured dependency; 503 when any fails."""
    checks: dict[str, Coroutine[Any, Any, None]] = {}
    if settings.redis_url:
        checks["redis"] = ping_redis(settings.redis_url)
    all_ok, statuses = await readiness_report(checks)
    return JSONResponse(
        status_code=200 if all_ok else 503,
        content={
            "status": "ready" if all_ok else "not_ready",
            "service": settings.service_name,
            "checks": statuses,
        },
    )
