"""Testcontainers fixtures and async client helpers for Adhera tests.

Import the fixtures from a ``conftest.py`` to make them available to a
test suite (see ``tests/integration/conftest.py``). All fixtures are
session-scoped: containers start once per test run.
"""

from __future__ import annotations

from collections.abc import Iterator
from typing import Any

import pytest
from httpx import ASGITransport, AsyncClient
from testcontainers.postgres import PostgresContainer
from testcontainers.rabbitmq import RabbitMqContainer
from testcontainers.redis import RedisContainer

POSTGRES_IMAGE = "postgres:16-alpine"
REDIS_IMAGE = "redis:7-alpine"
RABBITMQ_IMAGE = "rabbitmq:3-management-alpine"


@pytest.fixture(scope="session")
def postgres_container() -> Iterator[PostgresContainer]:
    """PostgreSQL container; ``get_connection_url()`` yields an asyncpg URL."""
    with PostgresContainer(POSTGRES_IMAGE, driver="asyncpg") as container:
        yield container


@pytest.fixture(scope="session")
def redis_container() -> Iterator[RedisContainer]:
    with RedisContainer(REDIS_IMAGE) as container:
        yield container


@pytest.fixture(scope="session")
def rabbitmq_container() -> Iterator[RabbitMqContainer]:
    with RabbitMqContainer(RABBITMQ_IMAGE) as container:
        yield container


def redis_url(container: RedisContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(container.port)
    return f"redis://{host}:{port}/0"


def rabbitmq_url(container: RabbitMqContainer) -> str:
    host = container.get_container_host_ip()
    port = container.get_exposed_port(container.port)
    return f"amqp://{container.username}:{container.password}@{host}:{port}/"


def async_client(app: Any, base_url: str = "http://testserver") -> AsyncClient:
    """HTTPX AsyncClient bound to a FastAPI app in-process (no sockets)."""
    return AsyncClient(transport=ASGITransport(app=app), base_url=base_url)
