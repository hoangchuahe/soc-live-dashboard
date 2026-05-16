"""Integration tests for /api/search backed by the DSL + SQLite."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from httpx import ASGITransport, AsyncClient  # noqa: E402
from sqlalchemy import delete  # noqa: E402

from app import db  # noqa: E402
from app.db import StoredEvent  # noqa: E402
from app.main import app  # noqa: E402


def _event(eid: str, source_ip: str, severity: str, ts: datetime) -> dict:
    return {
        "@timestamp": ts.isoformat().replace("+00:00", "Z"),
        "event": {"id": eid, "kind": "event", "category": "authentication",
                  "severity": severity, "outcome": "failure"},
        "source": {"ip": source_ip},
        "host": {"name": "WKS-01"},
        "message": "test",
    }


@pytest.fixture(autouse=True)
async def _seed():
    await db.init_db()
    # Wipe all events so cross-module test data doesn't bleed through
    async with db.get_session() as s:
        await s.execute(delete(StoredEvent))
        await s.commit()
    now = datetime.now(UTC)
    await db.persist_event(_event("a", "10.0.0.5", "high", now - timedelta(minutes=1)))
    await db.persist_event(_event("b", "10.0.0.6", "low",  now - timedelta(minutes=1)))


async def test_search_matches_by_ip():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:"10.0.0.5"'})
    assert r.status_code == 200
    body = r.json()
    ids = [e["event"]["id"] for e in body["results"]]
    assert ids == ["a"]
    assert body["source"] == "sqlite"
    assert body["matched"] == 1


async def test_parse_error_returns_400_with_position():
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:'})
    assert r.status_code == 400
    body = r.json()
    assert "detail" in body                 # FastAPI wrapper
    inner = body["detail"]
    assert "detail" in inner and "position" in inner


async def test_default_window_is_15_minutes():
    now = datetime.now(UTC)
    await db.persist_event(_event("old", "10.0.0.5", "high", now - timedelta(hours=2)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:"10.0.0.5"'})
    ids = [e["event"]["id"] for e in r.json()["results"]]
    assert "old" not in ids
    assert "a" in ids


async def test_limit_param_honoured():
    now = datetime.now(UTC)
    for i in range(10):
        await db.persist_event(_event(f"x{i}", "10.0.0.7", "high",
                                      now - timedelta(seconds=i)))
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://t") as ac:
        r = await ac.get('/api/search', params={"q": 'source.ip:"10.0.0.7"', "limit": 3})
    assert len(r.json()["results"]) == 3
