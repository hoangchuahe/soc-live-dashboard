# SOC Live Dashboard

A real-time Security Operations Centre dashboard that streams live telemetry over WebSocket and renders it with custom D3.js visualisations — no page refresh, no polling.

Built as a portfolio project to demonstrate the combination of skills I used at PNO (real-time WebSocket ingestion + D3 force graphs + async Python) in a single runnable repo.

![Dashboard preview](https://via.placeholder.com/1200x630/020617/06b6d4?text=SOC+Live+Dashboard)

---

## What it shows

| Panel | What's happening |
|---|---|
| **Stats bar** | Live CPU, memory, disk, network I/O, active connections — updates every second |
| **Metrics chart** | D3 time-series with dual-line (CPU/memory) + gradient area fill, last 60 seconds |
| **Network topology** | D3 force-directed graph — draggable nodes, risk rings pulsing on high-risk assets |
| **Event timeline** | D3 time-axis — security events plotted by timestamp, hover for detail |
| **Alert feed** | Scrolling list of events with severity badges (low / medium / high / critical) |

All panels update in real time as the WebSocket pushes frames from the backend.

---

## Tech stack

| Layer | Choice | Why |
|---|---|---|
| Backend | **FastAPI** (Python 3.12) | Async-first, native WebSocket support, auto OpenAPI |
| Data | In-memory simulation | No DB dependency — clone and run immediately |
| Frontend | **React 18 + TypeScript** | Component model fits panel-based dashboard layout |
| Visualisation | **D3.js v7** | Full control over force simulation, axis, area/line generators |
| Styling | **Tailwind CSS** | Dark theme utility classes without a design system dependency |
| Dev infra | **Docker Compose** | One-command setup, nginx reverse-proxies WebSocket to backend |

---

## Quick start

### Option A — Docker (recommended)

```bash
git clone https://github.com/YOUR_USERNAME/soc-live-dashboard.git
cd soc-live-dashboard
docker compose up --build
```

Open **http://localhost:3000** — the dashboard will start streaming immediately.

### Option B — Local dev

**Backend**
```bash
cd backend
python -m venv .venv
# Windows:
.venv\Scripts\activate
# macOS/Linux:
source .venv/bin/activate

pip install -r requirements.txt
uvicorn app.main:app --reload --port 8000
```

**Frontend** (separate terminal)
```bash
cd frontend
npm install
npm run dev
```

Open **http://localhost:5173**

---

## Architecture

```
Browser
  │
  ├── GET /api/topology ──────────────► FastAPI
  ├── GET /api/events ────────────────► FastAPI
  └── WebSocket /ws ──────────────────► FastAPI
                                           │
                                    Simulator (in-memory)
                                    ├── Random-walk metrics (CPU, mem…)
                                    ├── Stochastic event generator (18% / tick)
                                    └── Static network topology
```

The frontend maintains a **60-point rolling buffer** for the metrics chart and a **100-event buffer** for the alert feed and timeline — both managed in React state without any global store.

The WebSocket hook (`src/hooks/useWebSocket.ts`) auto-reconnects with a 3-second backoff, so the dashboard recovers transparently if the backend restarts.

### D3 integration pattern

Each visualisation is a React component that owns a `<svg>` ref. On every data update, `useEffect` tears down and redraws the D3 scene — this avoids the complexity of reconciling D3's internal state with React's, at the cost of a full redraw per tick. For 60 data points this is imperceptible; for production-scale data I would switch to an incremental update pattern using D3's `join()` enter/update/exit.

---

## Key design decisions

**WebSocket over polling** — A 1 Hz polling loop would work, but WebSocket eliminates the HTTP handshake overhead and lets the server push events exactly when they occur. This was the same reason I chose WebSocket at PNO for security telemetry ingestion.

**D3 force simulation** — The network topology uses `d3.forceSimulation` with `forceManyBody`, `forceLink`, and `forceCollide`. This produces organic layouts that communicate network structure intuitively, which is exactly what a SOC analyst needs to trace lateral movement paths. Nodes are draggable so analysts can rearrange the layout to match their mental model.

**Risk rings** — Each network node has an outer ring coloured green/orange/red based on a `risk` score (0–1). Critical-risk nodes (>0.7) get a CSS `pulse-ring` animation so they draw the eye without a modal or alert sound.

**No Redux / Zustand** — Three `useState` hooks (metrics history, events buffer, topology) are sufficient. Adding a global store would be premature for this scope.

---

## Extending this project

- **Real data source** — swap the simulator for an ElasticSearch query or a syslog ingestion pipeline (exactly what I built at PNO)
- **Authentication** — add JWT + RBAC middleware to the FastAPI app; I implemented a similar RBAC system for Tier 1/2 SOC analyst roles
- **Geospatial overlay** — add a D3 geo projection panel to map `source_ip` to lat/long (I built this at PNO using D3 + a MaxMind DB lookup)
- **Alerting** — POST to a webhook / Slack when `severity === 'critical'` events exceed a threshold
- **Persistence** — replace the in-memory buffer with PostgreSQL + TimescaleDB for time-series retention

---

## About

Built by **Pham Nhat Hoang** — full-stack engineer specialising in Python back-end systems and React/D3 frontends.

- Email: phamnhathoang091@gmail.com
- GitHub: [github.com/YOUR_USERNAME](https://github.com/YOUR_USERNAME)
- LinkedIn: [linkedin.com/in/YOUR_PROFILE](https://linkedin.com/in/YOUR_PROFILE)
