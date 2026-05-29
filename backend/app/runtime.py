"""Runtime orchestration.

Wires the streaming bus, analytics engine, anomaly detector and pipeline
together and exposes a single :class:`Runtime` object with ``start``/``stop``
managed by the FastAPI lifespan.

Data flow::

    pipeline ──publish──▶  bus  ──▶ consumer ──▶ persist (events)
                                         │
                                         ├──▶ analytics.ingest()
                                         ├──▶ anomaly.on_event()  ─┐
                                         └──▶ persist (anomalies)  │
                                                                   ▼
    tick loop ──▶ anomaly.on_tick() ──▶ publish anomaly events ──▶ bus
"""
from __future__ import annotations

import asyncio
import logging
import time
from datetime import datetime, timezone

from .analytics import AnalyticsEngine, get_engine
from .anomaly import AnomalyDetector, get_detector
from .database import SessionLocal
from .models import AnomalyRecordModel, EventRecord
from .pipeline.run_pipeline import PipelineService
from .schemas import Event, EventType
from .streaming import EventBus, get_bus

log = logging.getLogger("sis.runtime")


class Runtime:
    def __init__(self) -> None:
        self.bus: EventBus = get_bus()
        self.engine: AnalyticsEngine = get_engine()
        self.detector: AnomalyDetector = get_detector()
        self.pipeline = PipelineService(self.bus)
        self.started_at = time.time()
        self._buffer: list[Event] = []
        self._tasks: list[asyncio.Task] = []
        self._running = False

    # ------------------------------------------------------------------ #
    async def start(self) -> None:
        await self.bus.start()
        self._running = True
        self._tasks = [
            asyncio.create_task(self._consume(), name="consumer"),
            asyncio.create_task(self._flush_loop(), name="db-flush"),
            asyncio.create_task(self._tick_loop(), name="anomaly-tick"),
        ]
        await self.pipeline.start()
        log.info("Runtime started.")

    async def stop(self) -> None:
        self._running = False
        await self.pipeline.stop()
        for t in self._tasks:
            t.cancel()
        for t in self._tasks:
            try:
                await t
            except (asyncio.CancelledError, Exception):  # noqa: BLE001
                pass
        await self._flush()  # persist whatever remains
        await self.bus.stop()
        log.info("Runtime stopped.")

    # ------------------------------------------------------------------ #
    async def _consume(self) -> None:
        async for event in self.bus.subscribe():
            try:
                self.engine.ingest(event)
                self._buffer.append(event)
                if event.event_type != EventType.ANOMALY:
                    for payload in self.detector.on_event(event):
                        await self.bus.publish(Event.of(event.camera_id, payload))
            except Exception:  # noqa: BLE001
                log.exception("Error consuming event")

    async def _tick_loop(self) -> None:
        while self._running:
            await asyncio.sleep(1.0)
            try:
                now = datetime.now(timezone.utc)
                for payload in self.detector.on_tick(self.engine, now):
                    await self.bus.publish(Event.of(self.pipeline.event_gen.camera_id, payload))
            except Exception:  # noqa: BLE001
                log.exception("Error in anomaly tick")

    async def _flush_loop(self) -> None:
        while self._running:
            await asyncio.sleep(0.5)
            await self._flush()

    async def _flush(self) -> None:
        if not self._buffer:
            return
        batch, self._buffer = self._buffer, []
        try:
            async with SessionLocal() as session:
                for ev in batch:
                    p = ev.payload
                    session.add(
                        EventRecord(
                            event_id=ev.event_id,
                            event_type=ev.event_type.value,
                            camera_id=ev.camera_id,
                            ts=ev.ts,
                            zone=getattr(p, "zone", None),
                            track_id=getattr(p, "track_id", None),
                            payload=p.model_dump_json(),
                        )
                    )
                    if ev.event_type == EventType.ANOMALY:
                        session.add(
                            AnomalyRecordModel(
                                ts=ev.ts,
                                camera_id=ev.camera_id,
                                anomaly_type=p.anomaly_type.value,
                                zone=p.zone,
                                severity=p.severity,
                                metric=p.metric,
                                observed=p.observed,
                                expected=p.expected,
                                message=p.message,
                            )
                        )
                await session.commit()
        except Exception:  # noqa: BLE001
            log.exception("Failed to flush %d events", len(batch))

    @property
    def uptime(self) -> float:
        return time.time() - self.started_at


_runtime: Runtime | None = None


def get_runtime() -> Runtime:
    global _runtime
    if _runtime is None:
        _runtime = Runtime()
    return _runtime
