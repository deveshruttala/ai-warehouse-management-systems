"""Event-generation state machine tests."""
from datetime import datetime, timedelta, timezone

from app.pipeline.detector import Observation
from app.pipeline.event_gen import EventGenerator
from app.schemas import EventType


def _obs(track_id, cx, cy):
    return Observation(track_id=track_id, cx=cx, cy=cy, x=cx - 0.02, y=cy - 0.05, w=0.04, h=0.1, confidence=0.9)


def test_track_lifecycle_and_line_crossing():
    eg = EventGenerator("cam-01")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)

    # New track left of the entrance line (x=0.16), in the 'entrance' zone.
    evs = eg.process([_obs(1, 0.10, 0.5)], ts=t0)
    types = [e.event_type for e in evs]
    assert EventType.TRACK_STARTED in types
    assert EventType.ZONE_ENTERED in types  # entrance zone

    # Move right, crossing the entrance line inward and into skincare.
    evs = eg.process([_obs(1, 0.30, 0.30)], ts=t0 + timedelta(seconds=1))
    types = [e.event_type for e in evs]
    assert EventType.LINE_CROSSED in types
    crossed = next(e for e in evs if e.event_type == EventType.LINE_CROSSED)
    assert crossed.payload.direction.value == "in"
    assert EventType.ZONE_ENTERED in types  # entered skincare

    # Track disappears -> zone.exited (with dwell) + track.ended.
    evs = eg.process([], ts=t0 + timedelta(seconds=5))
    types = [e.event_type for e in evs]
    assert EventType.ZONE_EXITED in types
    assert EventType.TRACK_ENDED in types
    ended = next(e for e in evs if e.event_type == EventType.TRACK_ENDED)
    assert ended.payload.duration_sec == 5.0


def test_zone_exit_emits_dwell():
    eg = EventGenerator("cam-01")
    t0 = datetime(2026, 1, 1, tzinfo=timezone.utc)
    eg.process([_obs(2, 0.30, 0.30)], ts=t0)  # enters skincare
    evs = eg.process([_obs(2, 0.60, 0.30)], ts=t0 + timedelta(seconds=12))  # -> fragrance
    exited = [e for e in evs if e.event_type == EventType.ZONE_EXITED]
    assert exited and exited[0].payload.dwell_sec == 12.0
