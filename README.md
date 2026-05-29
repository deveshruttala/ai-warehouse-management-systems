# Store Intelligence System

> **Purplle Tech Challenge 2026 — Round 2**
> An end-to-end **Store Intelligence System** that turns raw CCTV footage into
> real-time operational insight: a detection & tracking pipeline, an event
> streaming backbone, live analytics, anomaly detection, production-ready APIs,
> and a live dashboard.

<p align="center"><em>Detect → Track → Stream events → Analyse → Detect anomalies → Visualise</em></p>

---

## Why this design

Retail CCTV is a firehose of pixels. The value is in **events** — _who entered_,
_which aisle they browsed_, _how long the checkout queue is_, _is someone in a
restricted area_. This system is built around a clean **event-driven
architecture** so each concern is decoupled and independently scalable:

```
 ┌──────────────┐   Observations   ┌──────────────┐   Events    ┌─────────────┐
 │  Detection   │ ───────────────▶ │   Event      │ ─────────▶  │  Streaming  │
 │  & Tracking  │  (YOLO + IoU /   │  Generator   │  (typed,    │  Bus        │
 │  Pipeline    │   Simulator)     │ (state mach.)│  versioned) │ (mem/Redis) │
 └──────────────┘                  └──────────────┘             └──────┬──────┘
                                                                       │
                  ┌────────────────────────────────────────────────────┼───────────────┐
                  ▼                         ▼                            ▼               ▼
          ┌──────────────┐         ┌──────────────┐            ┌──────────────┐  ┌─────────────┐
          │  Analytics   │         │   Anomaly    │            │  Persistence │  │  WebSocket  │
          │  Engine      │         │   Detector   │            │ (events +    │  │  fan-out    │
          │ (footfall,   │         │ (rules +     │            │  anomalies)  │  │  to clients │
          │  occupancy,  │         │  z-score)    │            │  SQLite/TS   │  └──────┬──────┘
          │  dwell, queue)│        └──────┬───────┘            └──────────────┘         │
          └──────┬───────┘                │ anomaly events                              │
                 │  REST snapshots         └────────────▶ (back onto the bus)            │
                 ▼                                                                       ▼
        ┌───────────────────────────────────────────────────────────────────────────────────┐
        │                         React Live Dashboard (Vite + TS)                            │
        │   stat cards · live floor map · footfall/occupancy trends · zone table · alerts     │
        └───────────────────────────────────────────────────────────────────────────────────┘
```

A key engineering decision: the pipeline is **pluggable**. It runs a real
**YOLO + tracker** over a video/RTSP source when the optional CV dependencies and
footage are available, and otherwise falls back to a **high-fidelity shopper
simulator** that emits the _exact same observation stream_. This means the
entire platform is fully demonstrable **without any video files** — which,
per the challenge rules, must not be committed to the repository.

---

## Features

| Area | What's implemented |
|------|--------------------|
| **Detection & tracking** | YOLOv8 person detection + greedy IoU multi-object tracker; pluggable simulator backend producing the same `Observation` stream |
| **Event schema** | Versioned `Event` envelope with discriminated, strongly-typed payloads (`track.*`, `zone.*`, `line.crossed`, `queue.update`, `occupancy.update`, `anomaly`) |
| **Event streaming** | Pub/sub bus with two backends: in-process asyncio fan-out (`memory`) and **Redis Streams** (`redis`) for durability & horizontal scale |
| **Real-time analytics** | Footfall (directional line crossings), live store + per-zone occupancy, dwell-time, checkout queue length & estimated wait, per-minute trend buckets |
| **Anomaly detection** | Rule-based (intrusion, long queue) + statistical (rolling-window z-score) for crowd surge, excessive dwell, footfall drop, occupancy outliers — with cooldown debouncing |
| **APIs** | FastAPI REST (`/api/...`) + OpenAPI docs (`/docs`) + WebSockets (`/ws/events`, `/ws/metrics`) + `/health` |
| **Live dashboard** | React + TypeScript + Tailwind + Recharts: stat cards, SVG floor map with moving tracks, trend charts, zone analytics, anomaly alerts with acknowledge, live event ticker |
| **Production readiness** | Dockerised stack, `docker compose`, healthchecks, batched DB writes, config via env, graceful startup/shutdown, test suite |

---

## Quick start

### Option A — Local dev (no Docker, no GPU, no video)

```bash
# 0. Prereqs: Python 3.12 and Node 18+ recommended.
make setup            # creates .venv, installs backend + frontend deps

# 1. Run the backend (API + pipeline + simulator) on :8000
make backend

# 2. In another terminal, run the dashboard on :5173
make frontend
```

Open the dashboard at **http://localhost:5173** and the API docs at
**http://localhost:8000/docs**.

