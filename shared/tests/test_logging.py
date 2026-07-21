"""Unit tests for shared structured logging and the sensitive-data mask."""

import json

import structlog

from shared.config import BaseServiceSettings
from shared.logging import REDACTED, configure_logging, get_logger, mask_sensitive


def _mask(event_dict: dict) -> dict:  # type: ignore[type-arg]
    return dict(mask_sensitive(None, "info", event_dict))


def test_mask_sensitive_redacts_credentials() -> None:
    masked = _mask(
        {
            "event": "login",
            "password": "hunter2",
            "password_hash": "abc",
            "access_token": "tok",
            "refresh_token": "tok2",
            "authorization": "Bearer xyz",
            "client_secret": "sst",
        }
    )
    assert masked["event"] == "login"
    for key in (
        "password",
        "password_hash",
        "access_token",
        "refresh_token",
        "authorization",
        "client_secret",
    ):
        assert masked[key] == REDACTED


def test_mask_sensitive_redacts_medication_free_text() -> None:
    masked = _mask({"instructions": "take with food", "user_note": "felt dizzy", "name": "ok"})
    assert masked["instructions"] == REDACTED
    assert masked["user_note"] == REDACTED
    assert masked["name"] == "ok"


def test_mask_sensitive_recurses_into_nested_structures() -> None:
    masked = _mask(
        {
            "payload": {"user": {"password": "pw"}, "items": [{"token": "t"}, {"safe": 1}]},
        }
    )
    assert masked["payload"]["user"]["password"] == REDACTED
    assert masked["payload"]["items"][0]["token"] == REDACTED
    assert masked["payload"]["items"][1]["safe"] == 1


def test_configure_logging_emits_json_with_required_fields(capsys) -> None:  # type: ignore[no-untyped-def]
    configure_logging(BaseServiceSettings(service_name="test-service", log_level="INFO"))
    structlog.contextvars.clear_contextvars()
    structlog.contextvars.bind_contextvars(correlation_id="cid-123")
    try:
        get_logger("test").info("something_happened", password="supersecret", detail=42)
    finally:
        structlog.contextvars.clear_contextvars()

    line = capsys.readouterr().out.strip().splitlines()[-1]
    record = json.loads(line)
    assert record["event"] == "something_happened"
    assert record["level"] == "info"
    assert record["service"] == "test-service"
    assert record["correlation_id"] == "cid-123"
    assert "timestamp" in record
    assert record["password"] == REDACTED
    assert "supersecret" not in line
    assert record["detail"] == 42
