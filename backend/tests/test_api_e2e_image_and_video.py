"""Full End-to-End REST API integration tests for MVP Image + Video workflows, revision, comparison, credentials, and export."""

from __future__ import annotations

import io
import zipfile

from fastapi.testclient import TestClient


def test_full_mvp_image_and_video_lifecycle_e2e(client: TestClient, sample_png_bytes: bytes) -> None:
    # 1. Health check
    health = client.get("/api/health")
    assert health.status_code == 200
    assert health.json()["protocols_loaded"] == 170
    assert health.json()["database_integrity"] == "ok"

    # 2. Register single user
    reg = client.post(
        "/api/auth/register",
        json={"email": "director@studio.local", "display_name": "Studio Director", "password": "ProductionPass123!"},
    )
    assert reg.status_code == 200
    assert reg.json()["user"]["daily_spend_cap_usd"] == 0.0

    # 3. Store & revoke server-side credential — verify plaintext NEVER returned
    secret_key = "AIzaSySecretNeverLeakToClient987654"
    cred_save = client.post("/api/settings/credentials", json={"provider": "google", "api_key": secret_key})
    assert cred_save.status_code == 200
    assert secret_key not in cred_save.text
    assert cred_save.json()["masked_key"] == "AIza...7654"

    cred_list = client.get("/api/settings/credentials")
    assert cred_list.status_code == 200
    assert secret_key not in cred_list.text

    # 4. Create, rename, archive, and reopen a project
    prj = client.post("/api/projects", json={"name": "Autumn Watch Campaign", "description": "Hero still and launch clip"})
    assert prj.status_code == 201
    project_id = prj.json()["id"]

    renamed = client.patch(f"/api/projects/{project_id}", json={"name": "Autumn Watch Campaign v1", "archived": True})
    assert renamed.status_code == 200 and renamed.json()["archived"] is True
    reopened = client.patch(f"/api/projects/{project_id}", json={"archived": False})
    assert reopened.status_code == 200 and reopened.json()["archived"] is False

    # 5. Upload reference image with role & rights confirmation
    ref_resp = client.post(
        f"/api/projects/{project_id}/references",
        files={"file": ("watch_ref.png", sample_png_bytes, "image/png")},
        data={"role": "product", "rights_confirmed": "true", "notes": "Hero dial geometry"},
    )
    assert ref_resp.status_code == 201
    ref_id = ref_resp.json()["id"]

    # Reject invalid polyglot file upload
    bad_ref = client.post(
        f"/api/projects/{project_id}/references",
        files={"file": ("evil.png", b"<script>alert(1)</script>", "image/png")},
        data={"role": "style", "rights_confirmed": "true"},
    )
    assert bad_ref.status_code == 400

    # 6. IMAGE WORKFLOW: Plan -> Quote -> Explicitly Approved Generate -> Preview -> Advisory QC -> Revise -> Regenerate -> Compare -> Export
    img_plan_resp = client.post(
        f"/api/projects/{project_id}/plans",
        json={
            "project_id": project_id,
            "media_type": "image",
            "prompt_text": "Brushed titanium mechanical watch resting on dark travertine stone in moody studio lighting",
            "aspect_ratio": "3:2",
            "resolution": "2K",
            "reference_ids": [ref_id],
            "provider_id": "local_test_fixture",
            "model_id": "local-optical-slate-v1",
        },
    )
    assert img_plan_resp.status_code == 201
    img_plan = img_plan_resp.json()
    assert len(img_plan["activated_protocols"]) >= 10
    assert img_plan["image_plan"]["aspect_ratio"] == "3:2"

    quote_resp = client.post(
        f"/api/plans/{img_plan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-optical-slate-v1"},
    )
    assert quote_resp.status_code == 200
    quote = quote_resp.json()
    assert quote["is_local_test_fixture"] is True

    gen_resp = client.post(
        f"/api/plans/{img_plan['id']}/generate",
        json={
            "quote_id": quote["quote_id"],
            "confirmation_token": quote["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert gen_resp.status_code == 200
    gen_data = gen_resp.json()
    assert gen_data["job"]["status"] == "succeeded"
    asset_v1 = gen_data["asset"]
    review_v1 = gen_data["quality_review"]
    assert asset_v1["mime_type"] == "image/png"
    assert asset_v1["width"] == 1200 and asset_v1["height"] == 800
    assert "deterministic" in review_v1["inspection_coverage"] or "full_image" in review_v1["inspection_coverage"]
    assert len(review_v1["limitations"]) >= 2

    # Stream generated image preview
    file_resp = client.get(f"/api/assets/{asset_v1['id']}/file")
    assert file_resp.status_code == 200
    assert file_resp.content[:8] == b"\x89PNG\r\n\x1a\n"

    # Submit human review feedback & organize tags/collection
    fb = client.post(
        f"/api/reviews/{review_v1['id']}/feedback",
        json={"status": "needs_rework", "note": "Warm up key lighting slightly"},
    )
    assert fb.status_code == 200
    org = client.patch(
        f"/api/assets/{asset_v1['id']}",
        json={"tags": ["hero", "watch"], "collection_name": "Autumn Launch", "is_favorite": True},
    )
    assert org.status_code == 200 and org.json()["is_favorite"] is True

    # Controlled revision -> v2 generation -> side-by-side comparison
    rev_resp = client.post(
        f"/api/plans/{img_plan['id']}/revise?source_asset_id={asset_v1['id']}",
        json={"change_request": "Make lighting warmer and tighten framing to 85mm close-up"},
    )
    assert rev_resp.status_code == 201
    plan_v2 = rev_resp.json()["plan"]
    assert plan_v2["version"] == 2
    assert plan_v2["image_plan"]["focal_length_mm"] == 85
    assert plan_v2["image_plan"]["aspect_ratio"] == "3:2"  # Preserved!

    q2 = client.post(
        f"/api/plans/{plan_v2['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-optical-slate-v1"},
    ).json()
    gen2 = client.post(
        f"/api/plans/{plan_v2['id']}/generate",
        json={
            "quote_id": q2["quote_id"],
            "confirmation_token": q2["confirmation_token"],
            "explicit_user_confirmed": True,
            "parent_asset_id": asset_v1["id"],
        },
    ).json()
    asset_v2 = gen2["asset"]
    assert asset_v2["version_number"] == 2
    assert asset_v2["parent_asset_id"] == asset_v1["id"]

    cmp_resp = client.get(f"/api/assets/compare?left_id={asset_v1['id']}&right_id={asset_v2['id']}")
    assert cmp_resp.status_code == 200
    diff_fields = {d["field"] for d in cmp_resp.json()["decision_diffs"]}
    assert "focal_length_mm" in diff_fields

    # Export ZIP + sanitized provenance sidecar (must NEVER contain API key!)
    exp_resp = client.get(f"/api/assets/{asset_v2['id']}/export")
    assert exp_resp.status_code == 200
    zf = zipfile.ZipFile(io.BytesIO(exp_resp.content))
    names = zf.namelist()
    assert any(n.endswith(".png") for n in names)
    sidecar_name = next(n for n in names if n.endswith(".provenance.json"))
    sidecar_text = zf.read(sidecar_name).decode("utf-8")
    assert secret_key not in sidecar_text
    assert asset_v2["id"] in sidecar_text

    # 7. VIDEO WORKFLOW: Timed Shot Plan -> Quote -> Async Generate -> Playable MP4 Preview -> Advisory Continuity Review -> Export
    vid_plan_resp = client.post(
        f"/api/projects/{project_id}/plans",
        json={
            "project_id": project_id,
            "media_type": "video",
            "prompt_text": "Two-shot watch reveal on travertine pedestal with slow camera glide then tight macro detail on sweeping seconds hand",
            "aspect_ratio": "16:9",
            "resolution": "720p",
            "duration_s": 6.0,
            "provider_id": "local_test_fixture",
            "model_id": "local-shot-animatic-v1",
        },
    )
    assert vid_plan_resp.status_code == 201
    vid_plan = vid_plan_resp.json()
    assert len(vid_plan["video_plan"]["shots"]) == 2
    assert vid_plan["video_plan"]["total_duration_s"] == 6.0

    vq = client.post(
        f"/api/plans/{vid_plan['id']}/quote",
        json={"provider_id": "local_test_fixture", "model_id": "local-shot-animatic-v1"},
    ).json()
    vgen = client.post(
        f"/api/plans/{vid_plan['id']}/generate",
        json={
            "quote_id": vq["quote_id"],
            "confirmation_token": vq["confirmation_token"],
            "explicit_user_confirmed": True,
        },
    )
    assert vgen.status_code == 200
    vdata = vgen.json()
    assert vdata["job"]["status"] == "succeeded"
    vasset = vdata["asset"]
    vreview = vdata["quality_review"]
    assert vasset["mime_type"] == "video/mp4"
    assert vasset["duration_s"] is not None and abs(vasset["duration_s"] - 6.0) <= 0.6
    assert "sampled_frames" in vreview["inspection_coverage"]

    vfile = client.get(f"/api/assets/{vasset['id']}/file")
    assert vfile.status_code == 200
    assert b"ftyp" in vfile.content[:64]  # Valid ISO BMFF / MP4 signature

    # 8. Templates & Audit trail check (zero secrets anywhere in audit log!)
    tpl = client.post(
        "/api/templates",
        json={
            "name": "Studio Watch Still",
            "media_type": "image",
            "description": "Repeatable tabletop watch preset",
            "default_brief": {"aspect_ratio": "3:2", "resolution": "2K"},
        },
    )
    assert tpl.status_code == 201
    audit = client.get(f"/api/audit?project_id={project_id}")
    assert audit.status_code == 200
    assert len(audit.json()) >= 6
    assert secret_key not in audit.text

    # Revoke credential
    rev_cred = client.delete("/api/settings/credentials/google")
    assert rev_cred.status_code == 200 and rev_cred.json()["status"] == "revoked"
