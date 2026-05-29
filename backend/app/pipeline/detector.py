"""Detection sources.

A *source* yields, on each tick, the list of currently tracked people as
:class:`Observation` records (normalised coordinates + stable ``track_id``).

Two sources are provided:

* :class:`YoloSource`   - real CCTV: decodes video frames, runs a YOLO person
  detector and the :class:`IoUTracker`. Requires the optional CV dependencies
  (``requirements-cv.txt``) and a video/RTSP source.
* :class:`SimulatorSource` (in ``simulator.py``) - synthesises realistic shopper
  trajectories so the whole platform runs with zero media files.
"""
from __future__ import annotations

import logging
from dataclasses import dataclass
from typing import Iterator, Protocol

log = logging.getLogger("sis.detector")


@dataclass
class Observation:
    track_id: int
    cx: float  # normalised centre x [0,1]
    cy: float  # normalised centre y [0,1]
    x: float   # normalised bbox top-left x
    y: float   # normalised bbox top-left y
    w: float   # normalised width
    h: float   # normalised height
    confidence: float


class FrameSource(Protocol):
    name: str

    def frames(self) -> Iterator[list[Observation]]:
        """Yield observations per processed frame until the stream ends."""
        ...


class YoloSource:
    """Real detection + tracking over a video file or RTSP stream."""

    name = "yolo"

    def __init__(self, video_source: str, model: str = "yolov8n.pt", conf: float = 0.35):
        self.video_source = video_source
        self.model_name = model
        self.conf = conf

    def frames(self) -> Iterator[list[Observation]]:
        import cv2  # type: ignore  # lazy import (optional dep)
        from ultralytics import YOLO  # type: ignore

        from .tracker import IoUTracker

        model = YOLO(self.model_name)
        tracker = IoUTracker()
        cap = cv2.VideoCapture(self.video_source)
        if not cap.isOpened():
            raise RuntimeError(f"Could not open video source: {self.video_source!r}")
        try:
            while True:
                ok, frame = cap.read()
                if not ok:
                    break
                fh, fw = frame.shape[:2]
                result = model.predict(frame, classes=[0], conf=self.conf, verbose=False)[0]
                boxes_px: list[tuple[float, float, float, float]] = []
                confs: list[float] = []
                for b in result.boxes:
                    x0, y0, x1, y1 = (float(v) for v in b.xyxy[0].tolist())
                    boxes_px.append((x0, y0, x1, y1))
                    confs.append(float(b.conf[0]))
                tracked = tracker.update(boxes_px)
                obs: list[Observation] = []
                for i, (tid, (x0, y0, x1, y1)) in enumerate(tracked):
                    obs.append(
                        Observation(
                            track_id=tid,
                            cx=((x0 + x1) / 2) / fw,
                            cy=((y0 + y1) / 2) / fh,
                            x=x0 / fw,
                            y=y0 / fh,
                            w=(x1 - x0) / fw,
                            h=(y1 - y0) / fh,
                            confidence=confs[i] if i < len(confs) else self.conf,
                        )
                    )
                yield obs
        finally:
            cap.release()
