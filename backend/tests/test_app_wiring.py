"""App boots, /health reports sources, and the producer is wired up."""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SOC_MODE"] = "demo"

from fastapi.testclient import TestClient  # noqa: E402

from app.main import app  # noqa: E402


def test_health_reports_mode_and_sources():
    with TestClient(app) as client:          # triggers lifespan startup
        resp = client.get("/health")
        assert resp.status_code == 200
        body = resp.json()
        assert body["mode"] == "demo"
        assert "sources" in body
        assert body["status"] == "ok"
