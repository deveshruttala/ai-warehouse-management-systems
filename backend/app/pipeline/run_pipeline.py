"""Pipeline service: drives a detection source and publishes domain events.

Runs the (blocking) frame source in a worker thread and marshals each frame's
observations back onto the event loop, where they are converted to events and
published to the streaming bus. Throttled to ``SIS_PROCESS_FPS``.
"""
from __future__ import annotations

import asyncio
import logging
import threading
import time
from typing import Iterator

from ..config import settings
from ..streaming import EventBus
from .detector import Observation, YoloSource
from .event_gen import EventGenerator
from .simulator import SimulatorSource
from .zones import DEFAULT_LAYOUT

log = logging.getLogger("sis.pipeline")


def _build_source():
    backend = settings.detector_backend
    has_video = bool(settings.video_source)

    def _try_yolo():
        try:
            import cv2  # noqa: F401
            import ultralytics  # noqa: F401
        except Exception as exc:  # pragma: no cover - optional dep
            raise RuntimeError(
                "YOLO backend requested but CV dependencies are missing. "
                "Install with: pip install -r requirements-cv.txt"
            ) from exc
        return YoloSource(settings.video_source, settings.yolo_model, settings.yolo_conf)

    if backend == "yolo":
        return _try_yolo(), "yolo"
    if backend == "simulator":
        return SimulatorSource(DEFAULT_LAYOUT, settings.sim_people, settings.sim_speed), "simulator"

    # auto
    if has_video:
        try:
            return _try_yolo(), "yolo"
        except RuntimeError as exc:
            log.warning("Falling back to simulator: %s", exc)
    return SimulatorSource(DEFAULT_LAYOUT, settings.sim_people, settings.sim_speed), "simulator"


class PipelineService:
    def __init__(self, bus: EventBus):
        self.bus = bus
        self.event_gen = EventGenerator(settings.camera_id, DEFAULT_LAYOUT)
        self.backend = "none"
        self.running = False
        self.latest_tracks: list[dict] = []
        self._task: asyncio.Task | None = None
        self._frames: Iterator[list[Observation]] | None = None
        self._stop = threading.Event()

    async def start(self) -> None:
        source, backend = _build_source()
        self.backend = backend
        self._frames = source.frames()
        self.running = True
        self._stop.clear()
        self._task = asyncio.create_task(self._run(), name="pipeline")
        log.info("Pipeline started with backend=%s camera=%s", backend, settings.camera_id)

    async def stop(self) -> None:
        self.running = False
        self._stop.set()
        if self._task:
            self._task.cancel()
            try:
                await self._task
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass

    def _next_frame(self) -> list[Observation] | None:
        assert self._frames is not None
        try:
            return next(self._frames)
        except StopIteration:
            return None

    async def _run(self) -> None:
        loop = asyncio.get_running_loop()
        period = 1.0 / max(settings.process_fps, 0.5)
        while self.running and not self._stop.is_set():
            t0 = time.perf_counter()
            obs = await loop.run_in_executor(None, self._next_frame)
            if obs is None:
                log.info("Frame source exhausted; pipeline stopping.")
                self.running = False
                break
            self.latest_tracks = [
                {"track_id": o.track_id, "cx": round(o.cx, 4), "cy": round(o.cy, 4),
                 "w": round(o.w, 4), "h": round(o.h, 4)}
                for o in obs
            ]
            for event in self.event_gen.process(obs):
                await self.bus.publish(event)
            elapsed = time.perf_counter() - t0
            await asyncio.sleep(max(0.0, period - elapsed))
