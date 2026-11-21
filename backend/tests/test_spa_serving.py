"""Verify compiled SPA root serves HTML cleanly when frontend/dist exists."""

from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient


def test_spa_root_serves_frontend_when_built(client: TestClient) -> None:
    dist_index = Path(__file__).resolve().parents[2] / "frontend" / "dist" / "index.html"
    if not dist_index.exists():
        return
    resp = client.get("/")
    assert resp.status_code == 200
    assert "Production Studio" in resp.text
    assert resp.headers.get("x-frame-options") == "DENY"
    assert resp.headers.get("x-content-type-options") == "nosniff"
