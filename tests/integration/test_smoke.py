"""Phase 0 smoke test: every service boots against real infrastructure.

Each service is started as a real uvicorn process (the same entry point its
container uses) pointed at Testcontainers-provided Postgres, Redis and
RabbitMQ, then probed on ``/health``, ``/ready`` and ``/metrics``. Running
services as subprocesses also sidesteps the fact that all services share the
top-level ``app`` package name, which forbids importing two of them into one
interpreter.
"""

from __future__ import annotations

import os
import socket
import subprocess
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

import httpx
import pytest

from shared.test_utils import rabbitmq_url, redis_url

if TYPE_CHECKING:
    from testcontainers.postgres import PostgresContainer
    from testcontainers.rabbitmq import RabbitMqContainer
    from testcontainers.redis import RedisContainer

REPO_ROOT = Path(__file__).resolve().parents[2]
STARTUP_TIMEOUT_SECONDS = 60.0

# Which dependencies each service has configured (redis: all of them).
SERVICES: dict[str, dict[str, bool]] = {
    "api-gateway": {"database": False, "rabbitmq": False},
    "identity-service": {"database": True, "rabbitmq": False},
    "medication-service": {"database": True, "rabbitmq": True},
    "notification-service": {"database": True, "rabbitmq": True},
}


def _free_port() -> int:
    with socket.socket() as sock:
        sock.bind(("127.0.0.1", 0))
        port: int = sock.getsockname()[1]
        return port


def _wait_until_healthy(url: str) -> None:
    deadline = time.monotonic() + STARTUP_TIMEOUT_SECONDS
    last_error: Exception | None = None
    while time.monotonic() < deadline:
        try:
            if httpx.get(url, timeout=2.0).status_code == 200:
                return
        except httpx.HTTPError as exc:
            last_error = exc
        time.sleep(0.5)
    raise AssertionError(
        f"{url} did not become healthy within {STARTUP_TIMEOUT_SECONDS}s: {last_error!r}"
    )


@pytest.mark.integration
@pytest.mark.parametrize("service", SERVICES)
def test_service_boots_healthy_and_ready(
    service: str,
    postgres_container: PostgresContainer,
    redis_container: RedisContainer,
    rabbitmq_container: RabbitMqContainer,
) -> None:
    needs = SERVICES[service]
    env = os.environ.copy()
    env["SERVICE_NAME"] = service
    env["PYTHONPATH"] = str(REPO_ROOT)
    env["REDIS_URL"] = redis_url(redis_container)
    env["DATABASE_URL"] = postgres_container.get_connection_url() if needs["database"] else ""
    env["RABBITMQ_URL"] = rabbitmq_url(rabbitmq_container) if needs["rabbitmq"] else ""

    port = _free_port()
    argv = [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1"]
    process = subprocess.Popen(  # noqa: S603 - fixed argv, no shell
        [*argv, "--port", str(port)],
        cwd=REPO_ROOT / "services" / service,
        env=env,
    )
    base = f"http://127.0.0.1:{port}"
    try:
        _wait_until_healthy(f"{base}/health")

        health = httpx.get(f"{base}/health", timeout=5.0)
        assert health.status_code == 200
        assert health.json() == {"status": "ok", "service": service}

        ready = httpx.get(f"{base}/ready", timeout=15.0)
        assert ready.status_code == 200, ready.text
        body = ready.json()
        assert body["status"] == "ready"
        assert all(status == "ok" for status in body["checks"].values()), body

        metrics = httpx.get(f"{base}/metrics", timeout=5.0)
        assert metrics.status_code == 200
        assert "http" in metrics.text
    finally:
        process.terminate()
        try:
            process.wait(timeout=10)
        except subprocess.TimeoutExpired:
            process.kill()
            process.wait(timeout=10)
