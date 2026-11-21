"""Tests for verified Google adapter HTTP contract (mocked — $0.00 live spend), timeout -> UNKNOWN safety, and idempotency."""

from __future__ import annotations

import base64
import io
from unittest.mock import patch

import httpx
from PIL import Image

from prodstud.domain.enums import CapabilitySupport, ErrorCategory, JobStatus, MediaType
from prodstud.domain.models import BriefInput
from prodstud.runtime import AppRuntime
from prodstud.security import hash_password


def _make_png_b64() -> str:
    img = Image.new("RGB", (1200, 800), (95, 110, 125))
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return base64.b64encode(buf.getvalue()).decode("ascii")


def test_provider_capability_matrix_reflects_verified_nov_2026_status(runtime: AppRuntime) -> None:
    img_caps = {c.model_id: c for c in runtime.providers.list_capabilities(MediaType.IMAGE)}
    assert img_caps["gemini-nano-banana-2.1"].support_status == CapabilitySupport.SUPPORTED
    assert img_caps["imagen-4"].support_status == CapabilitySupport.UNSUPPORTED
    assert img_caps["gemini-3.1-flash-image"].support_status == CapabilitySupport.DEPRECATED

    vid_caps = {c.model_id: c for c in runtime.providers.list_capabilities(MediaType.VIDEO)}
    assert vid_caps["gemini-omni-1.2-flash"].support_status == CapabilitySupport.SUPPORTED
    assert vid_caps["veo-3.1-generate-preview"].support_status == CapabilitySupport.UNSUPPORTED
    assert vid_caps["veo-3.1-generate-001"].support_status == CapabilitySupport.PROVIDER_CONDITIONAL


def test_google_image_timeout_transitions_to_unknown_without_blind_retry(runtime: AppRuntime) -> None:
    user = runtime.repo.create_user(
        email="timeout@example.com",
        display_name="Timeout Tester",
        password_hash=hash_password("TimeoutPass123!"),
        daily_spend_cap_usd=5.0,
    )
    runtime.repo.upsert_credential(
        user_id=user.id,
        provider="google",
        encrypted_key=runtime.vault.encrypt("AIzaSyFakeKeyTimeoutTest9999"),
        masked_key="AIza...9999",
    )
    project = runtime.repo.create_project(user.id, "Timeout Safety")
    cap = runtime.providers.resolve_capability(MediaType.IMAGE, "google_gemini_image", "gemini-nano-banana-2.1")
    brief = BriefInput(project_id=project.id, media_type=MediaType.IMAGE, prompt_text="Steel watch macro shot", aspect_ratio="3:2")
    bid = runtime.repo.save_brief(user.id, project.id, MediaType.IMAGE, brief.prompt_text, brief.model_dump())
    plan = runtime.engine.create_plan(brief_id=bid, brief=brief, references=[], capability=cap)
    runtime.repo.save_plan(user.id, plan)
    quote = runtime.jobs.request_quote(user=user, plan=plan, provider_id=cap.provider_id, model_id=cap.model_id)

    call_count = 0

    def fake_post(*args, **kwargs):
        nonlocal call_count
        call_count += 1
        raise httpx.ReadTimeout("Simulated timeout after sending request")

    with patch.object(httpx.Client, "post", side_effect=fake_post):
        job, asset, review = runtime.jobs.submit_approved_job(
            user=user,
            plan=plan,
            quote_id=quote.quote_id,
            confirmation_token=quote.confirmation_token,
            explicit_user_confirmed=True,
            idempotency_key="idem_timeout_1",
        )

    assert call_count == 1  # ZERO blind automatic retries!
    assert job.status == JobStatus.UNKNOWN
    assert job.provider_may_have_accepted is True
    assert job.error_category == ErrorCategory.TIMEOUT_UNKNOWN
    assert asset is None
    assert review is None


def test_google_image_mocked_success_and_idempotency_prevent_duplicate_charge(runtime: AppRuntime) -> None:
    user = runtime.repo.create_user(
        email="googleok@example.com",
        display_name="Google Mock Tester",
        password_hash=hash_password("GoogleMock123!"),
        daily_spend_cap_usd=5.0,
    )
    runtime.repo.upsert_credential(
        user_id=user.id,
        provider="google",
        encrypted_key=runtime.vault.encrypt("AIzaSyFakeKeySuccessTest1234"),
        masked_key="AIza...1234",
    )
    project = runtime.repo.create_project(user.id, "Mocked Google Image")
    cap = runtime.providers.resolve_capability(MediaType.IMAGE, "google_gemini_image", "gemini-nano-banana-2.1")
    brief = BriefInput(project_id=project.id, media_type=MediaType.IMAGE, prompt_text="Linen armchair in sunlit loft", aspect_ratio="3:2", resolution="1K")
    bid = runtime.repo.save_brief(user.id, project.id, MediaType.IMAGE, brief.prompt_text, brief.model_dump())
    plan = runtime.engine.create_plan(brief_id=bid, brief=brief, references=[], capability=cap)
    runtime.repo.save_plan(user.id, plan)
    quote = runtime.jobs.request_quote(user=user, plan=plan, provider_id=cap.provider_id, model_id=cap.model_id)

    mock_response = httpx.Response(
        200,
        json={
            "id": "inter_mock_001",
            "output_image": {"mime_type": "image/png", "data": _make_png_b64()},
            "usage": {"total_tokens": 1400},
        },
        request=httpx.Request("POST", "https://generativelanguage.googleapis.com/v1beta/interactions"),
    )

    with patch.object(httpx.Client, "post", return_value=mock_response) as mock_post:
        job1, asset1, review1 = runtime.jobs.submit_approved_job(
            user=user,
            plan=plan,
            quote_id=quote.quote_id,
            confirmation_token=quote.confirmation_token,
            explicit_user_confirmed=True,
            idempotency_key="idem_unique_abc",
        )
        # Re-submitting same idempotency_key MUST return existing job without calling Google twice!
        job2, asset2, review2 = runtime.jobs.submit_approved_job(
            user=user,
            plan=plan,
            quote_id=quote.quote_id,
            confirmation_token=quote.confirmation_token,
            explicit_user_confirmed=True,
            idempotency_key="idem_unique_abc",
        )
        assert mock_post.call_count == 1
        # Verify API key sent via header only, NOT query string
        _, kwargs = mock_post.call_args
        assert kwargs["headers"]["x-goog-api-key"] == "AIzaSyFakeKeySuccessTest1234"

    assert job1.status == JobStatus.SUCCEEDED
    assert job1.id == job2.id
    assert asset1 is not None and asset2 is not None and asset1.id == asset2.id
    assert asset1.is_local_test_fixture is False
    assert review1 is not None
    assert runtime.repo.get_user_spent_today(user.id) > 0.0
