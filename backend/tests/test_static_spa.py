"""mount_spa() serves the built SPA at / without shadowing API routes."""

from __future__ import annotations

import os

os.environ["DATABASE_URL"] = "sqlite+aiosqlite:///:memory:"
os.environ["SOC_MODE"] = "demo"

from fastapi import FastAPI  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

from app.main import mount_spa  # noqa: E402


def test_mount_spa_returns_false_when_dir_missing(tmp_path):
    missing = tmp_path / "nope"
    assert mount_spa(FastAPI(), str(missing)) is False


def test_mount_spa_serves_index_and_does_not_shadow_routes(tmp_path):
    (tmp_path / "index.html").write_text("<!doctype html><html>SPA OK</html>")

    app = FastAPI()

    @app.get("/health")
    def health():
        return {"status": "ok"}

    # Mount AFTER routes are registered, mirroring main.py ordering.
    assert mount_spa(app, str(tmp_path)) is True

    client = TestClient(app)
    # API route still wins — not shadowed by the "/" mount.
    assert client.get("/health").json() == {"status": "ok"}
    # Root serves the SPA index.
    root = client.get("/")
    assert root.status_code == 200
    assert "SPA OK" in root.text
