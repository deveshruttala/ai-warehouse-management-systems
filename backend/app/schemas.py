"""Event schema design for the Store Intelligence System.

Every message flowing through the streaming layer is an :class:`Event` — a
versioned envelope with a typed ``payload``. This gives us:

* **Forward/backward compatibility** via ``schema_version``.
* **Strong typing** of each event kind for analytics consumers.
* **Traceability** via ``event_id`` (idempotency key) and ``camera_id``.

Event taxonomy
--------------
``track.started`` / ``track.ended``   - lifecycle of a tracked person
``zone.entered``  / ``zone.exited``   - a person crosses a configured zone
``line.crossed``                      - directional crossing of a counting line (footfall in/out)
``queue.update``                      - queue length at a checkout/service zone
``occupancy.update``                  - current people count per zone / store
``anomaly``                           - a detected anomaly (typed by ``anomaly_type``)
"""
from __future__ import annotations

import uuid
from datetime import datetime, timezone
from enum import Enum
from typing import Annotated, Literal, Union

from pydantic import BaseModel, Field

SCHEMA_VERSION = "1.0"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _new_id() -> str:
    return uuid.uuid4().hex


class EventType(str, Enum):
    TRACK_STARTED = "track.started"
    TRACK_ENDED = "track.ended"
    ZONE_ENTERED = "zone.entered"
    ZONE_EXITED = "zone.exited"
    LINE_CROSSED = "line.crossed"
    QUEUE_UPDATE = "queue.update"
    OCCUPANCY_UPDATE = "occupancy.update"
    ANOMALY = "anomaly"


class Direction(str, Enum):
    IN = "in"
    OUT = "out"


class AnomalyType(str, Enum):
    CROWD_SURGE = "crowd_surge"          # occupancy spikes abnormally
    LONG_QUEUE = "long_queue"            # checkout queue exceeds threshold
    EXCESSIVE_DWELL = "excessive_dwell"  # person lingers in a zone too long
    ZONE_INTRUSION = "zone_intrusion"    # presence in a restricted zone
    FOOTFALL_DROP = "footfall_drop"      # sudden drop in entries (e.g. blocked entrance)
    STATISTICAL = "statistical"          # generic z-score outlier on a metric


# --------------------------------------------------------------------------- #
# Typed payloads
# --------------------------------------------------------------------------- #
class BBox(BaseModel):
    """Normalised bounding box (0..1) plus pixel centre for convenience."""
    x: float = Field(ge=0, le=1)
    y: float = Field(ge=0, le=1)
    w: float = Field(ge=0, le=1)
    h: float = Field(ge=0, le=1)
    cx: float
    cy: float


class TrackStartedPayload(BaseModel):
    type: Literal[EventType.TRACK_STARTED] = EventType.TRACK_STARTED
    track_id: int
    bbox: BBox
    confidence: float = Field(ge=0, le=1)


class TrackEndedPayload(BaseModel):
    type: Literal[EventType.TRACK_ENDED] = EventType.TRACK_ENDED
    track_id: int
    duration_sec: float
    last_zone: str | None = None


class ZoneEnteredPayload(BaseModel):
    type: Literal[EventType.ZONE_ENTERED] = EventType.ZONE_ENTERED
    track_id: int
    zone: str


class ZoneExitedPayload(BaseModel):
    type: Literal[EventType.ZONE_EXITED] = EventType.ZONE_EXITED
    track_id: int
    zone: str
    dwell_sec: float


class LineCrossedPayload(BaseModel):
    type: Literal[EventType.LINE_CROSSED] = EventType.LINE_CROSSED
    track_id: int
    line: str
    direction: Direction


class QueueUpdatePayload(BaseModel):
    type: Literal[EventType.QUEUE_UPDATE] = EventType.QUEUE_UPDATE
    zone: str
    length: int = Field(ge=0)
    avg_wait_sec: float = Field(ge=0)


class OccupancyUpdatePayload(BaseModel):
    type: Literal[EventType.OCCUPANCY_UPDATE] = EventType.OCCUPANCY_UPDATE
    zone: str
    count: int = Field(ge=0)


class AnomalyPayload(BaseModel):
    type: Literal[EventType.ANOMALY] = EventType.ANOMALY
    anomaly_type: AnomalyType
    zone: str | None = None
    severity: float = Field(ge=0, le=1, description="0..1 normalised severity")
    metric: str
    observed: float
    expected: float | None = None
    message: str


Payload = Annotated[
    Union[
        TrackStartedPayload,
        TrackEndedPayload,
        ZoneEnteredPayload,
        ZoneExitedPayload,
        LineCrossedPayload,
        QueueUpdatePayload,
        OccupancyUpdatePayload,
        AnomalyPayload,
    ],
    Field(discriminator="type"),
]


class Event(BaseModel):
    """Canonical event envelope persisted and streamed across the system."""
    schema_version: str = SCHEMA_VERSION
    event_id: str = Field(default_factory=_new_id)
    event_type: EventType
    camera_id: str
    ts: datetime = Field(default_factory=_utcnow)
    payload: Payload

    @classmethod
    def of(cls, camera_id: str, payload: Payload, ts: datetime | None = None) -> "Event":
        return cls(
            event_type=EventType(payload.type),
            camera_id=camera_id,
            ts=ts or _utcnow(),
            payload=payload,
        )


# --------------------------------------------------------------------------- #
# API response models
# --------------------------------------------------------------------------- #
class HealthResponse(BaseModel):
    status: str
    version: str
    stream_backend: str
    detector_backend: str
    pipeline_running: bool
    uptime_sec: float


class ZoneStats(BaseModel):
    zone: str
    occupancy: int
    total_entries: int
    avg_dwell_sec: float
    queue_length: int | None = None
    avg_wait_sec: float | None = None


class LiveMetrics(BaseModel):
    ts: datetime
    store_occupancy: int
    footfall_in: int
    footfall_out: int
    active_tracks: int
    zones: list[ZoneStats]
    open_anomalies: int


class TimeBucket(BaseModel):
    bucket: datetime
    footfall_in: int
    footfall_out: int
    avg_occupancy: float


class AnomalyRecord(BaseModel):
    id: int
    ts: datetime
    camera_id: str
    anomaly_type: AnomalyType
    zone: str | None
    severity: float
    metric: str
    observed: float
    expected: float | None
    message: str
    acknowledged: bool
