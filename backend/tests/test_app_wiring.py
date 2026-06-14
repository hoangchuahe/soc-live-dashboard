"""App boots, /health reports sources, and the producer is wired up."""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SOC_MODE"] = "demo"

from fastapi.testclient import TestClient  # noqa: E402

from app import main  # noqa: E402
from app.main import app  # noqa: E402
from app.sources.base import SourceStatus  # noqa: E402


def test_health_reports_mode_and_sources():
    with TestClient(app) as client:          # triggers lifespan startup
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "demo"
        assert "sources" in body
        assert body["status"] == "ok"


async def test_health_reflects_runtime_degraded_source(monkeypatch):
    """A source that fails repeatedly at runtime is reported unavailable + degraded."""

    class _FakeProducer:
        def source_status(self):
            return {"host.network": {"degraded": True, "consecutive_failures": 4}}

    monkeypatch.setattr(main, "_producer", _FakeProducer())
    monkeypatch.setattr(
        main, "_source_statuses",
        [SourceStatus(name="host.network", available=True, detail="ok")],
    )

    body = await main.health()
    src = next(s for s in body["sources"] if s["name"] == "host.network")
    assert src["available"] is False
    assert "degraded" in src["detail"]
    assert "4" in src["detail"]
