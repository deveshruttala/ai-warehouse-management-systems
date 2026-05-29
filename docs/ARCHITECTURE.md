# Architecture

## 1. Goals & principles

1. **Event-driven** — the system's source of truth is an append-only stream of
   typed events. Analytics, anomaly detection, persistence and the UI are all
   independent consumers. This decouples concerns and makes each piece
   independently testable and scalable.
2. **Pluggable detection** — computer vision is expensive and environment
   specific. The detection source is an interface; the rest of the system
   neither knows nor cares whether observations come from YOLO over real footage
   or from the simulator.
3. **Runs anywhere** — the default path has zero heavy dependencies (no GPU, no
   OpenCV, no video). This keeps the demo reproducible and the repo free of
   media, per the challenge rules.
4. **Production-shaped** — config via env, containerised, durable streaming
   option (Redis Streams), batched writes, healthchecks, graceful shutdown.

## 2. Component walkthrough

### 2.1 Detection & tracking pipeline (`app/pipeline`)
- **`zones.py`** — store layout in normalised `[0,1]` coordinates: aisles, a
  checkout *queue* zone, a *restricted* stock-room, and a vertical **counting
  line** at the entrance for directional footfall.
- **`detector.py`** — `Observation` data model + `YoloSource` which decodes
  frames (OpenCV), runs YOLOv8 person detection (`classes=[0]`), and assigns IDs
  via the tracker. Normalises boxes so downstream logic is resolution-agnostic.
- **`tracker.py`** — dependency-free greedy **IoU tracker** that assigns stable
  `track_id`s and ages out lost tracks. (Swap for ByteTrack/BoT-SORT in prod.)
- **`simulator.py`** — agent-based shopper model producing the same
  `Observation` stream. Maintains a baseline population, routes agents through
  aisles → checkout → exit, and **injects occasional scenarios** (checkout rush,
  aisle crowd surge, restricted-zone intrusion, abandoned dwell) so the anomaly
  detector has realistic signal.
- **`event_gen.py`** — a **state machine** that remembers each track's previous
  position/zone and emits: track lifecycle, zone enter/exit (with dwell),
  directional line crossings.
- **`run_pipeline.py`** — drives the (blocking) frame source in a worker thread,
  marshals observations onto the event loop, converts to events, throttles to
  `SIS_PROCESS_FPS`, and publishes to the bus.

### 2.2 Event schema (`app/schemas.py`)
A single versioned `Event` envelope (`schema_version`, `event_id`, `event_type`,
`camera_id`, `ts`, `payload`). The `payload` is a **Pydantic discriminated
union** keyed on `type`, so consumers get fully-typed payloads and the wire
format self-describes. See [`EVENT_SCHEMA.md`](EVENT_SCHEMA.md).

### 2.3 Streaming (`app/streaming.py`)
`EventBus` interface with `publish` / `subscribe` (async iterator):
- **`InMemoryEventBus`** — per-subscriber asyncio queues with newest-wins
  back-pressure handling. Zero deps; perfect for single-node + tests.
- **`RedisStreamBus`** — `XADD`/`XREAD` over Redis Streams: durable, supports
  many consumers and horizontal scale. Selected via `SIS_STREAM_BACKEND=redis`.

### 2.4 Analytics engine (`app/analytics.py`)
In-memory, continuously updated state derived from the event stream: footfall
in/out, live store + per-zone occupancy, rolling dwell averages, checkout queue
length & estimated wait, and per-minute trend buckets (180-min ring) for charts.
`snapshot()` returns the `LiveMetrics` served by the API and WebSocket.

### 2.5 Anomaly detection (`app/anomaly.py`)
Hybrid approach:
- **Rule-based** (explainable, operational): `zone_intrusion` (instant on
  restricted-zone entry), `long_queue` (checkout length threshold).
- **Statistical** (`RollingStat` z-score): `crowd_surge` (per-zone occupancy),
  `footfall_drop` (per-minute entries), `statistical` (store-occupancy outlier),
  plus `excessive_dwell` (per-individual time-in-zone threshold).
- A per-`(type, zone)` **cooldown** debounces repeated alerts for the same
  condition. Detected anomalies are emitted back onto the bus as `anomaly`
  events, so they are persisted and pushed to dashboards uniformly.

### 2.6 Runtime orchestration (`app/runtime.py`)
Wires everything and is owned by the FastAPI lifespan:
- a **consumer** task: `subscribe()` → analytics ingest → event-driven anomaly
  checks → buffer for persistence;
- a **tick** task (1 Hz): periodic statistical anomaly checks;
- a **flush** task (2 Hz): **batched** DB writes (events + anomalies) to avoid
  per-event transaction overhead;
- the **pipeline** service.

### 2.7 API & dashboard
FastAPI exposes REST + OpenAPI + two WebSockets. The React/Vite dashboard
consumes `/ws/metrics` (live metrics + track positions, ~2 Hz) and `/ws/events`
(raw event firehose), and polls history/anomaly endpoints. The SVG floor map
renders zones, the counting line and live track positions.

## 3. Data model & persistence

`events` is append-only (maps to a **TimescaleDB hypertable** partitioned on
`ts` in production, enabling efficient time-range queries and retention
policies). `anomalies` stores acknowledged-able alerts. Indices cover
`(event_type, ts)` and `(zone, ts)` for the common dashboard/query patterns.

## 4. Scaling path

| Concern | Dev default | Production |
|---------|-------------|------------|
| Streaming | in-memory bus | Redis Streams / Kafka with consumer groups |
| Storage | SQLite | TimescaleDB / Postgres (hypertable + retention) |
| Detection | simulator | YOLO on GPU workers, one per camera, publishing to the bus |
| API | single uvicorn | multiple stateless replicas behind a load balancer |
| Dashboard | Vite dev server | static build behind nginx/CDN |

Because cameras publish events independently and consumers are stateless w.r.t.
the bus, the pipeline scales horizontally by camera and the API by replica.

## 5. Failure handling

- WebSocket clients auto-reconnect (frontend hook) with newest-wins buffering.
- DB writes are batched and isolated in try/except so a write hiccup never stalls
  the real-time path.
- Pipeline runs in a supervised asyncio task; the source exhausting (finite
  video) stops cleanly. Redis disconnects surface on the next `XREAD`.

## 6. AI-assisted engineering decisions

This solution was developed with AI pair-programming. The most impactful
AI-assisted choices:

1. **Pluggable detector + simulator fallback.** Rather than hard-coupling to a
   specific model/footage, we designed an `Observation` interface and a
   simulator that emits the identical stream. This made the whole system
   demonstrable without media (satisfying the no-video rule) and kept CV deps
   optional — a pragmatic decision for portability and review.
2. **Discriminated-union event schema with a versioned envelope.** Chosen for
   forward-compatibility and to give every consumer strong typing for free,
   instead of passing around loose dicts.
3. **Hybrid anomaly detection (rules + rolling z-score) with cooldowns.** Pure
   thresholds are brittle and pure ML is opaque/overkill here; combining
   explainable rules with adaptive statistical baselines — and debouncing
   alerts — gives operationally useful, low-noise detection.
4. **Event bus abstraction with memory/Redis backends.** Lets the same code run
   trivially in dev and scale to durable multi-consumer streaming in prod.
5. **Batched, decoupled persistence.** Keeps the real-time analytics path off the
   database write latency.
