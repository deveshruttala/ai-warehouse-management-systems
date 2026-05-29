"""FastAPI application entrypoint for the Store Intelligence System."""
from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from . import __version__
from .config import settings
from .database import init_db
from .runtime import get_runtime
from .schemas import HealthResponse

logging.basicConfig(
    level=getattr(logging, settings.log_level.upper(), logging.INFO),
    format="%(asctime)s %(levelname)-7s %(name)s | %(message)s",
)
log = logging.getLogger("sis")


@asynccontextmanager
async def lifespan(app: FastAPI):
    await init_db()
    runtime = get_runtime()
    await runtime.start()
    log.info("Store Intelligence System v%s ready.", __version__)
    try:
        yield
    finally:
        await runtime.stop()


app = FastAPI(
    title="Store Intelligence System",
    version=__version__,
    description=(
        "End-to-end store intelligence over CCTV: detection & tracking pipeline, "
        "event streaming, real-time analytics, anomaly detection and live dashboard APIs."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Routers
from .api import analytics, anomalies, events, websocket  # noqa: E402

app.include_router(analytics.router)
app.include_router(events.router)
app.include_router(anomalies.router)
app.include_router(websocket.router)


@app.get("/health", response_model=HealthResponse, tags=["system"])
async def health() -> HealthResponse:
    rt = get_runtime()
    return HealthResponse(
        status="ok",
        version=__version__,
        stream_backend=settings.stream_backend,
        detector_backend=rt.pipeline.backend,
        pipeline_running=rt.pipeline.running,
        uptime_sec=round(rt.uptime, 1),
    )


@app.get("/", tags=["system"])
async def root() -> JSONResponse:
    return JSONResponse(
        {
            "name": "Store Intelligence System",
            "version": __version__,
            "docs": "/docs",
            "health": "/health",
            "websockets": ["/ws/events", "/ws/metrics"],
        }
    )
