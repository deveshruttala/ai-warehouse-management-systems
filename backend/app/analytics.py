"""Real-time analytics engine.

Maintains in-memory, continuously-updated store metrics by consuming the event
stream: footfall (in/out), live store + per-zone occupancy, dwell times, and
checkout queue length / estimated wait. Also keeps per-minute rolling buckets
to power the dashboard's trend charts.
"""
from __future__ import annotations

from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone

from .schemas import (
    Event,
    EventType,
    LiveMetrics,
    TimeBucket,
    ZoneStats,
)
from .pipeline.zones import (
    DEFAULT_LAYOUT,
    QUEUE_ZONES,
    SALES_FLOOR_ZONES,
    StoreLayout,
)

HISTORY_MINUTES = 180
DWELL_WINDOW = 50  # recent dwell samples kept per zone


def _minute_floor(ts: datetime) -> datetime:
    return ts.replace(second=0, microsecond=0)


class _MinuteBucket:
    __slots__ = ("footfall_in", "footfall_out", "occ_sum", "occ_n")

    def __init__(self) -> None:
        self.footfall_in = 0
        self.footfall_out = 0
        self.occ_sum = 0
        self.occ_n = 0

    @property
    def avg_occupancy(self) -> float:
        return self.occ_sum / self.occ_n if self.occ_n else 0.0


class AnalyticsEngine:
    def __init__(self, layout: StoreLayout = DEFAULT_LAYOUT):
        self.layout = layout
        self.zone_occupancy: dict[str, set[int]] = defaultdict(set)
        self.zone_entries: dict[str, int] = defaultdict(int)
        self.zone_dwell: dict[str, deque[float]] = defaultdict(lambda: deque(maxlen=DWELL_WINDOW))
        self.active_tracks: set[int] = set()
        self.footfall_in = 0
        self.footfall_out = 0
        self.track_zone_entry: dict[int, tuple[str, datetime]] = {}
        self.buckets: dict[datetime, _MinuteBucket] = {}
        self.open_anomalies = 0
        self.last_ts: datetime = datetime.now(timezone.utc)

    # ------------------------------------------------------------------ #
    def _bucket(self, ts: datetime) -> _MinuteBucket:
        key = _minute_floor(ts)
        b = self.buckets.get(key)
        if b is None:
            b = _MinuteBucket()
            self.buckets[key] = b
            # Trim history.
            cutoff = key - timedelta(minutes=HISTORY_MINUTES)
            for k in [k for k in self.buckets if k < cutoff]:
                del self.buckets[k]
        return b

    # ------------------------------------------------------------------ #
    def ingest(self, event: Event) -> None:
        self.last_ts = event.ts
        p = event.payload
        et = event.event_type

        if et == EventType.TRACK_STARTED:
            self.active_tracks.add(p.track_id)
        elif et == EventType.TRACK_ENDED:
            self.active_tracks.discard(p.track_id)
            self.track_zone_entry.pop(p.track_id, None)
        elif et == EventType.LINE_CROSSED:
            b = self._bucket(event.ts)
            if p.direction.value == "in":
                self.footfall_in += 1
                b.footfall_in += 1
            else:
                self.footfall_out += 1
                b.footfall_out += 1
        elif et == EventType.ZONE_ENTERED:
            self.zone_occupancy[p.zone].add(p.track_id)
            self.zone_entries[p.zone] += 1
            self.track_zone_entry[p.track_id] = (p.zone, event.ts)
        elif et == EventType.ZONE_EXITED:
            self.zone_occupancy[p.zone].discard(p.track_id)
            self.zone_dwell[p.zone].append(p.dwell_sec)
            self.track_zone_entry.pop(p.track_id, None)
        elif et == EventType.ANOMALY:
            self.open_anomalies += 1

        # Sample current store occupancy into the active minute bucket.
        b = self._bucket(event.ts)
        b.occ_sum += self.store_occupancy
        b.occ_n += 1

    # ------------------------------------------------------------------ #
    @property
    def store_occupancy(self) -> int:
        return sum(len(self.zone_occupancy[z]) for z in SALES_FLOOR_ZONES)

    def _avg_dwell(self, zone: str) -> float:
        d = self.zone_dwell.get(zone)
        return round(sum(d) / len(d), 1) if d else 0.0

    def queue_length(self, zone: str) -> int:
        return len(self.zone_occupancy.get(zone, ()))

    def avg_wait(self, zone: str) -> float:
        # Simple estimator: queue length * mean service time proxy (avg dwell).
        avg_dwell = self._avg_dwell(zone)
        return round(self.queue_length(zone) * max(avg_dwell, 8.0) / 2.0, 1)

    def current_dwell(self, track_id: int, now: datetime) -> tuple[str, float] | None:
        info = self.track_zone_entry.get(track_id)
        if not info:
            return None
        zone, entry = info
        return zone, (now - entry).total_seconds()

    # ------------------------------------------------------------------ #
    def snapshot(self) -> LiveMetrics:
        zones: list[ZoneStats] = []
        for z in self.layout.zones:
            is_queue = z.name in QUEUE_ZONES
            zones.append(
                ZoneStats(
                    zone=z.name,
                    occupancy=len(self.zone_occupancy.get(z.name, ())),
                    total_entries=self.zone_entries.get(z.name, 0),
                    avg_dwell_sec=self._avg_dwell(z.name),
                    queue_length=self.queue_length(z.name) if is_queue else None,
                    avg_wait_sec=self.avg_wait(z.name) if is_queue else None,
                )
            )
        return LiveMetrics(
            ts=datetime.now(timezone.utc),
            store_occupancy=self.store_occupancy,
            footfall_in=self.footfall_in,
            footfall_out=self.footfall_out,
            active_tracks=len(self.active_tracks),
            zones=zones,
            open_anomalies=self.open_anomalies,
        )

    def history(self, minutes: int = 60) -> list[TimeBucket]:
        cutoff = _minute_floor(datetime.now(timezone.utc)) - timedelta(minutes=minutes)
        out: list[TimeBucket] = []
        for key in sorted(self.buckets):
            if key < cutoff:
                continue
            b = self.buckets[key]
            out.append(
                TimeBucket(
                    bucket=key,
                    footfall_in=b.footfall_in,
                    footfall_out=b.footfall_out,
                    avg_occupancy=round(b.avg_occupancy, 2),
                )
            )
        return out


_engine: AnalyticsEngine | None = None


def get_engine() -> AnalyticsEngine:
    global _engine
    if _engine is None:
        _engine = AnalyticsEngine()
    return _engine
