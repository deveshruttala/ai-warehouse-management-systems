"""Analytics engine aggregation tests."""
from datetime import datetime, timezone

from app.analytics import AnalyticsEngine
from app.schemas import (
    Direction,
    Event,
    LineCrossedPayload,
    TrackStartedPayload,
    ZoneEnteredPayload,
    ZoneExitedPayload,
    BBox,
)


def _bbox():
    return BBox(x=0.1, y=0.1, w=0.04, h=0.1, cx=0.12, cy=0.15)


def test_footfall_and_occupancy_accounting():
    eng = AnalyticsEngine()
    now = datetime.now(timezone.utc)

    eng.ingest(Event.of("c", TrackStartedPayload(track_id=1, bbox=_bbox(), confidence=0.9), ts=now))
    eng.ingest(Event.of("c", LineCrossedPayload(track_id=1, line="entrance_line", direction=Direction.IN), ts=now))
    eng.ingest(Event.of("c", ZoneEnteredPayload(track_id=1, zone="skincare"), ts=now))

    snap = eng.snapshot()
    assert snap.footfall_in == 1
    assert snap.active_tracks == 1
    assert eng.store_occupancy == 1
    skincare = next(z for z in snap.zones if z.zone == "skincare")
    assert skincare.occupancy == 1
    assert skincare.total_entries == 1

    eng.ingest(Event.of("c", ZoneExitedPayload(track_id=1, zone="skincare", dwell_sec=20.0), ts=now))
    eng.ingest(Event.of("c", LineCrossedPayload(track_id=1, line="entrance_line", direction=Direction.OUT), ts=now))
    snap = eng.snapshot()
    assert snap.footfall_out == 1
    assert eng.store_occupancy == 0
    skincare = next(z for z in snap.zones if z.zone == "skincare")
    assert skincare.occupancy == 0
    assert skincare.avg_dwell_sec == 20.0


def test_queue_length_tracks_checkout_zone():
    eng = AnalyticsEngine()
    now = datetime.now(timezone.utc)
    for tid in range(5):
        eng.ingest(Event.of("c", ZoneEnteredPayload(track_id=tid, zone="checkout"), ts=now))
    assert eng.queue_length("checkout") == 5
    snap = eng.snapshot()
    checkout = next(z for z in snap.zones if z.zone == "checkout")
    assert checkout.queue_length == 5
