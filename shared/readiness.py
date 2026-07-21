"""Dependency ping helpers for service ``/ready`` endpoints.

Each service builds a mapping of dependency name → check coroutine for the
dependencies it actually has configured, then calls :func:`readiness_report`.
A failing or slow (> ``CHECK_TIMEOUT_SECONDS``) dependency marks the service
not ready; the per-dependency status map is returned either way so operators
can see exactly which dependency is down.
"""

from __future__ import annotations

import asyncio
from collections.abc import Coroutine
from typing import TYPE_CHECKING, Any

from sqlalchemy import text

if TYPE_CHECKING:
    from sqlalchemy.ext.asyncio import AsyncEngine

CHECK_TIMEOUT_SECONDS = 3.0


async def ping_database(engine: AsyncEngine) -> None:
    """Round-trip ``SELECT 1`` on the service's own database."""
    async with engine.connect() as connection:
        await connection.execute(text("SELECT 1"))


async def ping_redis(redis_url: str) -> None:
    """PING the configured Redis instance."""
    import redis.asyncio as aioredis  # imported lazily: not every service needs redis

    client = aioredis.from_url(redis_url)
    try:
        await client.ping()
    finally:
        await client.aclose()


async def ping_rabbitmq(rabbitmq_url: str) -> None:
    """Open and close a connection to the configured RabbitMQ broker."""
    import aio_pika  # imported lazily: only event-driven services depend on aio-pika

    connection = await aio_pika.connect(rabbitmq_url)
    await connection.close()


async def _run_check(check: Coroutine[Any, Any, None]) -> str:
    try:
        await asyncio.wait_for(check, timeout=CHECK_TIMEOUT_SECONDS)
    except TimeoutError:
        return f"error: timed out after {CHECK_TIMEOUT_SECONDS}s"
    except Exception as exc:  # noqa: BLE001 - any dependency failure means "not ready"
        return f"error: {exc.__class__.__name__}: {exc}"
    return "ok"


async def readiness_report(
    checks: dict[str, Coroutine[Any, Any, None]],
) -> tuple[bool, dict[str, str]]:
    """Run all checks concurrently; return (all_ok, per-dependency status map)."""
    names = list(checks)
    results = await asyncio.gather(*(_run_check(checks[name]) for name in names))
    statuses = dict(zip(names, results, strict=True))
    return all(status == "ok" for status in statuses.values()), statuses
