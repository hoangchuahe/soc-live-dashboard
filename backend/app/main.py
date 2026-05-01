import asyncio
import json
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware

from .simulator import get_topology, maybe_event, next_metrics
from .threat_intel import fetch_recent_cves
from .mitre_data import TACTICS_ORDER, TECHNIQUES
from . import elastic


@asynccontextmanager
async def lifespan(app: FastAPI):
    await elastic.startup()
    yield


app = FastAPI(title="SOC Live Dashboard API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_events_buffer: list[dict] = []
_tick = 0


# ── Health ────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "elasticsearch": elastic.is_available(),
    }


# ── Topology ──────────────────────────────────────────────────────────────────

@app.get("/api/topology")
async def topology():
    nodes, edges = get_topology()
    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


# ── Events ────────────────────────────────────────────────────────────────────

@app.get("/api/events")
async def events(limit: int = Query(default=50, le=200)):
    return {"events": _events_buffer[-limit:]}


# ── Real CVE feed (NVD API) ───────────────────────────────────────────────────

@app.get("/api/cves")
async def cves(limit: int = Query(default=12, le=20)):
    data = await fetch_recent_cves(limit)
    return {"cves": data, "source": "NVD (nvd.nist.gov)"}


# ── MITRE ATT&CK summary ──────────────────────────────────────────────────────

@app.get("/api/mitre/tactics")
async def mitre_tactics():
    """Returns all tactics with technique counts — used to render the heatmap."""
    counts: dict[str, int] = {t: 0 for t in TACTICS_ORDER}
    for evt in _events_buffer:
        tactic = evt.get("tactic")
        if tactic and tactic in counts:
            counts[tactic] += 1
    return {
        "tactics": [{"name": t, "count": counts[t]} for t in TACTICS_ORDER],
        "techniques": TECHNIQUES,
    }


# ── ElasticSearch search passthrough ─────────────────────────────────────────

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    results = await elastic.search(q)
    return {"results": results, "source": "elasticsearch" if elastic.is_available() else "unavailable"}


# ── WebSocket ─────────────────────────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global _tick
    await websocket.accept()
    try:
        while True:
            _tick += 1
            event = maybe_event()
            if event:
                event_dict = event.model_dump()
                _events_buffer.append(event_dict)
                if len(_events_buffer) > 500:
                    _events_buffer.pop(0)
                # Fire-and-forget to ES
                asyncio.create_task(elastic.index_event(event_dict))

            frame = {
                "tick": _tick,
                "metrics": next_metrics(),
                "event": event.model_dump() if event else None,
            }
            await websocket.send_text(json.dumps(frame))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
