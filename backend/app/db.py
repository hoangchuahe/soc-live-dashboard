"""
SQLite persistence layer.

Survives backend restarts so demo state isn't lost. Schema mirrors the ECS
event shape — columns named after their ECS field paths so queries are
intuitive.

For production this would move to PostgreSQL (TimescaleDB for events,
Postgres for risk/alerts/users). The async SQLAlchemy interface used here
swaps drivers with a config change.
"""

from __future__ import annotations

import json
import os
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from datetime import datetime, timezone
from pathlib import Path

from sqlalchemy import (
    Column, DateTime, Float, Integer, String, Text, select, delete, func,
)
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine
from sqlalchemy.orm import DeclarativeBase

DB_URL = os.getenv("DATABASE_URL", f"sqlite+aiosqlite:///{Path(__file__).parent.parent}/soc.db")

engine = create_async_engine(DB_URL, echo=False, future=True)
SessionLocal = async_sessionmaker(engine, class_=AsyncSession, expire_on_commit=False)


class Base(DeclarativeBase):
    pass


class StoredEvent(Base):
    __tablename__ = "events"
    event_id    = Column(String, primary_key=True)
    timestamp   = Column(DateTime, nullable=False, index=True)
    kind        = Column(String, nullable=False, index=True)   # event | alert
    category    = Column(String, nullable=False, index=True)
    severity    = Column(String, nullable=False, index=True)
    source_ip   = Column(String, index=True)
    host_name   = Column(String, index=True)
    technique   = Column(String, index=True)                   # MITRE technique ID
    rule_id     = Column(String, index=True, nullable=True)    # set on alerts only
    message     = Column(Text)
    raw_json    = Column(Text, nullable=False)                  # full ECS payload


class StoredRiskScore(Base):
    __tablename__ = "risk_scores"
    entity        = Column(String, primary_key=True)
    score         = Column(Float, nullable=False)
    last_updated  = Column(DateTime, nullable=False)
    rule_count    = Column(Integer, nullable=False, default=0)


class AlertLifecycle(Base):
    __tablename__ = "alert_lifecycle"
    alert_id  = Column(String, primary_key=True)
    status    = Column(String, nullable=False, default="new")  # new | ack | in_progress | closed
    assignee  = Column(String, nullable=True)
    created   = Column(DateTime, nullable=False)
    updated   = Column(DateTime, nullable=False)
    note      = Column(Text, nullable=True)


# ── Session helper ────────────────────────────────────────────────────────────

@asynccontextmanager
async def get_session() -> AsyncGenerator[AsyncSession, None]:
    async with SessionLocal() as session:
        yield session


async def init_db() -> None:
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)


# ── Event helpers ─────────────────────────────────────────────────────────────

async def persist_event(event: dict) -> None:
    """Insert an ECS event into the events table. Best-effort — no exceptions."""
    try:
        async with get_session() as s:
            ev = event.get("event", {})
            stored = StoredEvent(
                event_id  = ev.get("id", ""),
                timestamp = datetime.fromisoformat(event["@timestamp"].replace("Z", "+00:00"))
                            if event.get("@timestamp") else datetime.now(timezone.utc),
                kind      = ev.get("kind", "event"),
                category  = ev.get("category", "unknown"),
                severity  = ev.get("severity", "low"),
                source_ip = (event.get("source") or {}).get("ip"),
                host_name = (event.get("host")   or {}).get("name"),
                technique = ((event.get("threat") or {}).get("technique") or {}).get("id"),
                rule_id   = (event.get("rule")   or {}).get("id"),
                message   = event.get("message", ""),
                raw_json  = json.dumps(event, default=str),
            )
            s.add(stored)
            await s.commit()
    except Exception:
        # never let persistence kill the live pipeline
        pass


async def recent_events(limit: int = 50, kind: str | None = None) -> list[dict]:
    async with get_session() as s:
        stmt = select(StoredEvent).order_by(StoredEvent.timestamp.desc()).limit(limit)
        if kind:
            stmt = select(StoredEvent).where(StoredEvent.kind == kind).order_by(StoredEvent.timestamp.desc()).limit(limit)
        result = await s.execute(stmt)
        rows = result.scalars().all()
        return [json.loads(r.raw_json) for r in reversed(rows)]


async def event_counts_by_severity() -> dict[str, int]:
    async with get_session() as s:
        stmt = select(StoredEvent.severity, func.count(StoredEvent.event_id)).group_by(StoredEvent.severity)
        result = await s.execute(stmt)
        return {sev: count for sev, count in result.all()}


# ── Risk persistence ──────────────────────────────────────────────────────────

async def persist_risk_score(entity: str, score: float, rule_count: int) -> None:
    try:
        async with get_session() as s:
            existing = await s.get(StoredRiskScore, entity)
            now = datetime.now(timezone.utc)
            if existing:
                existing.score = score
                existing.last_updated = now
                existing.rule_count = rule_count
            else:
                s.add(StoredRiskScore(
                    entity=entity, score=score, rule_count=rule_count, last_updated=now,
                ))
            await s.commit()
    except Exception:
        pass


# ── Alert lifecycle ───────────────────────────────────────────────────────────

async def create_alert_lifecycle(alert_id: str) -> None:
    try:
        async with get_session() as s:
            existing = await s.get(AlertLifecycle, alert_id)
            if existing:
                return
            now = datetime.now(timezone.utc)
            s.add(AlertLifecycle(alert_id=alert_id, status="new", created=now, updated=now))
            await s.commit()
    except Exception:
        pass


async def update_alert_status(alert_id: str, status: str, assignee: str | None = None,
                              note: str | None = None) -> bool:
    valid_statuses = {"new", "ack", "in_progress", "closed"}
    if status not in valid_statuses:
        return False
    async with get_session() as s:
        record = await s.get(AlertLifecycle, alert_id)
        if not record:
            return False
        record.status = status
        record.updated = datetime.now(timezone.utc)
        if assignee:
            record.assignee = assignee
        if note:
            record.note = note
        await s.commit()
        return True


async def list_alert_lifecycle(status: str | None = None, limit: int = 50) -> list[dict]:
    async with get_session() as s:
        stmt = select(AlertLifecycle).order_by(AlertLifecycle.updated.desc()).limit(limit)
        if status:
            stmt = select(AlertLifecycle).where(AlertLifecycle.status == status).order_by(
                AlertLifecycle.updated.desc()).limit(limit)
        result = await s.execute(stmt)
        return [
            {
                "alert_id": r.alert_id, "status": r.status, "assignee": r.assignee,
                "created": r.created.isoformat(), "updated": r.updated.isoformat(),
                "note": r.note,
            }
            for r in result.scalars().all()
        ]


async def prune_old_events(days: int = 7) -> int:
    """Delete events older than `days`. Returns count deleted."""
    cutoff = datetime.now(timezone.utc).timestamp() - (days * 86400)
    cutoff_dt = datetime.fromtimestamp(cutoff, tz=timezone.utc)
    async with get_session() as s:
        stmt = delete(StoredEvent).where(StoredEvent.timestamp < cutoff_dt)
        result = await s.execute(stmt)
        await s.commit()
        return result.rowcount or 0
