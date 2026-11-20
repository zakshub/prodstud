"""Comprehensive PR #1 reliability & Phase 2 acceptance tests (variations, batch, video extension, Vision QC, manual audit)."""

from __future__ import annotations

import base64
import io
import json
import shutil
from pathlib import Path

import httpx
from fastapi.testclient import TestClient
from PIL import Image

from prodstud.api.app import create_app
from prodstud.config import Settings
from prodstud.domain.enums import ErrorCategory, JobStatus, MediaType
from prodstud.engine.vision_qc import VisionQCService
from prodstud.providers.base import ProviderAdapterError, ProviderSubmissionResult
from prodstud.security import sanitize_download_filename


def _png_bytes(color: tuple[int, int, int] = (90, 120, 150)) -> bytes:
    buf = io.BytesIO()
    Image.new("RGB", (64, 64), color).save(buf, format="PNG")
    return buf.getvalue()


def _make_client(tmp_path: Path) -> tuple[TestClient, object]:
    cfg = Settings.from_env(data_dir_override=str(tmp_path / "data"), env_override="test")
    app = create_app(cfg)
    return TestClient(app), app.state.runtime


def _register_and_project(client: TestClient, email: str = "p2@studio.test") -> str:
    r = client.post(
        "/api/auth/register",
        json={"email": email, "display_name": "Phase2 Owner", "password": "StrongPassword!2026"},
    )
    assert r.status_code in {200, 201}
    p = client.post("/api/projects", json={"name": "Phase 2 Suite", "description": "Acceptance project"})
    assert p.status_code in {200, 201}
    return p.json()["id"]


def test_logout_revokes_session_server_side_and_csp_present(tmp_path: Path):
    client, _ = _make_client(tmp_path)
    _register_and_project(client, email="logout@studio.test")

    me_before = client.get("/api/auth/me")
    assert me_before.status_code == 200
    assert "content-security-policy" in {k.lower() for k in me_before.headers.keys()}
    saved_cookie = client.cookies.get("prodstud_session")
    assert saved_cookie

    out = client.post("/api/auth/logout")
    assert out.status_code == 200

    # Replaying the exact pre-logout session cookie must fail with 401 (server-side DB row deleted)
    replay = client.get("/api/auth/me", cookies={"prodstud_session": saved_cookie})
    assert replay.status_code == 401


def test_content_disposition_filename_sanitization(tmp_path: Path):
    cleaned = sanitize_download_filename('../evil"\r\nX-Injected: true;foo.png')
    assert "\r" not in cleaned and "\n" not in cleaned and '"' not in cleaned and "/" not in cleaned and ";" not in cleaned

    client, _ = _make_client(tmp_path)
    pid = _register_and_project(client, email="disp@studio.test")
    resp = client.post(
        f"/api/projects/{pid}/references",
        data={"role": "product", "rights_confirmed": "true"},
        files={"file": ('weird"name;bad.png', _png_bytes(), "image/png")},
    )
    assert resp.status_code == 201
    ref_id = resp.json()["id"]
    dl = client.get(f"/api/references/{ref_id}/file")
    assert dl.status_code == 200
    cd = dl.headers.get("content-disposition", "")
    assert "filename" in cd and "\r" not in cd and "\n" not in cd and ";bad.png" not in cd


def test_plan_edit_and_revision_revalidate_feasibility(tmp_path: Path):
    client, _ = _make_client(tmp_path)
    pid = _register_and_project(client, email="feas@studio.test")

    plan_resp = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "video",
            "prompt_text": "Smooth dolly across studio ceramic cup",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "duration_s": 8.0,
            "provider_id": "local_test_fixture",
            "model_id": "local-shot-animatic-v1",
        },
    )
    assert plan_resp.status_code == 201
    plan = plan_resp.json()
    assert plan["feasibility_ok"] is True

    # Editing duration above 15s single-clip limit must immediately flip feasibility_ok to False
    vp_bad = dict(plan["video_plan"])
    vp_bad["total_duration_s"] = 24.0
    edited = client.patch(f"/api/plans/{plan['id']}", json={"video_plan": vp_bad})
    assert edited.status_code == 200
    assert edited.json()["feasibility_ok"] is False
    assert any("15" in w for w in edited.json()["feasibility_warnings"])

    # Targeted revision restoring duration to 8.0s must restore feasibility_ok to True
    rev = client.post(
        f"/api/plans/{plan['id']}/revise",
        json={"change_request": "Condense clip back to 8 seconds", "override_fields": {"total_duration_s": 8.0}},
    )
    assert rev.status_code == 201
    assert rev.json()["plan"]["feasibility_ok"] is True


