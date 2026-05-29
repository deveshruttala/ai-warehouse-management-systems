"""Real-time analytics & store-layout endpoints."""
from __future__ import annotations

from fastapi import APIRouter, Query

from ..analytics import get_engine
from ..pipeline.zones import DEFAULT_LAYOUT
from ..runtime import get_runtime
from ..schemas import LiveMetrics, TimeBucket, ZoneStats

router = APIRouter(prefix="/api", tags=["analytics"])


@router.get("/live/metrics", response_model=LiveMetrics)
async def live_metrics() -> LiveMetrics:
    """Current store-wide and per-zone metrics."""
    return get_engine().snapshot()


@router.get("/live/tracks")
async def live_tracks() -> dict:
    """Current tracked positions (for the live floor map)."""
    rt = get_runtime()
    return {"camera_id": rt.pipeline.event_gen.camera_id, "tracks": rt.pipeline.latest_tracks}


@router.get("/analytics/zones", response_model=list[ZoneStats])
async def zone_stats() -> list[ZoneStats]:
    return get_engine().snapshot().zones


@router.get("/analytics/history", response_model=list[TimeBucket])
async def history(minutes: int = Query(60, ge=1, le=180)) -> list[TimeBucket]:
    """Per-minute footfall and average occupancy for the last ``minutes``."""
    return get_engine().history(minutes)


@router.get("/layout")
async def layout() -> dict:
    """Static store layout (zones + counting lines) for the dashboard."""
    return {
        "zones": [
            {
                "name": z.name,
                "label": z.label or z.name,
                "kind": z.kind,
                "x0": z.x0,
                "y0": z.y0,
                "x1": z.x1,
                "y1": z.y1,
            }
            for z in DEFAULT_LAYOUT.zones
        ],
        "lines": [
            {"name": ln.name, "x": ln.x, "inward_is_right": ln.inward_is_right}
            for ln in DEFAULT_LAYOUT.lines
        ],
    }
