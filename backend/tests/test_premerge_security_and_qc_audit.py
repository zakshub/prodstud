"""Pre-Merge Security Hardening, Engine Isolation, Controlled Vision QC Audit & Integrity Regression Suite."""

from __future__ import annotations

import ast
import dataclasses
import importlib.util
import io
import json
import sys
import zipfile
from pathlib import Path

import httpx
import pytest
from fastapi.testclient import TestClient
from PIL import Image

from prodstud.api.app import create_app
from prodstud.config import Settings
from prodstud.domain.enums import JobStatus
from prodstud.engine.vision_qc import VisionQCService
from prodstud.providers.google_vision_qc import GoogleVisionQCAdapter
from prodstud.storage.asset_store import AssetStore, MediaValidationError


REPO_ROOT = Path(__file__).resolve().parents[2]


def _png_bytes(size: tuple[int, int] = (64, 64), color: tuple[int, int, int] = (100, 120, 140)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", size, color).save(buf, format="PNG")
    return buf.getvalue()


def _make_client(tmp_path: Path, **cfg_overrides: object) -> tuple[TestClient, object]:
    cfg = Settings.from_env(data_dir_override=str(tmp_path / "data"), env_override="test")
    if cfg_overrides:
        cfg = dataclasses.replace(cfg, **cfg_overrides)
    app = create_app(cfg)
    return TestClient(app), app.state.runtime


def _register(client: TestClient, email: str, password: str = "StrongPass!2026") -> dict:
    r = client.post("/api/auth/register", json={"email": email, "display_name": email.split("@")[0], "password": password})
    assert r.status_code in {200, 201}, r.text
    return r.json()


def test_engine_has_zero_provider_imports() -> None:
    """Enforce non-negotiable rule: Production Intelligence Engine stays strictly independent of providers/."""
    engine_dir = REPO_ROOT / "backend" / "src" / "prodstud" / "engine"
    py_files = sorted(engine_dir.rglob("*.py"))
    assert len(py_files) >= 5
    violations: list[str] = []
    for py_file in py_files:
        tree = ast.parse(py_file.read_text(encoding="utf-8"), filename=str(py_file))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    if alias.name.startswith("prodstud.providers"):
                        violations.append(f"{py_file.name}: import {alias.name}")
            elif isinstance(node, ast.ImportFrom):
                if node.module and node.module.startswith("prodstud.providers"):
                    violations.append(f"{py_file.name}: from {node.module} import ...")
    assert violations == [], f"Engine/provider boundary violated: {violations}"


def test_auth_omits_raw_token_from_json_and_sets_httponly_cookie(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    reg = client.post(
        "/api/auth/register",
        json={"email": "owner@studio.test", "display_name": "Owner", "password": "StrongPass!2026"},
    )
    assert reg.status_code in {200, 201}
    assert "token" not in reg.json()
    set_cookie = reg.headers.get("set-cookie", "").lower()
    assert "httponly" in set_cookie
    assert "samesite=lax" in set_cookie

    client.post("/api/auth/logout")

    # Wrong email and wrong password both return clean 401 without leaking user existence
    bad_email = client.post("/api/auth/login", json={"email": "ghost@studio.test", "password": "WrongPassword!9"})
    assert bad_email.status_code == 401
    bad_pw = client.post("/api/auth/login", json={"email": "owner@studio.test", "password": "WrongPassword!9"})
    assert bad_pw.status_code == 401
    assert bad_email.json()["detail"] == bad_pw.json()["detail"]

    ok_login = client.post("/api/auth/login", json={"email": "owner@studio.test", "password": "StrongPass!2026"})
    assert ok_login.status_code == 200
    assert "token" not in ok_login.json()


def test_csrf_middleware_blocks_cross_origin_cookie_mutations(tmp_path: Path) -> None:
    client, _ = _make_client(tmp_path)
    _register(client, "csrf@studio.test")

    # Cross-origin cookie-authenticated POST MUST be blocked with 403
    evil = client.post(
        "/api/projects",
        json={"name": "Evil Forged Project"},
        headers={"Origin": "https://evil.example"},
    )
    assert evil.status_code == 403
    assert "Cross-origin" in evil.json()["detail"]

    # Same-origin cookie-authenticated POST MUST succeed
    legit = client.post(
        "/api/projects",
        json={"name": "Legitimate Project"},
        headers={"Origin": "http://testserver"},
    )
    assert legit.status_code == 201


def test_atomic_quote_consumption_prevents_replay(tmp_path: Path) -> None:
    client, rt = _make_client(tmp_path)
    me = _register(client, "atomic@studio.test")
    uid = me["user"]["id"]
    pid = client.post("/api/projects", json={"name": "Atomic Quote Project"}).json()["id"]

    plan_resp = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "image",
            "prompt_text": "Matte ceramic mug on travertine counter",
            "aspect_ratio": "3:2",
            "provider_id": "local_test_fixture",
            "model_id": "local-optical-slate-v1",
        },
    )
    assert plan_resp.status_code == 201, plan_resp.text
    plan = plan_resp.json()

    q = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-optical-slate-v1"},
    ).json()

    # First atomic consumption succeeds; second replay fails
    assert rt.repo.consume_quote_atomically(uid, q["quote_id"]) is True
    assert rt.repo.consume_quote_atomically(uid, q["quote_id"]) is False

    # Submitting with already-consumed quote returns 403 Forbidden (APPROVAL_REQUIRED)
    replay = client.post(
        f"/api/plans/{plan['id']}/generate",
        json={
            "quote_id": q["quote_id"],
            "confirmation_token": q["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert replay.status_code == 403

    # Batch atomic quote consumption also executes exactly once
    bq_resp = client.post(
        f"/api/projects/{pid}/batches/quote",
        json={
            "items": [{"plan_id": plan["id"], "provider_id": "local_test_fixture", "model_id": "local-optical-slate-v1", "output_count": 1}],
        },
    )
    assert bq_resp.status_code == 200, bq_resp.text
    bq = bq_resp.json()
    assert rt.repo.consume_batch_quote_atomically(uid, bq["batch_quote_id"]) is True
    assert rt.repo.consume_batch_quote_atomically(uid, bq["batch_quote_id"]) is False


def test_unknown_timeout_reserves_estimated_spend_preventing_cap_bypass(tmp_path: Path) -> None:
    client, rt = _make_client(tmp_path)
    _register(client, "spendreserve@studio.test")
    pid = client.post("/api/projects", json={"name": "Spend Reserve Project"}).json()["id"]

    # Configure Google API key + tight $0.07 daily spend cap (enough for 1 2K image ~$0.0504, NOT 2!)
    assert client.post("/api/settings/credentials", json={"provider": "google", "api_key": "AIzaSyTestSpendReserveKey1234567890"}).status_code == 200
    assert client.patch("/api/settings", json={"daily_spend_cap_usd": 0.07}).status_code == 200

    # Simulate network ReadTimeout ONLY on GoogleImageAdapter's outbound HTTP client
    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("simulated network timeout after submission", request=request)

    plan_resp = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "image",
            "prompt_text": "Minimal glass perfume bottle on slate plinth",
            "aspect_ratio": "3:2",
            "provider_id": "google_gemini_image",
            "model_id": "gemini-nano-banana-2.1",
        },
    )
    assert plan_resp.status_code == 201, plan_resp.text
    plan = plan_resp.json()

    q1 = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "google_gemini_image", "model_id": "gemini-nano-banana-2.1"},
    ).json()
    assert q1["spend_guard_allows"] is True

    from unittest.mock import patch

    with patch(
        "prodstud.providers.google_image.build_http_client",
        side_effect=lambda timeout=120.0: httpx.Client(transport=httpx.MockTransport(timeout_handler), timeout=timeout),
    ):
        gen1 = client.post(
            f"/api/plans/{plan['id']}/generate",
            json={"quote_id": q1["quote_id"], "confirmation_token": q1["confirmation_token"], "explicit_user_confirmed": True},
        )
    assert gen1.status_code in {200, 201}, gen1.text
    assert gen1.json()["job"]["status"] == JobStatus.UNKNOWN.value

    # Daily spend MUST reflect conservative reservation >= $0.03 so a second billable request is blocked!
    me_after = client.get("/api/auth/me").json()
    assert me_after["user"]["spent_today_usd"] >= 0.03

    q2 = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "google_gemini_image", "model_id": "gemini-nano-banana-2.1"},
    ).json()
    assert q2["spend_guard_allows"] is False

    # Also verify Vision QC timeout reserves estimated spend cleanly
    assert client.patch("/api/settings", json={"daily_spend_cap_usd": 0.10}).status_code == 200
    local_plan = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "image",
            "prompt_text": "Local proof bottle",
            "aspect_ratio": "3:2",
            "provider_id": "local_test_fixture",
            "model_id": "local-optical-slate-v1",
        },
    ).json()
    lq = client.post(f"/api/plans/{local_plan['id']}/quote", json={"provider_id": "local_test_fixture", "model_id": "local-optical-slate-v1"}).json()
    asset = client.post(
        f"/api/plans/{local_plan['id']}/generate",
        json={"quote_id": lq["quote_id"], "confirmation_token": lq["confirmation_token"], "explicit_user_confirmed": True},
    ).json()["asset"]

    rt.jobs.vision_qc = VisionQCService(
        transport=GoogleVisionQCAdapter(
            http_client_factory=lambda t: httpx.Client(transport=httpx.MockTransport(timeout_handler), timeout=t)
        )
    )
    spent_before_vqc = client.get("/api/auth/me").json()["user"]["spent_today_usd"]
    vq = client.post(f"/api/assets/{asset['id']}/review/vision/quote").json()
    assert vq["spend_guard_allows"] is True
    vrun = client.post(
        f"/api/assets/{asset['id']}/review/vision/run",
        json={"quote_id": vq["quote_id"], "confirmation_token": vq["confirmation_token"], "explicit_user_confirmed": True},
    )
    assert vrun.status_code == 504
    spent_after_vqc = client.get("/api/auth/me").json()["user"]["spent_today_usd"]
    assert spent_after_vqc > spent_before_vqc


