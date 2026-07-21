"""Smoke tests for health, readiness, and metrics endpoints."""

import app.main as main
import pytest
from app.config import settings
from app.main import app
from fastapi.testclient import TestClient

client = TestClient(app)


def test_health() -> None:
    response = client.get("/health")
    assert response.status_code == 200
    assert response.json()["status"] == "ok"


def test_ready_with_no_dependencies_configured() -> None:
    response = client.get("/ready")
    assert response.status_code == 200
    assert response.json()["status"] == "ready"


def test_ready_returns_503_when_a_dependency_fails(monkeypatch: pytest.MonkeyPatch) -> None:
    async def failing_ping(redis_url: str) -> None:
        raise ConnectionError("redis down")

    monkeypatch.setattr(main, "ping_redis", failing_ping)
    monkeypatch.setattr(settings, "redis_url", "redis://redis.invalid:6379/0")

    response = client.get("/ready")
    assert response.status_code == 503
    body = response.json()
    assert body["status"] == "not_ready"
    assert body["checks"]["redis"].startswith("error:")


def test_ready_echoes_correlation_id() -> None:
    response = client.get("/ready", headers={"X-Correlation-ID": "test-cid"})
    assert response.headers["X-Correlation-ID"] == "test-cid"


def test_metrics_exposed() -> None:
    response = client.get("/metrics")
    assert response.status_code == 200
    assert "http" in response.text
