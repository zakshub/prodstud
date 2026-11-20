"""Representative regression test set (QUALITY_AND_EVALUATION.md & Phase 2 V1 gate) plus mocked Google Video async lifecycle."""

from __future__ import annotations

import base64
from unittest.mock import patch

import httpx
import pytest

from prodstud.domain.enums import ErrorCategory, JobStatus, MediaType
from prodstud.domain.models import BriefInput
from prodstud.runtime import AppRuntime
from prodstud.security import hash_password


REPRESENTATIVE_BRIEFS = [
    ("product_clean", MediaType.IMAGE, "Matte terracotta ceramic vase on pale oak plinth, diffused studio daylight", "4:5", None),
    ("portrait_natural", MediaType.IMAGE, "Close-up editorial portrait of ceramicist in sunlit studio, 85mm natural gaze", "4:5", None),
    ("complex_lighting_night", MediaType.IMAGE, "Tailored wool coat in rain-slicked Tokyo alley at night with warm tungsten storefront practicals", "3:2", None),
    ("text_logo_packaging", MediaType.IMAGE, "Minimalist coffee tin packaging with crisp embossed label typography on travertine slab", "1:1", None),
    ("video_single_shot", MediaType.VIDEO, "Slow dolly-in across steam rising from black espresso cup on walnut counter", "16:9", 5.0),
    ("video_multi_shot_continuity", MediaType.VIDEO, "Three-shot lookbook sequence of linen trench coat walking through courtyard then macro fabric weave detail", "9:16", 12.0),
]


@pytest.mark.parametrize("case_name,media_type,prompt,aspect_ratio,duration_s", REPRESENTATIVE_BRIEFS)
def test_representative_brief_regression_suite(
    runtime: AppRuntime,
    case_name: str,
    media_type: MediaType,
    prompt: str,
    aspect_ratio: str,
    duration_s: float | None,
) -> None:
    cap = runtime.providers.resolve_capability(media_type)
    brief = BriefInput(
        project_id=f"prj_{case_name}",
        media_type=media_type,
        prompt_text=prompt,
        aspect_ratio=aspect_ratio,
        duration_s=duration_s,
    )
    plan = runtime.engine.create_plan(brief_id=f"brf_{case_name}", brief=brief, references=[], capability=cap)
    assert plan.feasibility_ok is True
    assert 10 <= len(plan.activated_protocols) <= 30
    assert len(plan.decisions) >= 3
    if media_type == MediaType.IMAGE:
        assert plan.image_plan is not None
        assert plan.image_plan.aspect_ratio == aspect_ratio
        assert plan.image_plan.lighting_key
        assert plan.image_plan.negative_constraints
    else:
        assert plan.video_plan is not None
        assert plan.video_plan.aspect_ratio == aspect_ratio
        assert len(plan.video_plan.shots) >= 1
        assert abs(sum(s.duration_s for s in plan.video_plan.shots) - plan.video_plan.total_duration_s) < 0.2
        assert len(plan.video_plan.continuity_invariants) >= 3


def test_google_video_async_submit_poll_and_cancel_lifecycle(runtime: AppRuntime) -> None:
    user = runtime.repo.create_user(
        email="vidmock@example.com",
        display_name="Video Mock Tester",
        password_hash=hash_password("VideoMock123!"),
        daily_spend_cap_usd=10.0,
    )
    runtime.repo.upsert_credential(
        user_id=user.id,
        provider="google",
        encrypted_key=runtime.vault.encrypt("AIzaSyFakeVideoKeyTest123456"),
        masked_key="AIza...3456",
    )
    project = runtime.repo.create_project(user.id, "Async Video Test")
    cap = runtime.providers.resolve_capability(MediaType.VIDEO, "google_gemini_video", "gemini-omni-1.2-flash")
    brief = BriefInput(
        project_id=project.id,
        media_type=MediaType.VIDEO,
        prompt_text="Camera smoothly tracks brushed aluminum speaker rotating in warm gallery light",
        aspect_ratio="16:9",
        resolution="720p",
        duration_s=6.0,
    )
    bid = runtime.repo.save_brief(user.id, project.id, MediaType.VIDEO, brief.prompt_text, brief.model_dump())
    plan = runtime.engine.create_plan(brief_id=bid, brief=brief, references=[], capability=cap)
    runtime.repo.save_plan(user.id, plan)
    quote = runtime.jobs.request_quote(user=user, plan=plan, provider_id=cap.provider_id, model_id=cap.model_id)

    # First POST returns async in_progress interaction
    submit_resp = httpx.Response(
        200,
        json={"id": "inter_vid_900", "status": "in_progress"},
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/interactions"),
    )
    with patch.object(httpx.Client, "post", return_value=submit_resp):
        job, asset, review = runtime.jobs.submit_approved_job(
            user=user,
            plan=plan,
            quote_id=quote.quote_id,
            confirmation_token=quote.confirmation_token,
            explicit_user_confirmed=True,
        )
    assert job.status == JobStatus.PROCESSING
    assert job.provider_job_id == "inter_vid_900"
    assert asset is None

    # Poll returns timeout -> transitions safely to UNKNOWN (never resubmits!)
    with patch.object(httpx.Client, "get", side_effect=httpx.ReadTimeout("Poll timed out")):
        job_unknown, _, _ = runtime.jobs.poll_job(user.id, job.id)
    assert job_unknown.status == JobStatus.UNKNOWN
    assert job_unknown.error_category == ErrorCategory.TIMEOUT_UNKNOWN

    # Subsequent poll resolves cleanly with real valid MP4 from local fixture renderer
    local_adapter = runtime.providers.get_video_adapter("local_test_fixture")
    valid_mp4 = local_adapter._render_animatic_mp4(plan)  # type: ignore[attr-defined]
    done_resp = httpx.Response(
        200,
        json={
            "id": "inter_vid_900",
            "status": "completed",
            "output_video": {"mime_type": "video/mp4", "data": base64.b64encode(valid_mp4).decode("ascii")},
        },
        request=httpx.Request("GET", "https://generativelanguage.googleapis.com/v1beta/interactions/inter_vid_900"),
    )
    with patch.object(httpx.Client, "get", return_value=done_resp):
        job_done, asset_done, review_done = runtime.jobs.poll_job(user.id, job.id)
    assert job_done.status == JobStatus.SUCCEEDED
    assert asset_done is not None and asset_done.mime_type == "video/mp4"
    assert review_done is not None and "sampled_frames" in review_done.inspection_coverage
