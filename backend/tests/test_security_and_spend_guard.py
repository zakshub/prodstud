"""Security, Fernet vault encryption, log secret redaction, $0.00 Spend Guard, approval token, and unknown-state safety tests."""

from __future__ import annotations

import pytest

from prodstud.domain.enums import ErrorCategory, MediaType
from prodstud.domain.models import BriefInput
from prodstud.providers.base import ProviderAdapterError
from prodstud.runtime import AppRuntime
from prodstud.security import hash_password, mask_api_key, redact_secrets, verify_password


def test_secret_redaction_and_fernet_vault(runtime: AppRuntime) -> None:
    fake_key = "AIzaSyFakeSecretKeyValueForTesting99887766"
    ct = runtime.vault.encrypt(fake_key)
    assert fake_key not in ct
    assert runtime.vault.decrypt(ct) == fake_key
    assert mask_api_key(fake_key) == "AIza...7766"

    scrubbed = redact_secrets({"msg": f"Failed using key {fake_key}", "api_key": fake_key, "nested": ["Bearer tok_12345"]})
    assert fake_key not in str(scrubbed)
    assert scrubbed["api_key"] == "[REDACTED]"
    assert "[REDACTED_GOOGLE_KEY]" in scrubbed["msg"]
    assert scrubbed["nested"][0] == "Bearer [REDACTED]"

    pw_hash = hash_password("StrongPass123!")
    assert verify_password("StrongPass123!", pw_hash) is True
    assert verify_password("WrongPass!", pw_hash) is False


def test_spend_guard_blocks_billable_provider_at_zero_cap(runtime: AppRuntime) -> None:
    user = runtime.repo.create_user(
        email="guard@example.com",
        display_name="Guard Tester",
        password_hash=hash_password("GuardPass123!"),
        daily_spend_cap_usd=0.0,
    )
    # Even WITH an active server-side Google key stored, $0.00 cap MUST block billable submission!
    runtime.repo.upsert_credential(
        user_id=user.id,
        provider="google",
        encrypted_key=runtime.vault.encrypt("AIzaSyFakeTestKeyNotReal00001111"),
        masked_key="AIza...1111",
    )
    project = runtime.repo.create_project(user.id, "Spend Guard Test")
    cap = runtime.providers.resolve_capability(MediaType.IMAGE, "google_gemini_image", "gemini-nano-banana-2.1")
    brief = BriefInput(project_id=project.id, media_type=MediaType.IMAGE, prompt_text="Glass perfume bottle on dark slate", aspect_ratio="1:1")
    bid = runtime.repo.save_brief(user.id, project.id, MediaType.IMAGE, brief.prompt_text, brief.model_dump())
    plan = runtime.engine.create_plan(brief_id=bid, brief=brief, references=[], capability=cap)
    runtime.repo.save_plan(user.id, plan)

    quote = runtime.jobs.request_quote(user=user, plan=plan, provider_id=cap.provider_id, model_id=cap.model_id)
    assert quote.is_billable is True
    assert quote.spend_guard_allows is False

    with pytest.raises(ProviderAdapterError) as exc_info:
        runtime.jobs.submit_approved_job(
            user=user,
            plan=plan,
            quote_id=quote.quote_id,
            confirmation_token=quote.confirmation_token,
            explicit_user_confirmed=True,
        )
    assert exc_info.value.category == ErrorCategory.SPEND_GUARD


def test_explicit_confirmation_and_tampered_token_rejected(runtime: AppRuntime) -> None:
    user = runtime.repo.create_user(
        email="confirm@example.com",
        display_name="Confirm Tester",
        password_hash=hash_password("ConfirmPass123!"),
    )
    project = runtime.repo.create_project(user.id, "Approval Test")
    cap = runtime.providers.resolve_capability(MediaType.IMAGE, "local_test_fixture", "local-optical-slate-v1")
    brief = BriefInput(project_id=project.id, media_type=MediaType.IMAGE, prompt_text="Studio ceramic vase", aspect_ratio="3:2")
    bid = runtime.repo.save_brief(user.id, project.id, MediaType.IMAGE, brief.prompt_text, brief.model_dump())
    plan = runtime.engine.create_plan(brief_id=bid, brief=brief, references=[], capability=cap)
    runtime.repo.save_plan(user.id, plan)
    quote = runtime.jobs.request_quote(user=user, plan=plan, provider_id=cap.provider_id, model_id=cap.model_id)

    # Rejects explicit_user_confirmed=False
    with pytest.raises(ProviderAdapterError) as exc1:
        runtime.jobs.submit_approved_job(
            user=user,
            plan=plan,
            quote_id=quote.quote_id,
            confirmation_token=quote.confirmation_token,
            explicit_user_confirmed=False,
        )
    assert exc1.value.category == ErrorCategory.APPROVAL_REQUIRED

    # Rejects tampered token
    with pytest.raises(ProviderAdapterError) as exc2:
        runtime.jobs.submit_approved_job(
            user=user,
            plan=plan,
            quote_id=quote.quote_id,
            confirmation_token="bad_token_123",
            explicit_user_confirmed=True,
        )
    assert exc2.value.category == ErrorCategory.APPROVAL_REQUIRED


def test_database_integrity_and_atomic_snapshot(runtime: AppRuntime) -> None:
    assert runtime.db.verify_integrity() == "ok"
    snap = runtime.db.create_atomic_snapshot(runtime.settings.snapshots_dir)
    assert snap["integrity"] == "ok"
    assert len(snap["sha256"]) == 64
