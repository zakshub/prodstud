"""Shared test fixtures isolating every test run into an ephemeral tmp_path workspace."""

from __future__ import annotations

import io
from pathlib import Path

import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prodstud.api.app import create_app
from prodstud.config import Settings
from prodstud.runtime import AppRuntime


@pytest.fixture()
def test_settings(tmp_path: Path) -> Settings:
    return Settings.from_env(data_dir_override=tmp_path / "data", env_override="test")


@pytest.fixture()
def runtime(test_settings: Settings) -> AppRuntime:
    return AppRuntime.create(test_settings)


@pytest.fixture()
def client(test_settings: Settings) -> TestClient:
    app = create_app(test_settings)
    return TestClient(app)


@pytest.fixture()
def sample_png_bytes() -> bytes:
    img = Image.new("RGB", (640, 480), (140, 120, 100))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()
