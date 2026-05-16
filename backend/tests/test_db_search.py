"""Tests for db.search_events — in-memory SQLite + predicate application."""

from __future__ import annotations

import os
from datetime import UTC, datetime, timedelta

import pytest

# Force an isolated in-memory DB before importing the module
os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"

from app import db  # noqa: E402
from app.query import evaluate, parse  # noqa: E402


def _event(eid: str, source_ip: str, severity: str, ts: datetime) -> dict:
    return {
        "@timestamp": ts.isoformat().replace("+00:00", "Z"),
        "event": {"id": eid, "kind": "event", "category": "authentication",
                  "severity": severity, "outcome": "failure"},
        "source": {"ip": source_ip},
        "host": {"name": "WKS-01"},
        "message": f"event {eid}",
    }


@pytest.fixture(autouse=True)
async def _init():
    await db.init_db()


async def test_search_events_filters_by_predicate_and_window():
    now = datetime.now(UTC)
    await db.persist_event(_event("a", "10.0.0.5", "high", now - timedelta(minutes=2)))
    await db.persist_event(_event("b", "10.0.0.6", "low",  now - timedelta(minutes=2)))
    await db.persist_event(_event("c", "10.0.0.5", "high", now - timedelta(hours=2)))  # outside window

    ast = parse('source.ip:"10.0.0.5"')
    results = await db.search_events(
        predicate=lambda e: evaluate(ast, e),
        from_ts=now - timedelta(minutes=10),
        to_ts=now,
        limit=50,
    )
    ids = [r["event"]["id"] for r in results]
    assert ids == ["a"]


async def test_search_events_honours_limit():
    now = datetime.now(UTC)
    for i in range(5):
        await db.persist_event(_event(f"e{i}", "10.0.0.5", "high",
                                      now - timedelta(seconds=i)))
    ast = parse('source.ip:"10.0.0.5"')
    results = await db.search_events(
        predicate=lambda e: evaluate(ast, e),
        from_ts=now - timedelta(minutes=1),
        to_ts=now + timedelta(seconds=1),
        limit=3,
    )
    assert len(results) == 3