def test_bounded_upload_size_and_pixel_dimension_limit(tmp_path: Path) -> None:
    # Set tight 1 MB upload cap to test HTTP 413 cleanly
    client, _ = _make_client(tmp_path, max_reference_bytes=1024 * 1024)
    _register(client, "uploads@studio.test")
    pid = client.post("/api/projects", json={"name": "Upload Guard Project"}).json()["id"]

    # > 1 MB raw payload -> 413 Payload Too Large
    oversized = b"\x89PNG\r\n\x1a\n" + (b"0" * (1024 * 1024 + 512))
    r_big = client.post(
        f"/api/projects/{pid}/references",
        data={"role": "product"},
        files={"file": ("huge.png", oversized, "image/png")},
    )
    assert r_big.status_code == 413

    # Highly compressible PNG exceeding 25MP limit (e.g. 6000x5000 = 30,000,000 px) -> 400
    buf = io.BytesIO()
    Image.new("L", (6000, 5000), 128).save(buf, format="PNG")
    r_bomb = client.post(
        f"/api/projects/{pid}/references",
        data={"role": "product"},
        files={"file": ("bomb.png", buf.getvalue(), "image/png")},
    )
    assert r_bomb.status_code == 400


def test_asset_store_blocks_sibling_prefix_traversal_and_zip_slip(tmp_path: Path) -> None:
    base = tmp_path / "assets"
    sibling = tmp_path / "assets_evil"
    base.mkdir()
    sibling.mkdir()
    (sibling / "secret.txt").write_text("leaked", encoding="utf-8")

    store = AssetStore(base)
    with pytest.raises(MediaValidationError, match="Path traversal blocked"):
        store.resolve("../assets_evil/secret.txt")

    stored = store.store_generated_media(_png_bytes(), "image/png")
    zip_bytes = store.build_export_zip(
        [
            (stored.relpath, "../../etc/passwd.png", {"id": "a1"}),
            (stored.relpath, "../../etc/passwd.png", {"id": "a2"}),
        ]
    )
    with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
        names = zf.namelist()
        assert all(".." not in n and not n.startswith("/") and "/" not in n for n in names)
        png_members = [n for n in names if n.endswith(".png")]
        assert len(png_members) == 2
        assert len(set(png_members)) == 2