> Don't have `make`? See [`docs/RUNBOOK.md`](docs/RUNBOOK.md) for the raw commands.

### Option B — Full stack via Docker (includes Redis Streams)

```bash
docker compose up --build
```

- Dashboard → **http://localhost:8080**
- API / docs → **http://localhost:8000/docs**

### Option C — Run on REAL CCTV footage (optional)

```bash
make setup-cv                                  # installs ultralytics + opencv
export SIS_DETECTOR_BACKEND=yolo
export SIS_VIDEO_SOURCE=/path/to/your/footage.mp4   # or an rtsp:// URL
make backend
```

The YOLO model weights download on first run and are **git-ignored**. Footage is
never committed.

---

## Configuration

All settings are environment variables prefixed with `SIS_` (see
[`.env.example`](.env.example)). Highlights:

| Variable | Default | Description |
|----------|---------|-------------|
| `SIS_DETECTOR_BACKEND` | `auto` | `auto` \| `yolo` \| `simulator` |
| `SIS_VIDEO_SOURCE` | _(empty)_ | Video file path or RTSP URL for YOLO backend |
| `SIS_STREAM_BACKEND` | `memory` | `memory` \| `redis` |
| `SIS_DATABASE_URL` | `sqlite+aiosqlite:///./store_intelligence.db` | Any async SQLAlchemy URL (use TimescaleDB/Postgres in prod) |
| `SIS_SIM_PEOPLE` | `18` | Concurrent simulated shoppers |
| `SIS_QUEUE_ALERT_LEN` | `6` | Checkout queue length that triggers an alert |
| `SIS_DWELL_ALERT_SEC` | `180` | Dwell time (s) that triggers an alert |
| `SIS_ANOMALY_ZSCORE` | `3.0` | Z-score threshold for statistical anomalies |

---

## API summary

| Method | Path | Description |
|--------|------|-------------|
| `GET` | `/health` | Service & pipeline status |
| `GET` | `/api/live/metrics` | Current store + per-zone metrics |
| `GET` | `/api/live/tracks` | Current tracked positions (floor map) |
| `GET` | `/api/analytics/zones` | Per-zone analytics |
| `GET` | `/api/analytics/history?minutes=60` | Per-minute footfall & occupancy |
| `GET` | `/api/layout` | Store layout (zones + counting lines) |
| `GET` | `/api/events?limit=&event_type=&zone=&since=` | Query the event log |
| `GET` | `/api/events/stats` | Event counts by type |
| `GET` | `/api/anomalies?acknowledged=&anomaly_type=` | List anomalies |
| `POST` | `/api/anomalies/{id}/ack` | Acknowledge an anomaly |
| `WS` | `/ws/events` | Stream every domain event |
| `WS` | `/ws/metrics` | Push live metrics + track positions (~2 Hz) |

Full event schema reference: [`docs/EVENT_SCHEMA.md`](docs/EVENT_SCHEMA.md).
Architecture deep-dive: [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md).

---

## Project layout

```
.
├── backend/                  # FastAPI service + pipeline
│   ├── app/
│   │   ├── main.py           # app factory + lifespan
│   │   ├── config.py         # env-driven settings
│   │   ├── schemas.py        # EVENT SCHEMA (Pydantic, versioned, discriminated)
│   │   ├── database.py       # async SQLAlchemy
│   │   ├── models.py         # ORM (events, anomalies)
│   │   ├── streaming.py      # event bus (memory / Redis Streams)
│   │   ├── analytics.py      # real-time analytics engine
│   │   ├── anomaly.py        # rule + statistical anomaly detection
│   │   ├── runtime.py        # orchestration (consumer, persistence, ticks)
│   │   ├── api/              # REST + WebSocket routers
│   │   └── pipeline/         # zones, detector (YOLO), tracker, simulator, event-gen
│   └── tests/                # pytest suite
├── frontend/                 # React + TS + Tailwind dashboard (Vite)
├── docs/                     # architecture, event schema, runbook
├── docker-compose.yml        # full stack (redis + backend + frontend)
└── Makefile                  # one-command workflows
```

---

## Testing

```bash
make test     # 11 tests: schema round-trips, event-gen, analytics, anomaly logic
```

---

## AI-assisted engineering notes

This project was built with AI pair-programming. Notable AI-assisted decisions
are documented in [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md#ai-assisted-engineering-decisions),
including the pluggable detector design, the discriminated-union event schema,
and the hybrid rule + statistical anomaly approach.

---

## Notes on the dataset / video rule

Per the challenge rules, **no dataset or video files are committed**. The
`.gitignore` explicitly excludes `data/`, `datasets/`, `videos/`, all common
video/image/model-weight extensions, and the local SQLite DB. The simulator
makes the system fully runnable and reviewable without any media.
