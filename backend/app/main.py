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
import os
from collections import deque
from contextlib import asynccontextmanager
from datetime import UTC, datetime, timedelta

from fastapi import Body, Depends, FastAPI, HTTPException, Query, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse

from . import db, elastic, metrics
from .auth import (
    LoginRequest,
    LoginResponse,
    UserInfo,
    authenticate,
    create_access_token,
    current_user,
    require_admin,
)
from .detection import DetectionEngine, load_rules
from .hub import ConnectionHub
from .mitre_data import TACTICS_ORDER, TECHNIQUES
from .producer import Producer
from .query import ParseError, evaluate, parse
from .risk import RiskTracker
from .simulator import get_topology
from .sources import build_metrics_provider, build_sources
from .threat_intel import fetch_recent_cves

# ── Globals ───────────────────────────────────────────────────────────────────

risk_tracker = RiskTracker()
detection_engine = DetectionEngine(load_rules(), risk_tracker)

# Ring buffer — last N events for replay on reconnect (lightweight WAL)
_event_buffer: deque[dict] = deque(maxlen=500)
_alert_buffer: deque[dict] = deque(maxlen=200)

hub = ConnectionHub()
_producer: Producer | None = None
_producer_task: asyncio.Task | None = None
_mode: str = "blend"            # actual value resolved from SOC_MODE in lifespan()
_source_statuses: list = []


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

    # Build sources for the configured mode and start the single producer.
    global _producer, _producer_task, _source_statuses, _mode
    _mode = os.getenv("SOC_MODE", "blend")
    sources, _source_statuses = build_sources(_mode)
    metrics_provider = build_metrics_provider(_mode)
    _producer = Producer(
        sources=sources,
        metrics_provider=metrics_provider,
        engine=detection_engine,
        hub=hub,
        event_buffer=_event_buffer,
        alert_buffer=_alert_buffer,
        persist_event=db.persist_event,
        index_event=elastic.index_event,
        create_alert_lifecycle=db.create_alert_lifecycle,
    )
    active = ", ".join(s.name for s in sources) or "none"
    print(f"[startup] SOC_MODE={_mode}; active sources: {active}")
    _producer_task = asyncio.create_task(_producer.run_forever())

    yield

    # Shutdown: stop the producer cleanly.
    if _producer is not None:
        _producer.stop()
    if _producer_task is not None:
        _producer_task.cancel()
        try:
            await _producer_task
        except (asyncio.CancelledError, Exception):
            pass


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
    # Merge startup preflight status with the producer's live failure tracking:
    # a source that fails repeatedly at runtime is reported unavailable + degraded.
    runtime = _producer.source_status() if _producer is not None else {}
    sources = []
    for st in _source_statuses:
        r = runtime.get(st.name)
        degraded = bool(r and r["degraded"])
        sources.append({
            "name": st.name,
            "available": st.available and not degraded,
            "detail": (
                f"degraded: {r['consecutive_failures']} consecutive poll failures"
                if degraded and r else st.detail
            ),
        })
    return {
        "status": "ok",
        "mode": _mode,
        "sources": sources,
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


# ── Search (DSL over SQLite ring) + ES passthrough ────────────────────────────

def _parse_window(from_q: str | None, to_q: str | None) -> tuple[datetime, datetime]:
    to_ts = datetime.fromisoformat(to_q.replace("Z", "+00:00")) if to_q else datetime.now(UTC)
    from_ts = (
        datetime.fromisoformat(from_q.replace("Z", "+00:00")) if from_q
        else to_ts - timedelta(minutes=15)
    )
    return from_ts, to_ts


@app.get("/api/search", tags=["Telemetry"])
async def search(
    q: str = Query(..., min_length=1),
    from_: str | None = Query(None, alias="from"),
    to:    str | None = Query(None),
    limit: int = Query(100, le=500),
):
    """DSL search over persisted events. Time window defaults to last 15 minutes."""
    try:
        ast = parse(q)
    except ParseError as exc:
        raise HTTPException(
            status_code=400,
            detail={"detail": exc.detail, "position": exc.position},
        ) from exc

    from_ts, to_ts = _parse_window(from_, to)
    results = await db.search_events(
        predicate=lambda e: evaluate(ast, e),
        from_ts=from_ts,
        to_ts=to_ts,
        limit=limit,
    )
    return {
        "results": results,
        "matched": len(results),
        "from": from_ts.isoformat(),
        "to": to_ts.isoformat(),
        "source": "sqlite",
    }


@app.get("/api/search/es", tags=["Telemetry"])
async def search_es(q: str = Query(..., min_length=1)):
    """Raw ElasticSearch passthrough — only useful when --profile elastic is up."""
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
    await websocket.accept()
    await hub.register(websocket)
    metrics.websocket_clients.set(hub.count)
    try:
        # The Producer broadcasts frames; this coroutine just keeps the socket
        # open and waits for the client to disconnect.
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        pass
    finally:
        hub.unregister(websocket)
        metrics.websocket_clients.set(hub.count)
