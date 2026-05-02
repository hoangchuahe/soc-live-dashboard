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
                                       └─► SQLite (persistent buffer)
"""

from __future__ import annotations

import asyncio
import json
from collections import deque
from contextlib import asynccontextmanager

from fastapi import Body, Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import db, elastic, metrics
from .auth import (
    LoginRequest, LoginResponse, UserInfo,
    authenticate, create_access_token, current_user, require_admin,
)
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
    await db.init_db()
    print("[startup] sqlite initialised")
    await elastic.startup()

    # Backfill in-memory ring buffers from sqlite so reconnecting clients get
    # context across restarts
    try:
        recent = await db.recent_events(limit=200)
        for e in recent:
            _event_buffer.append(e)
        recent_alerts = await db.recent_events(limit=100, kind="alert")
        for a in recent_alerts:
            _alert_buffer.append(a)
        print(f"[startup] backfilled {len(_event_buffer)} events + {len(_alert_buffer)} alerts from sqlite")
    except Exception as exc:
        print(f"[startup] backfill skipped: {exc}")

    yield


app = FastAPI(
    title="SOC Live Dashboard API",
    version="4.0.0",
    description=(
        "Real-time security telemetry pipeline with Sigma-style detection rules, "
        "risk-based alerting, ECS-formatted events, JWT auth + RBAC, and SQLite persistence."
    ),
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)


# ── Health & metrics (public) ─────────────────────────────────────────────────

@app.get("/health", tags=["Health"])
async def health():
    return {
        "status": "ok",
        "elasticsearch": elastic.is_available(),
        "rules_loaded": len(detection_engine.rules),
        "events_buffered": len(_event_buffer),
        "alerts_buffered": len(_alert_buffer),
    }


@app.get("/metrics", response_class=PlainTextResponse, tags=["Health"])
async def prometheus_metrics():
    return metrics.render()


# ── Auth ──────────────────────────────────────────────────────────────────────

@app.post("/api/auth/login", response_model=LoginResponse, tags=["Auth"])
async def login(payload: LoginRequest):
    role = authenticate(payload.username, payload.password)
    if not role:
        raise HTTPException(status_code=401, detail="Invalid credentials")
    token, ttl = create_access_token(payload.username, role)
    return LoginResponse(access_token=token, role=role, expires_in=ttl)


@app.get("/api/auth/me", response_model=UserInfo, tags=["Auth"])
async def whoami(user: UserInfo = Depends(current_user)):
    return user


# ── Topology ──────────────────────────────────────────────────────────────────

@app.get("/api/topology", tags=["Telemetry"])
async def topology():
    nodes, edges = get_topology()
    return {"nodes": nodes, "edges": edges}


# ── Events / alerts (with replay cursor) ──────────────────────────────────────

@app.get("/api/events", tags=["Telemetry"])
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


@app.get("/api/alerts", tags=["Telemetry"])
async def alerts(limit: int = Query(50, le=200)):
    return {"alerts": list(_alert_buffer)[-limit:]}


# ── Alert lifecycle (auth required) ──────────────────────────────────────────

@app.get("/api/alerts/lifecycle", tags=["Alerts"])
async def alerts_lifecycle(status: str | None = None, limit: int = Query(50, le=200)):
    return {"items": await db.list_alert_lifecycle(status, limit)}


@app.post("/api/alerts/{alert_id}/ack", tags=["Alerts"])
async def ack_alert(
    alert_id: str,
    note: str | None = Body(default=None, embed=True),
    user: UserInfo = Depends(current_user),
):
    """Any authenticated user (Tier 1 analyst) can acknowledge."""
    ok = await db.update_alert_status(alert_id, "ack", assignee=user.username, note=note)
    if not ok:
        await db.create_alert_lifecycle(alert_id)
        await db.update_alert_status(alert_id, "ack", assignee=user.username, note=note)
    return {"alert_id": alert_id, "status": "ack", "assignee": user.username}


@app.post("/api/alerts/{alert_id}/close", tags=["Alerts"])
async def close_alert(
    alert_id: str,
    note: str | None = Body(default=None, embed=True),
    user: UserInfo = Depends(require_admin),
):
    """Only Tier 2 / admin can close an alert."""
    ok = await db.update_alert_status(alert_id, "closed", assignee=user.username, note=note)
    if not ok:
        await db.create_alert_lifecycle(alert_id)
        await db.update_alert_status(alert_id, "closed", assignee=user.username, note=note)
    return {"alert_id": alert_id, "status": "closed", "assignee": user.username}


# ── Detection rules ───────────────────────────────────────────────────────────

@app.get("/api/rules", tags=["Detection"])
async def rules():
    return {"rules": detection_engine.rule_summary()}


@app.post("/api/rules/reload", tags=["Detection"])
async def reload_rules(user: UserInfo = Depends(require_admin)):
    """Hot-reload detection rules from disk. Admin only."""
    new_rules = load_rules()
    detection_engine.rules = new_rules
    return {"reloaded": len(new_rules), "by": user.username}


# ── Risk-Based Alerting ───────────────────────────────────────────────────────

@app.get("/api/risk/top", tags=["Detection"])
async def risk_top(n: int = Query(10, le=50)):
    return {"entities": risk_tracker.top(n)}


# ── Threat intel (real CVEs from NVD) ─────────────────────────────────────────

@app.get("/api/cves", tags=["Threat Intel"])
async def cves(limit: int = Query(12, le=20)):
    data = await fetch_recent_cves(limit)
    return {"cves": data, "source": "NVD (services.nvd.nist.gov)"}


# ── MITRE ATT&CK heatmap ──────────────────────────────────────────────────────

@app.get("/api/mitre/tactics", tags=["Detection"])
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

@app.get("/api/search", tags=["Telemetry"])
async def search(q: str = Query(..., min_length=1)):
    results = await elastic.search(q)
    return {
        "results": results,
        "source": "elasticsearch" if elastic.is_available() else "unavailable",
    }


# ── Admin: maintenance ────────────────────────────────────────────────────────

@app.post("/api/admin/prune", tags=["Admin"])
async def prune(days: int = Query(7, ge=1, le=90), user: UserInfo = Depends(require_admin)):
    deleted = await db.prune_old_events(days)
    return {"deleted": deleted, "days": days, "by": user.username}


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

                # Persist to SQLite + ES (best-effort, never blocks the tick)
                asyncio.create_task(db.persist_event(event))
                asyncio.create_task(elastic.index_event(event))
                for alert in fired_alerts:
                    asyncio.create_task(db.persist_event(alert))
                    asyncio.create_task(db.create_alert_lifecycle(alert["event"]["id"]))
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
