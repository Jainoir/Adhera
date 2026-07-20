"""Adhera Notification and Escalation Service — FastAPI application entry point."""

from fastapi import FastAPI

from app.config import settings

app = FastAPI(
    title="Adhera Notification and Escalation Service",
    version="0.1.0",
    description="Part of the Adhera medication adherence platform.",
)


@app.get("/health", tags=["observability"])
async def health() -> dict[str, str]:
    """Liveness probe."""
    return {"status": "ok", "service": settings.service_name}


@app.get("/ready", tags=["observability"])
async def ready() -> dict[str, str]:
    """Readiness probe. Extend with DB/broker checks as dependencies are added."""
    return {"status": "ready", "service": settings.service_name}