def test_cross_user_isolation_plan_spoofing_batch_duplicates_and_feedback_audit(tmp_path: Path) -> None:
    cfg = Settings.from_env(data_dir_override=str(tmp_path / "data"), env_override="test")
    app = create_app(cfg)
    client_a = TestClient(app)
    client_b = TestClient(app)

    _register(client_a, "alice@studio.test")
    _register(client_b, "bob@studio.test")

    pid_a = client_a.post("/api/projects", json={"name": "Alice Project"}).json()["id"]
    pid_b = client_b.post("/api/projects", json={"name": "Bob Project"}).json()["id"]

    # Upload reference under User B
    ref_b = client_b.post(
        f"/api/projects/{pid_b}/references",
        data={"role": "product"},
        files={"file": ("bob_ref.png", _png_bytes(), "image/png")},
    ).json()

    # User A cannot attach User B's reference_id to Alice's plan
    bad_ref_plan = client_a.post(
        f"/api/projects/{pid_a}/plans",
        json={
            "project_id": pid_a,
            "media_type": "image",
            "prompt_text": "Attempt foreign reference attachment",
            "reference_ids": [ref_b["id"]],
        },
    )
    assert bad_ref_plan.status_code == 400

    # User A creates video plan & generates asset
    vplan_a = client_a.post(
        f"/api/projects/{pid_a}/plans",
        json={
            "project_id": pid_a,
            "media_type": "video",
            "prompt_text": "Steady tabletop clip for Alice",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "duration_s": 4.0,
            "provider_id": "local_test_fixture",
            "model_id": "local-shot-animatic-v1",
        },
    ).json()

    # Client PATCH CANNOT spoof server-owned video extension provenance fields
    spoof_patch = client_a.patch(
        f"/api/plans/{vplan_a['id']}",
        json={
            "video_plan": {
                **vplan_a["video_plan"],
                "extended_from_asset_id": "ast_forged_999",
                "extension_duration_s": 7.0,
                "source_provider_job_id": "operations/forged-veo-op",
            }
        },
    )
    assert spoof_patch.status_code == 200
    vp_after = spoof_patch.json()["video_plan"]
    assert vp_after["extended_from_asset_id"] is None
    assert vp_after["extension_duration_s"] is None
    assert vp_after["source_provider_job_id"] is None

    # Batch rejects duplicate plan_ids
    dup_batch = client_a.post(
        f"/api/projects/{pid_a}/batches/quote",
        json={
            "items": [
                {"plan_id": vplan_a["id"], "provider_id": "local_test_fixture", "model_id": "local-shot-animatic-v1", "output_count": 1},
                {"plan_id": vplan_a["id"], "provider_id": "local_test_fixture", "model_id": "local-shot-animatic-v1", "output_count": 1},
            ],
        },
    )
    assert dup_batch.status_code == 400

    # Generate Alice's video asset and verify Bob cannot access, download, or extend it
    vq_a = client_a.post(
        f"/api/plans/{vplan_a['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-shot-animatic-v1"},
    ).json()
    gen_a = client_a.post(
        f"/api/plans/{vplan_a['id']}/generate",
        json={"quote_id": vq_a["quote_id"], "confirmation_token": vq_a["confirmation_token"], "explicit_user_confirmed": True},
    ).json()
    asset_a = gen_a["asset"]
    review_a = client_a.get(f"/api/assets/{asset_a['id']}/review").json()

    assert client_b.get(f"/api/projects/{pid_a}").status_code == 404
    assert client_b.get(f"/api/plans/{vplan_a['id']}").status_code == 404
    assert client_b.get(f"/api/assets/{asset_a['id']}/file").status_code == 404
    assert client_b.post(f"/api/assets/{asset_a['id']}/extend", json={"continuation_prompt": "Hijack"}).status_code == 404

    # Alice submits human feedback and audit log records project_id properly
    fb = client_a.post(f"/api/reviews/{review_a['id']}/feedback", json={"status": "accepted", "note": "Playback verified"})
    assert fb.status_code == 200
    audits = client_a.get(f"/api/audit?project_id={pid_a}").json()
    fb_events = [e for e in audits if e["event_type"] == "quality_feedback_recorded"]
    assert len(fb_events) == 1
    assert fb_events[0]["project_id"] == pid_a


