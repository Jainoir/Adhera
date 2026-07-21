"""Shared libraries used by all Adhera services.

Subpackages:
- ``shared.config`` — pydantic-settings base class for service configuration.
- ``shared.logging`` — structlog JSON logging + correlation-ID middleware.
- ``shared.readiness`` — dependency ping helpers for ``/ready`` endpoints.
- ``shared.event_schemas`` — versioned event schema loader and envelope model.
- ``shared.test_utils`` — Testcontainers fixtures and async test clients (dev only).
"""
