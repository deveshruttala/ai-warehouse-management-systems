"""Event-schema validation and round-trip tests."""
from app.schemas import (
    AnomalyPayload,
    AnomalyType,
    Direction,
    Event,
    EventType,
    LineCrossedPayload,
    ZoneEnteredPayload,
)


def test_event_envelope_round_trip():
    ev = Event.of("cam-01", ZoneEnteredPayload(track_id=7, zone="skincare"))
    assert ev.event_type == EventType.ZONE_ENTERED
    assert ev.camera_id == "cam-01"

    raw = ev.model_dump_json()
    back = Event.model_validate_json(raw)
    assert back.event_id == ev.event_id
    assert back.payload.zone == "skincare"
    assert back.payload.track_id == 7


def test_discriminated_payload_decodes_correct_type():
    ev = Event.of("cam-01", LineCrossedPayload(track_id=3, line="entrance_line", direction=Direction.IN))
    back = Event.model_validate_json(ev.model_dump_json())
    assert isinstance(back.payload, LineCrossedPayload)
    assert back.payload.direction == Direction.IN


def test_anomaly_payload_severity_bounds():
    p = AnomalyPayload(
        anomaly_type=AnomalyType.LONG_QUEUE,
        zone="checkout",
        severity=0.8,
        metric="queue_length",
        observed=9,
        expected=6,
        message="queue too long",
    )
    ev = Event.of("cam-01", p)
    assert ev.event_type == EventType.ANOMALY
    assert 0 <= ev.payload.severity <= 1
