import asyncio
import json
from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from .simulator import get_topology, maybe_event, next_metrics

app = FastAPI(title="SOC Live Dashboard API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

_events_buffer: list[dict] = []
_tick = 0


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/api/topology")
async def topology():
    nodes, edges = get_topology()
    return {
        "nodes": [n.model_dump() for n in nodes],
        "edges": [e.model_dump() for e in edges],
    }


@app.get("/api/events")
async def events():
    return {"events": _events_buffer[-50:]}


@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global _tick
    await websocket.accept()
    try:
        while True:
            _tick += 1
            event = maybe_event()
            if event:
                _events_buffer.append(event.model_dump())
                if len(_events_buffer) > 200:
                    _events_buffer.pop(0)

            frame = {
                "tick": _tick,
                "metrics": next_metrics(),
                "event": event.model_dump() if event else None,
            }
            await websocket.send_text(json.dumps(frame))
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        pass
