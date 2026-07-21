"""Wires the shared Testcontainers fixtures into the integration suite."""

from shared.test_utils import (  # noqa: F401
    postgres_container,
    rabbitmq_container,
    redis_container,
)
