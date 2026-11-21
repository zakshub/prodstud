"""Tests for Level 1 CLI (prodstud) ensuring full API-independent operational execution."""

from __future__ import annotations

import json
from pathlib import Path

from prodstud.cli import main


def test_cli_full_image_workflow_and_snapshot(tmp_path: Path, capsys) -> None:
    data_dir = str(tmp_path / "cli_data")

    assert main(["--data-dir", data_dir, "--env", "test", "init-db"]) == 0
    out = json.loads(capsys.readouterr().out)
    assert out["integrity"] == "ok"

    assert main(["--data-dir", data_dir, "--env", "test", "register", "--email", "cli@studio.local", "--name", "CLI Op", "--password", "CliPass123!"]) == 0
    capsys.readouterr()

    assert main(["--data-dir", data_dir, "--env", "test", "project", "create", "--email", "cli@studio.local", "--name", "CLI Project"]) == 0
    prj = json.loads(capsys.readouterr().out)

    assert main([
        "--data-dir", data_dir, "--env", "test", "plan",
        "--email", "cli@studio.local",
        "--project-id", prj["id"],
        "--media-type", "image",
        "--prompt", "Sculptural glass carafe on concrete plinth",
        "--aspect-ratio", "4:5",
        "--provider", "local_test_fixture",
        "--model", "local-optical-slate-v1",
    ]) == 0
    plan = json.loads(capsys.readouterr().out)

    # Without --approve, must return awaiting_explicit_approval quote only!
    assert main([
        "--data-dir", data_dir, "--env", "test", "generate",
        "--email", "cli@studio.local",
        "--plan-id", plan["id"],
    ]) == 0
    pending = json.loads(capsys.readouterr().out)
    assert pending["status"] == "awaiting_explicit_approval"

    # With --approve, executes cleanly
    assert main([
        "--data-dir", data_dir, "--env", "test", "generate",
        "--email", "cli@studio.local",
        "--plan-id", plan["id"],
        "--approve",
    ]) == 0
    done = json.loads(capsys.readouterr().out)
    assert done["job"]["status"] == "succeeded"
    asset_id = done["asset"]["id"]

    # Export ZIP via CLI
    export_zip = tmp_path / "cli_export.zip"
    assert main([
        "--data-dir", data_dir, "--env", "test", "export",
        "--email", "cli@studio.local",
        "--asset-id", asset_id,
        "--out", str(export_zip),
    ]) == 0
    capsys.readouterr()
    assert export_zip.exists() and export_zip.stat().st_size > 500

    # Atomic snapshot via CLI
    assert main(["--data-dir", data_dir, "--env", "test", "snapshot"]) == 0
    snap = json.loads(capsys.readouterr().out)
    assert snap["integrity"] == "ok"
