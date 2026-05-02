"""
SOC Live Dashboard — main FastAPI application.

Pipeline per WebSocket tick:

    Simulator.maybe_event()
            │
            ▼
    Raw ECS event ──► DetectionEngine.evaluate()
            │                       │
            │                       ├─► matches selection? threshold met?
            │                       ▼
            │                  Detection (ECS alert)
            │                       │
            │                       ├─► RiskTracker.bump(entity, weight)
            │                       └─► metrics.detections_fired.inc()
            │
            ▼
    Frame { metrics, event, alerts[] } ──► WebSocket clients
                                       └─► ElasticSearch (best-effort)
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Query
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import elastic, metrics
from .detection import DetectionEngine, load_rules
from .mitre_data import TACTICS_ORDER, TECHNIQUES
from .risk import RiskTracker
from .simulator import get_topology, maybe_event, next_metrics
from .threat_intel import fetch_recent_cves


# ── Globals ───────────────────────────────────────────────────────────────────

risk_tracker = RiskTracker()
detection_engine = DetectionEngine(load_rules(), risk_tracker)

# Ring buffer — last N events for replay on reconnect (lightweight WAL)
_event_buffer: deque[dict] = deque(maxlen=500)
_alert_buffer: deque[dict] = deque(maxlen=200)

_tick = 0


# ── App lifecycle ─────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    print(f"[startup] loaded {len(detection_engine.rules)} detection rules")
    await elastic.startup()
    yield


app = FastAPI(
    title="SOC Live Dashboard API",
    version="3.0.0",
    description=(
        "Real-time security telemetry pipeline with Sigma-style detection rules, "
        "risk-based alerting, and ECS-formatted events."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health & metrics ──────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {
        "status": "ok",
        "elasticsearch": elastic.is_available(),
        "rules_loaded": len(detection_engine.rules),
        "events_buffered": len(_event_buffer),
        "alerts_buffered": len(_alert_buffer),
    }


@app.get("/metrics", response_class=PlainTextResponse)
async def prometheus_metrics():
    return metrics.render()


# ── Topology ──────────────────────────────────────────────────────────────────

@app.get("/api/topology")
async def topology():
    nodes, edges = get_topology()
    return {"nodes": nodes, "edges": edges}


# ── Events / alerts (with replay cursor) ──────────────────────────────────────

@app.get("/api/events")
async def events(
    limit: int = Query(50, le=500),
    since: str | None = Query(None, description="event.id cursor — return events after this id"),
):
    items = list(_event_buffer)
    if since:
        for i, e in enumerate(items):
            if e.get("event", {}).get("id") == since:
                items = items[i + 1 :]
                break
    return {"events": items[-limit:], "total_buffered": len(_event_buffer)}


@app.get("/api/alerts")
async def alerts(limit: int = Query(50, le=200)):
    return {"alerts": list(_alert_buffer)[-limit:]}


# ── Detection rules ───────────────────────────────────────────────────────────

@app.get("/api/rules")
async def rules():
    return {"rules": detection_engine.rule_summary()}


# ── Risk-Based Alerting ───────────────────────────────────────────────────────

@app.get("/api/risk/top")
async def risk_top(n: int = Query(10, le=50)):
    return {"entities": risk_tracker.top(n)}


# ── Threat intel (real CVEs from NVD) ─────────────────────────────────────────

@app.get("/api/cves")
async def cves(limit: int = Query(12, le=20)):
    data = await fetch_recent_cves(limit)
    return {"cves": data, "source": "NVD (services.nvd.nist.gov)"}


# ── MITRE ATT&CK heatmap ──────────────────────────────────────────────────────

@app.get("/api/mitre/tactics")
async def mitre_tactics():
    counts = {t: 0 for t in TACTICS_ORDER}
    for evt in _event_buffer:
        tactic = evt.get("threat", {}).get("tactic", {})
        if tactic and (name := tactic.get("name")) in counts:
            counts[name] += 1
    return {
        "tactics": [{"name": t, "count": counts[t]} for t in TACTICS_ORDER],
        "techniques": TECHNIQUES,
    }


# ── ElasticSearch passthrough search ──────────────────────────────────────────

@app.get("/api/search")
async def search(q: str = Query(..., min_length=1)):
    results = await elastic.search(q)
    return {
        "results": results,
        "source": "elasticsearch" if elastic.is_available() else "unavailable",
    }


# ── WebSocket — live frame stream ─────────────────────────────────────────────

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    global _tick
    await websocket.accept()
    metrics.websocket_clients.set(metrics.websocket_clients._value + 1)

    try:
        while True:
            _tick += 1

            event = maybe_event()
            fired_alerts: list[dict] = []

            if event:
                _event_buffer.append(event)
                metrics.events_ingested.inc(
                    category=event["event"]["category"],
                    severity=event["event"]["severity"],
                )

                # Run through detection engine
                detections = detection_engine.evaluate(event)
                for det in detections:
                    alert = det.to_ecs()
                    fired_alerts.append(alert)
                    _alert_buffer.append(alert)
                    metrics.detections_fired.inc(
                        rule_id=det.rule_id,
                        tactic=det.tactic or "unknown",
                    )

                # Best-effort ES indexing (never blocks the tick)
                asyncio.create_task(elastic.index_event(event))
                for alert in fired_alerts:
                    asyncio.create_task(elastic.index_event(alert))

            frame = {
                "tick": _tick,
                "metrics": next_metrics(),
                "event": event,
                "alerts": fired_alerts,
            }
            await websocket.send_text(json.dumps(frame, default=str))
            await asyncio.sleep(1)

    except WebSocketDisconnect:
        pass
    finally:
        metrics.websocket_clients.set(max(0, metrics.websocket_clients._value - 1))
