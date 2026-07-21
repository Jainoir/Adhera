"""Unit tests for the event schema loader and EventEnvelope."""

from uuid import uuid4

import pytest

from shared.event_schemas import (
    EventEnvelope,
    EventValidationError,
    UnknownEventTypeError,
    load_schema,
    validate_event,
)

VALID_DOSE_DUE_PAYLOAD = {
    "dose_instance_id": str(uuid4()),
    "patient_id": str(uuid4()),
    "medication_id": str(uuid4()),
    "scheduled_at": "2026-07-20T08:00:00+00:00",
}


def _valid_message() -> dict[str, object]:
    return EventEnvelope(event_type="DoseDue", payload=dict(VALID_DOSE_DUE_PAYLOAD)).to_message(
        validate=False
    )


def test_load_schema_finds_all_versioned_schemas() -> None:
    for event_type in (
        "DoseDue",
        "DoseConfirmed",
        "DoseConfirmationOverdue",
        "CaregiverAlerted",
        "AlertAcknowledged",
    ):
        schema = load_schema(event_type, version=1)
        assert schema["properties"]["event_type"]["const"] == event_type


def test_load_schema_unknown_event_type_raises() -> None:
    with pytest.raises(UnknownEventTypeError):
        load_schema("NoSuchEvent")


def test_valid_dose_due_message_passes_validation() -> None:
    validate_event(_valid_message())


def test_missing_required_field_fails_validation() -> None:
    message = _valid_message()
    del message["patient_id"]
    with pytest.raises(EventValidationError, match="patient_id"):
        validate_event(message)


def test_missing_event_type_fails_validation() -> None:
    with pytest.raises(EventValidationError):
        validate_event({"event_id": str(uuid4())})


def test_envelope_to_message_flattens_and_validates() -> None:
    envelope = EventEnvelope(event_type="DoseDue", payload=dict(VALID_DOSE_DUE_PAYLOAD))
    message = envelope.to_message()
    assert message["event_type"] == "DoseDue"
    assert message["event_version"] == 1
    assert message["dose_instance_id"] == VALID_DOSE_DUE_PAYLOAD["dose_instance_id"]


def test_envelope_round_trip() -> None:
    original = EventEnvelope(event_type="DoseDue", payload=dict(VALID_DOSE_DUE_PAYLOAD))
    restored = EventEnvelope.from_message(original.to_message())
    assert restored.event_id == original.event_id
    assert restored.correlation_id == original.correlation_id
    assert restored.payload == original.payload
