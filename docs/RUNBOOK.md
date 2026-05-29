# Runbook (raw commands, no `make`)

## Prerequisites
- Python 3.12 (3.11/3.13 also fine). 3.14 works for the core but the optional
  CV stack may lack wheels — use 3.12 if you intend to run real YOLO.
- Node.js 18+.

## Backend

```bash
python3.12 -m venv .venv
. .venv/bin/activate
pip install -U pip
pip install -r backend/requirements.txt

cd backend
uvicorn app.main:app --reload --port 8000
```

- API docs: http://localhost:8000/docs
- Health:   http://localhost:8000/health

## Frontend

```bash
cd frontend
npm install
npm run dev          # http://localhost:5173 (proxies /api and /ws to :8000)
```

If port 5173 is occupied (or a stale service worker from another project is
registered on that origin), use a different port:

```bash
npm run dev -- --port 5199 --host
```

## Tests

```bash
cd backend
../.venv/bin/python -m pytest -q
```

## Run with Redis Streams instead of the in-memory bus

```bash
docker run -p 6379:6379 redis:7-alpine        # or use docker compose
export SIS_STREAM_BACKEND=redis
export SIS_REDIS_URL=redis://localhost:6379/0
uvicorn app.main:app --port 8000
```

## Run on real CCTV footage (optional)

```bash
pip install -r backend/requirements-cv.txt
export SIS_DETECTOR_BACKEND=yolo
export SIS_VIDEO_SOURCE=/absolute/path/to/footage.mp4   # or rtsp://…
uvicorn app.main:app --port 8000
```

## Full stack via Docker

```bash
docker compose up --build
# dashboard → http://localhost:8080 ; api → http://localhost:8000/docs
docker compose down
```

## Common issues

| Symptom | Fix |
|---------|-----|
| `No module named 'greenlet'` | `pip install greenlet` (already pinned in requirements) |
| Dashboard shows a different app | Stale service worker on `localhost:5173`; run the dev server on another port (`--port 5199`) or unregister the SW in DevTools → Application |
| `ws://…/ws/metrics` not connecting | Ensure the backend is on :8000 and CORS/proxy is configured (default Vite proxy handles it) |
| No anomalies appear | Let it run ~30–60s; raise `SIS_SIM_PEOPLE`/`SIS_SIM_SPEED` to generate load faster |