def test_controlled_vision_qc_dataset_reproduces_tp_tn_fp_fn() -> None:
    """Verify controlled 13-case Vision QC audit runs at $0.00 spend and reproduces documented FP/FN modes."""
    script_path = REPO_ROOT / "scripts" / "audit_vision_qc.py"
    spec = importlib.util.spec_from_file_location("audit_vision_qc", script_path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules["audit_vision_qc"] = mod
    spec.loader.exec_module(mod)

    report = mod.run_controlled_audit()
    assert report["dataset_size"] == 13
    assert report["spend_usd"] == 0.0
    assert report["live_vision_api_invoked"] is False
    assert report["summary_counts"] == {"TP": 5, "TN": 2, "FP": 3, "FN": 3}

    by_id = {c["case_id"]: c for c in report["cases"]}
    assert by_id["IMG-05"]["classification"] == "FP"
    assert by_id["IMG-06"]["classification"] == "FP"
    assert by_id["IMG-09"]["classification"] == "FP"
    assert by_id["IMG-07"]["classification"] == "FN"
    assert by_id["IMG-10"]["classification"] == "FN"
    assert by_id["VID-02"]["classification"] == "FN"
    assert "NOT full frame-by-frame playback" in by_id["VID-02"]["inspection_coverage"]


def test_honest_external_blockers_and_zero_private_brain_leakage() -> None:
    """Ensure PDF verification remains blocked_external, 0 fabricated pages, and frontend leaks no private brain paths."""
    reg = json.loads((REPO_ROOT / "data" / "protocols_170.json").read_text(encoding="utf-8"))
    assert len(reg["protocols"]) == 170
    assert all(p.get("source_manual_page") is None for p in reg["protocols"])
    assert all(p.get("source_confidence") == "summary_verified_pending_full_manual_page_audit" for p in reg["protocols"])

    tracker = json.loads((REPO_ROOT / "docs" / "IMPLEMENTATION_STATUS.json").read_text(encoding="utf-8"))
    tasks = {t["id"]: t for p in tracker["phases"] for t in p["tasks"]}
    assert tasks["P2-7"]["status"] == "blocked_external"
    assert tasks["P2-8"]["status"] == "blocked_external"

    # Verify customer-facing frontend source never exposes private intelligence repo names or internal methodologies
    frontend_src = REPO_ROOT / "frontend" / "src"
    forbidden = ("zakshub/studio", "zakshub/designer", "Operating Constitution", "Designer Brain", "Studio Brain")
    leaks: list[str] = []
    for fpath in sorted(frontend_src.rglob("*")):
        if fpath.is_file() and fpath.suffix in {".ts", ".tsx", ".css", ".html"}:
            text = fpath.read_text(encoding="utf-8")
            for term in forbidden:
                if term in text:
                    leaks.append(f"{fpath.name}: contains '{term}'")
    assert leaks == [], f"Private intelligence methodology leaked into frontend UI: {leaks}"