def test_multi_output_image_variations_spend_guard_and_halt_on_unknown(tmp_path: Path, monkeypatch):
    client, rt = _make_client(tmp_path)
    pid = _register_and_project(client, email="vars@studio.test")

    plan = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "image",
            "prompt_text": "Brushed titanium mechanical watch on dark slate, diffused studio daylight, 85mm macro",
            "aspect_ratio": "3:2",
            "resolution": "1K",
            "provider_id": "local_test_fixture",
            "model_id": "local-optical-slate-v1",
        },
    ).json()

    # 1. Local test fixture 3x variations -> 3 unique assets + idempotent replay protection
    q = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-optical-slate-v1", "variation_count": 3},
    ).json()
    assert q["variation_count"] == 3
    assert q["estimated_cost_usd"] == 0.0

    gen = client.post(
        f"/api/plans/{plan['id']}/generate",
        json={
            "quote_id": q["quote_id"],
            "confirmation_token": q["confirmation_token"],
            "explicit_user_confirmed": True,
            "idempotency_key": "idem_var_test_01",
        },
    )
    assert gen.status_code == 200
    body = gen.json()
    assert len(body["jobs"]) == 3
    assert len(body["assets"]) == 3
    assert len({a["sha256"] for a in body["assets"]}) == 3
    assert [a["metadata"]["variation_index"] for a in body["assets"]] == [1, 2, 3]

    # Idempotent retry with same idempotency_key returns existing 3 jobs without creating more
    replay = client.post(
        f"/api/plans/{plan['id']}/generate",
        json={
            "quote_id": q["quote_id"],
            "confirmation_token": q["confirmation_token"],
            "explicit_user_confirmed": True,
            "idempotency_key": "idem_var_test_01",
        },
    )
    assert replay.status_code == 200
    assert [j["id"] for j in replay.json()["jobs"]] == [j["id"] for j in body["jobs"]]

    # 2. Billable Spend Guard scaling across variation_count
    client.post("/api/settings/credentials", json={"provider": "google", "api_key": "AIzaSyFakeTestKeyForUnitTests1234567"})
    client.patch("/api/settings", json={"daily_spend_cap_usd": 0.08})

    q2 = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "google_gemini_image", "model_id": "gemini-nano-banana-2.1", "variation_count": 2},
    ).json()
    assert q2["spend_guard_allows"] is True
    assert abs(q2["estimated_cost_usd"] - 0.0672) < 1e-5

    q3 = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "google_gemini_image", "model_id": "gemini-nano-banana-2.1", "variation_count": 3},
    ).json()
    assert q3["spend_guard_allows"] is False
    assert abs(q3["estimated_cost_usd"] - 0.1008) < 1e-5
    blocked = client.post(
        f"/api/plans/{plan['id']}/generate",
        json={"quote_id": q3["quote_id"], "confirmation_token": q3["confirmation_token"], "explicit_user_confirmed": True},
    )
    assert blocked.status_code == 402

    # 3. Fail-closed halt on UNKNOWN: 3-variation paid quote where take #2 times out -> take #3 MUST NOT run
    client.patch("/api/settings", json={"daily_spend_cap_usd": 1.00})
    q3_ok = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "google_gemini_image", "model_id": "gemini-nano-banana-2.1", "variation_count": 3},
    ).json()
    assert q3_ok["spend_guard_allows"] is True

    calls: list[int] = []
    google_img = rt.providers.get_image_adapter("google_gemini_image")

    def fake_submit(**kwargs):
        vidx = kwargs["variation_index"]
        calls.append(vidx)
        if vidx == 2:
            raise ProviderAdapterError(
                "Simulated timeout on variation 2",
                category=ErrorCategory.TIMEOUT_UNKNOWN,
                provider_may_have_accepted=True,
            )
        return ProviderSubmissionResult(
            status=JobStatus.SUCCEEDED,
            provider_job_id=f"inter_{vidx}",
            media_bytes=_png_bytes((40 * vidx, 80, 120)),
            mime_type="image/png",
            reported_cost_usd=0.0336,
        )

    monkeypatch.setattr(google_img, "submit", fake_submit)
    halted_res = client.post(
        f"/api/plans/{plan['id']}/generate",
        json={"quote_id": q3_ok["quote_id"], "confirmation_token": q3_ok["confirmation_token"], "explicit_user_confirmed": True},
    )
    assert halted_res.status_code == 200
    assert calls == [1, 2]  # Variation 3 was NEVER submitted after variation 2 entered UNKNOWN!
    assert len(halted_res.json()["jobs"]) == 2
    assert halted_res.json()["jobs"][0]["status"] == "succeeded"
    assert halted_res.json()["jobs"][1]["status"] == "unknown"


