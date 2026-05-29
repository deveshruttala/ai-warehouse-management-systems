"""Convert per-frame observations into domain events.

A stateful machine that remembers each track's previous position and zone, so
it can emit zone transitions, directional line crossings and track lifecycle
events. This is the bridge between raw CV output and the event schema.
"""
from __future__ import annotations

from datetime import datetime, timezone

from ..schemas import (
    BBox,
    Direction,
    Event,
    LineCrossedPayload,
    TrackEndedPayload,
    TrackStartedPayload,
    ZoneEnteredPayload,
    ZoneExitedPayload,
)
from .detector import Observation
from .zones import DEFAULT_LAYOUT, StoreLayout


class _TrackState:
    __slots__ = ("start_ts", "last_cx", "zone", "zone_entry_ts", "last_seen_ts")

    def __init__(self, ts: datetime, cx: float):
        self.start_ts = ts
        self.last_cx = cx
        self.zone: str | None = None
        self.zone_entry_ts: datetime = ts
        self.last_seen_ts = ts


class EventGenerator:
    def __init__(self, camera_id: str, layout: StoreLayout = DEFAULT_LAYOUT):
        self.camera_id = camera_id
        self.layout = layout
        self._state: dict[int, _TrackState] = {}

    def _emit(self, payload, ts: datetime) -> Event:
        return Event.of(self.camera_id, payload, ts=ts)

    def process(self, observations: list[Observation], ts: datetime | None = None) -> list[Event]:
        now = ts or datetime.now(timezone.utc)
        events: list[Event] = []
        seen: set[int] = set()

        for ob in observations:
            seen.add(ob.track_id)
            zone_now = self.layout.zone_at(ob.cx, ob.cy)
            st = self._state.get(ob.track_id)

            if st is None:
                st = _TrackState(now, ob.cx)
                self._state[ob.track_id] = st
                bbox = BBox(x=ob.x, y=ob.y, w=ob.w, h=ob.h, cx=ob.cx, cy=ob.cy)
                events.append(
                    self._emit(
                        TrackStartedPayload(track_id=ob.track_id, bbox=bbox, confidence=ob.confidence),
                        now,
                    )
                )
                if zone_now is not None:
                    st.zone = zone_now
                    st.zone_entry_ts = now
                    events.append(self._emit(ZoneEnteredPayload(track_id=ob.track_id, zone=zone_now), now))
                st.last_cx = ob.cx
                st.last_seen_ts = now
                continue

            # Directional line crossings.
            for line in self.layout.lines:
                crossed_right = st.last_cx < line.x <= ob.cx
                crossed_left = st.last_cx > line.x >= ob.cx
                if crossed_right or crossed_left:
                    inward = crossed_right if line.inward_is_right else crossed_left
                    events.append(
                        self._emit(
                            LineCrossedPayload(
                                track_id=ob.track_id,
                                line=line.name,
                                direction=Direction.IN if inward else Direction.OUT,
                            ),
                            now,
                        )
                    )

            # Zone transitions.
            if zone_now != st.zone:
                if st.zone is not None:
                    dwell = (now - st.zone_entry_ts).total_seconds()
                    events.append(
                        self._emit(ZoneExitedPayload(track_id=ob.track_id, zone=st.zone, dwell_sec=dwell), now)
                    )
                if zone_now is not None:
                    events.append(self._emit(ZoneEnteredPayload(track_id=ob.track_id, zone=zone_now), now))
                    st.zone_entry_ts = now
                st.zone = zone_now

            st.last_cx = ob.cx
            st.last_seen_ts = now

        # Tracks that vanished this frame -> close out.
        for tid in list(self._state):
            if tid in seen:
                continue
            st = self._state.pop(tid)
            if st.zone is not None:
                dwell = (now - st.zone_entry_ts).total_seconds()
                events.append(self._emit(ZoneExitedPayload(track_id=tid, zone=st.zone, dwell_sec=dwell), now))
            duration = (now - st.start_ts).total_seconds()
            events.append(
                self._emit(TrackEndedPayload(track_id=tid, duration_sec=duration, last_zone=st.zone), now)
            )

        return events
