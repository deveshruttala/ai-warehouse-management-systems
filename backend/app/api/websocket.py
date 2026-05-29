"""WebSocket endpoints for real-time push."""
from __future__ import annotations

import asyncio
import contextlib
import logging

from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from ..analytics import get_engine
from ..runtime import get_runtime
from ..streaming import get_bus

router = APIRouter(tags=["realtime"])
log = logging.getLogger("sis.ws")


@router.websocket("/ws/events")
async def ws_events(ws: WebSocket) -> None:
    """Stream every domain event as it is produced."""
    await ws.accept()
    bus = get_bus()
    try:
        async for event in bus.subscribe():
            await ws.send_text(event.model_dump_json())
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.debug("ws/events closed", exc_info=True)


@router.websocket("/ws/metrics")
async def ws_metrics(ws: WebSocket) -> None:
    """Push a live metrics + track-position snapshot a few times per second."""
    await ws.accept()
    engine = get_engine()
    rt = get_runtime()
    try:
        while True:
            payload = {
                "metrics": engine.snapshot().model_dump(mode="json"),
                "tracks": rt.pipeline.latest_tracks,
            }
            await ws.send_json(payload)
            await asyncio.sleep(0.5)
    except WebSocketDisconnect:
        pass
    except Exception:  # noqa: BLE001
        log.debug("ws/metrics closed", exc_info=True)
    finally:
        with contextlib.suppress(Exception):
            await ws.close()