def test_batch_generation_combined_cost_approval_and_spend_guard(tmp_path: Path):
    client, _ = _make_client(tmp_path)
    pid = _register_and_project(client, email="batch@studio.test")

    img_plan = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "image",
            "prompt_text": "Matte ceramic pitcher on limestone ledge, natural morning light",
            "aspect_ratio": "3:2",
            "resolution": "1K",
            "provider_id": "local_test_fixture",
            "model_id": "local-optical-slate-v1",
        },
    ).json()
    vid_plan = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "video",
            "prompt_text": "Slow push-in across matte ceramic pitcher in warm studio morning light",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "duration_s": 4.0,
            "provider_id": "local_test_fixture",
            "model_id": "local-shot-animatic-v1",
        },
    ).json()

    # Combined batch quote: 2 image variations + 1 video = 3 outputs
    bq = client.post(
        f"/api/projects/{pid}/batches/quote",
        json={
            "items": [
                {"plan_id": img_plan["id"], "variation_count": 2},
                {"plan_id": vid_plan["id"], "variation_count": 1},
            ]
        },
    )
    assert bq.status_code == 200
    bquote = bq.json()
    assert bquote["total_requested_outputs"] == 3
    assert bquote["spend_guard_allows"] is True
    assert bquote["total_estimated_cost_usd"] == 0.0

    # Reject missing explicit confirmation
    no_confirm = client.post(
        f"/api/projects/{pid}/batches/execute",
        json={
            "batch_quote_id": bquote["batch_quote_id"],
            "confirmation_token": bquote["confirmation_token"],
            "explicit_user_confirmed": False,
        },
    )
    assert no_confirm.status_code == 403

    # Approve & execute batch
    exec_resp = client.post(
        f"/api/projects/{pid}/batches/execute",
        json={
            "batch_quote_id": bquote["batch_quote_id"],
            "confirmation_token": bquote["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert exec_resp.status_code == 200
    exec_data = exec_resp.json()
    assert exec_data["batch"]["status"] == "completed"
    assert exec_data["batch"]["completed_outputs"] == 3
    assert len(exec_data["assets"]) == 3

    # Consumed batch quote cannot be reused
    reuse = client.post(
        f"/api/projects/{pid}/batches/execute",
        json={
            "batch_quote_id": bquote["batch_quote_id"],
            "confirmation_token": bquote["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert reuse.status_code == 403

    batches = client.get(f"/api/projects/{pid}/batches").json()
    assert len(batches) == 1 and batches[0]["batch_id"] == exec_data["batch"]["batch_id"]

    # Billable batch quote blocked at $0.00 default cap
    client.post("/api/settings/credentials", json={"provider": "google", "api_key": "AIzaSyFakeBatchKey123456789012345"})
    bq_paid = client.post(
        f"/api/projects/{pid}/batches/quote",
        json={
            "items": [
                {
                    "plan_id": img_plan["id"],
                    "provider_id": "google_gemini_image",
                    "model_id": "gemini-nano-banana-2.1",
                    "variation_count": 2,
                }
            ]
        },
    ).json()
    assert bq_paid["spend_guard_allows"] is False
    assert abs(bq_paid["total_estimated_cost_usd"] - 0.0672) < 1e-5
    blocked = client.post(
        f"/api/projects/{pid}/batches/execute",
        json={
            "batch_quote_id": bq_paid["batch_quote_id"],
            "confirmation_token": bq_paid["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert blocked.status_code == 402


def test_multi_turn_video_extension_local_and_google_contract_and_30s_cap(tmp_path: Path, monkeypatch):
    client, rt = _make_client(tmp_path)
    pid = _register_and_project(client, email="ext@studio.test")

    vplan = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "video",
            "prompt_text": "Slow tracking shot across architectural coffee bar at dawn",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "duration_s": 6.0,
            "provider_id": "local_test_fixture",
            "model_id": "local-shot-animatic-v1",
        },
    ).json()
    vq = client.post(
        f"/api/plans/{vplan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-shot-animatic-v1"},
    ).json()
    vgen = client.post(
        f"/api/plans/{vplan['id']}/generate",
        json={"quote_id": vq["quote_id"], "confirmation_token": vq["confirmation_token"], "explicit_user_confirmed": True},
    ).json()
    src_asset = vgen["asset"]
    assert src_asset["media_type"] == "video"
    assert abs(src_asset["duration_s"] - 6.0) <= 0.6

    # Extend by +4s -> total 10.0s
    ext_resp = client.post(
        f"/api/assets/{src_asset['id']}/extend",
        json={
            "continuation_prompt": "Camera settles onto pour-over carafe as steam curls softly into sunbeam",
            "extension_duration_s": 4.0,
        },
    )
    assert ext_resp.status_code == 201
    ext_plan = ext_resp.json()
    assert ext_plan["task_mode"] == "VIDEO_EXTENSION"
    assert ext_plan["feasibility_ok"] is True
    assert abs(ext_plan["video_plan"]["total_duration_s"] - 10.0) <= 0.3
    assert ext_plan["video_plan"]["extended_from_asset_id"] == src_asset["id"]
    assert ext_plan["video_plan"]["shots"][-1]["start_s"] >= 5.5

    eq = client.post(
        f"/api/plans/{ext_plan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-shot-animatic-v1"},
    ).json()
    egen = client.post(
        f"/api/plans/{ext_plan['id']}/generate",
        json={"quote_id": eq["quote_id"], "confirmation_token": eq["confirmation_token"], "explicit_user_confirmed": True},
    ).json()
    ext_asset = egen["asset"]
    assert ext_asset["parent_asset_id"] == src_asset["id"]
    assert abs(ext_asset["duration_s"] - 10.0) <= 0.6

    # Verify GoogleVideoAdapter contract sends previous_interaction_id and turn duration (4s, NOT 10s)
    captured_payload: dict = {}

    def mock_handler(request: httpx.Request) -> httpx.Response:
        captured_payload.update(json.loads(request.content.decode("utf-8")))
        return httpx.Response(200, json={"id": "inter_vid_ext_02", "status": "in_progress"})

    monkeypatch.setattr(
        "prodstud.providers.google_video.build_http_client",
        lambda timeout: httpx.Client(transport=httpx.MockTransport(mock_handler), timeout=timeout),
    )
    gvid = rt.providers.get_video_adapter("google_gemini_video")
    ext_plan_obj = rt.repo.get_plan(rt.repo.get_user_row_by_email("ext@studio.test")["id"], ext_plan["id"])
    assert ext_plan_obj is not None and ext_plan_obj.video_plan is not None
    ext_plan_obj.video_plan.source_provider_job_id = "inter_vid_base_01"
    res = gvid.submit(
        plan=ext_plan_obj,
        model_id="gemini-omni-1.2-flash",
        references=[],
        api_key="AIzaSyMockVideoExtensionKey1234567890",
        idempotency_key="idem_gvid_ext_1",
        previous_provider_job_id="inter_vid_base_01",
    )
    assert res.status == JobStatus.PROCESSING
    assert captured_payload["previous_interaction_id"] == "inter_vid_base_01"
    assert captured_payload["response_format"]["duration"] == 4  # Extension turn duration!

    # Verify >30s cumulative cap fails feasibility
    ext_plan_obj.video_plan.total_duration_s = 32.0
    errs = gvid.validate_request(ext_plan_obj, "gemini-omni-1.2-flash", [])
    assert any("30s" in e for e in errs)


def test_optional_multimodal_vision_qc_gating_and_mocked_execution(tmp_path: Path):
    client, rt = _make_client(tmp_path)
    pid = _register_and_project(client, email="vqc@studio.test")

    # Upload product reference so source comparison is triggered
    ref = client.post(
        f"/api/projects/{pid}/references",
        data={"role": "product", "rights_confirmed": "true"},
        files={"file": ("bottle.png", _png_bytes((200, 160, 120)), "image/png")},
    ).json()
    plan = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "image",
            "prompt_text": "Keep bottle label unchanged, place on warm sandstone slab in afternoon light",
            "aspect_ratio": "3:2",
            "resolution": "1K",
            "reference_ids": [ref["id"]],
            "preservation_mode": "selective_edit",
            "provider_id": "local_test_fixture",
            "model_id": "local-optical-slate-v1",
        },
    ).json()
    q = client.post(
        f"/api/plans/{plan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-optical-slate-v1"},
    ).json()
    asset = client.post(
        f"/api/plans/{plan['id']}/generate",
        json={"quote_id": q["quote_id"], "confirmation_token": q["confirmation_token"], "explicit_user_confirmed": True},
    ).json()["asset"]

    # At $0.00 default cap and no credential, Vision QC quote reports blocked and run fails closed
    vq_zero = client.post(f"/api/assets/{asset['id']}/review/vision/quote").json()
    assert vq_zero["spend_guard_allows"] is False
    assert vq_zero["credential_ready"] is False
    assert vq_zero["includes_source_comparison"] is True
    blocked = client.post(
        f"/api/assets/{asset['id']}/review/vision/run",
        json={
            "quote_id": vq_zero["quote_id"],
            "confirmation_token": vq_zero["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert blocked.status_code in {402, 403}

    # Add encrypted key + raise cap to $0.50 + inject mocked multimodal Gemini response with critical preservation fail (1.8)
    client.post("/api/settings/credentials", json={"provider": "google", "api_key": "AIzaSyMockVisionQCKey12345678901234"})
    client.patch("/api/settings", json={"daily_spend_cap_usd": 0.50})

    mock_json = {
        "brief_adherence_score": 4.2,
        "brief_adherence_evidence": "Bottle silhouette and warm sandstone tone align with brief.",
        "physical_causality_score": 3.8,
        "physical_causality_evidence": "Directional shadow matches upper-left key light.",
        "preservation_score": 1.8,
        "preservation_evidence": "Label typography appears distorted compared to source reference.",
        "detected_ai_tells": [{"id": "T10", "status": "detected", "evidence": "Garbled micro-lettering on bottle label."}],
        "findings": [
            {
                "severity": "critical",
                "dimension": "vision_source_preservation",
                "location": "Center bottle label",
                "observed_evidence": "Label lettering differs from attached source reference.",
                "inferred_cause": "Model re-synthesized label typography.",
                "confidence": 0.85,
                "suggested_correction": "Use selective preservation revision locking label zone.",
            }
        ],
    }

    def vision_handler(request: httpx.Request) -> httpx.Response:
        assert "x-goog-api-key" in request.headers
        return httpx.Response(
            200,
            json={
                "candidates": [{"content": {"parts": [{"text": json.dumps(mock_json)}]}}],
                "usageMetadata": {"promptTokenCount": 1400, "candidatesTokenCount": 260},
            },
        )

    rt.jobs.vision_qc = VisionQCService(
        http_client_factory=lambda t: httpx.Client(transport=httpx.MockTransport(vision_handler), timeout=t)
    )

    vq_ok = client.post(f"/api/assets/{asset['id']}/review/vision/quote").json()
    assert vq_ok["spend_guard_allows"] is True
    assert vq_ok["credential_ready"] is True

    run_resp = client.post(
        f"/api/assets/{asset['id']}/review/vision/run",
        json={
            "quote_id": vq_ok["quote_id"],
            "confirmation_token": vq_ok["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert run_resp.status_code == 200
    upgraded = run_resp.json()
    # Critical preservation gate <= 2.0 MUST force rework_recommended!
    assert upgraded["advisory_verdict"] == "rework_recommended"
    assert "multimodal_vision" in upgraded["inspection_coverage"]
    assert any(t["id"] == "T10" and t["check_status"] == "vision_detected" for t in upgraded["ai_tell_checklist"])

    # Both deterministic and multimodal reviews are preserved in history
    history = client.get(f"/api/assets/{asset['id']}/reviews").json()
    assert len(history) == 2

    # Verify spend telemetry incremented slightly (> 0)
    me = client.get("/api/auth/me").json()
    assert me["user"]["spent_today_usd"] > 0.0

    # Also test Video multimodal Vision QC sampled frames disclosure
    vplan = client.post(
        f"/api/projects/{pid}/plans",
        json={
            "project_id": pid,
            "media_type": "video",
            "prompt_text": "Gentle camera dolly on espresso steam",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "duration_s": 4.0,
            "provider_id": "local_test_fixture",
            "model_id": "local-shot-animatic-v1",
        },
    ).json()
    vq_vid_gen = client.post(
        f"/api/plans/{vplan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-shot-animatic-v1"},
    ).json()
    vid_asset = client.post(
        f"/api/plans/{vplan['id']}/generate",
        json={
            "quote_id": vq_vid_gen["quote_id"],
            "confirmation_token": vq_vid_gen["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    ).json()["asset"]

    vid_mock = {
        "brief_adherence_score": 4.4,
        "brief_adherence_evidence": "Sampled keyframes show planned shot markers.",
        "frame_continuity_score": 4.3,
        "frame_continuity_evidence": "Consistent lighting tone across all 3 sampled frames.",
        "findings": [],
    }
    rt.jobs.vision_qc = VisionQCService(
        http_client_factory=lambda t: httpx.Client(
            transport=httpx.MockTransport(
                lambda req: httpx.Response(200, json={"candidates": [{"content": {"parts": [{"text": json.dumps(vid_mock)}]}}]})
            ),
            timeout=t,
        )
    )
    vvq = client.post(f"/api/assets/{vid_asset['id']}/review/vision/quote").json()
    assert vvq["frames_to_inspect"] == 3
    vrun = client.post(
        f"/api/assets/{vid_asset['id']}/review/vision/run",
        json={"quote_id": vvq["quote_id"], "confirmation_token": vvq["confirmation_token"], "explicit_user_confirmed": True},
    )
    assert vrun.status_code == 200
    assert "NOT full frame-by-frame playback" in vrun.json()["inspection_coverage"]


def test_manual_page_verifier_and_live_smoke_dry_run(tmp_path: Path):
    import importlib.util

    repo_root = Path(__file__).resolve().parents[2]
    verifier_path = repo_root / "scripts" / "verify_manual_pages.py"
    spec = importlib.util.spec_from_file_location("verify_manual_pages", verifier_path)
    assert spec and spec.loader
    vmod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(vmod)

    # Copy registry to temp path so canonical repo file is NEVER mutated by test
    tmp_reg = tmp_path / "protocols_170.json"
    shutil.copy2(repo_root / "data" / "protocols_170.json", tmp_reg)

    manual_txt = tmp_path / "synthetic_manual.txt"
    manual_txt.write_text(
        "--- Page 1 ---\nProtocol 001: Input Interpretation\nParse user brief cleanly.\n"
        "--- Page 2 ---\nProtocol 002: User Intent Classification\nClassify task mode.\n"
        "--- Page 3 ---\nProtocol 003: Unrelated Fabricated Heading\nMismatch test.\n",
        encoding="utf-8",
    )
    report = vmod.verify_manual_against_registry(source_path=manual_txt, registry_path=tmp_reg, update_registry=True)
    assert report["verified_count"] == 2
    assert report["title_discrepancies_count"] == 1
    assert report["missing_count"] == 167

    updated_data = json.loads(tmp_reg.read_text(encoding="utf-8"))
    p1, p2, p3 = updated_data["protocols"][0], updated_data["protocols"][1], updated_data["protocols"][2]
    assert p1["source_confidence"] == "page_verified" and p1["source_manual_page"] == 1
    assert p2["source_confidence"] == "page_verified" and p2["source_manual_page"] == 2
    # Protocol 003 had mismatch -> canonical title preserved untouched & confidence NOT upgraded!
    assert p3["source_confidence"] == "summary_verified_pending_full_manual_page_audit"
    assert "source_manual_page" not in p3

    # Verify live smoke test script runs cleanly in --dry-run ($0.00)
    smoke_path = repo_root / "scripts" / "live_google_smoke_test.py"
    sspec = importlib.util.spec_from_file_location("live_google_smoke_test", smoke_path)
    assert sspec and sspec.loader
    smod = importlib.util.module_from_spec(sspec)
    sspec.loader.exec_module(smod)
    assert smod.main(["--dry-run"]) == 0
