"""Authentication, user settings, spend-cap controls, and server-side encrypted credential vault routes."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request, Response
from pydantic import BaseModel, Field

from prodstud.api.deps import get_current_user, get_runtime
from prodstud.domain.models import CredentialSummary, UserProfile
from prodstud.runtime import AppRuntime
from prodstud.security import (
    generate_session_token,
    hash_password,
    hash_session_token,
    mask_api_key,
    verify_password,
)
from prodstud.storage.database import utcnow_iso

router = APIRouter(tags=["auth_and_settings"])

SESSION_COOKIE = "prodstud_session"


class RegisterPayload(BaseModel):
    email: str = Field(..., min_length=4, max_length=200)
    display_name: str = Field(..., min_length=1, max_length=120)
    password: str = Field(..., min_length=8, max_length=128)


class LoginPayload(BaseModel):
    email: str
    password: str


class SettingsUpdatePayload(BaseModel):
    display_name: str | None = Field(default=None, min_length=1, max_length=120)
    daily_spend_cap_usd: float | None = Field(default=None, ge=0.0, le=10000.0)
    preferred_theme: str | None = Field(default=None, pattern="^(dark|light)$")


class CredentialUpsertPayload(BaseModel):
    provider: str = Field(default="google", pattern="^[a-z0-9_\\-]{2,40}$")
    api_key: str = Field(..., min_length=8, max_length=512)


_DUMMY_PASSWORD_HASH = hash_password("DummyTimingProtection!2026")


@router.post("/api/auth/register")
def register(
    payload: RegisterPayload,
    response: Response,
    rt: AppRuntime = Depends(get_runtime),
) -> dict:
    if "@" not in payload.email:
        raise HTTPException(status_code=422, detail="Please enter a valid email address.")
    if rt.repo.get_user_row_by_email(payload.email):
        raise HTTPException(status_code=409, detail="An account with this email already exists.")

    try:
        pw_hash = hash_password(payload.password)
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc

    user = rt.repo.create_user(
        email=payload.email,
        display_name=payload.display_name,
        password_hash=pw_hash,
        daily_spend_cap_usd=rt.settings.default_daily_spend_cap_usd,
    )
    raw_token = generate_session_token()
    rt.repo.create_session(user.id, hash_session_token(raw_token))
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="user_registered",
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email, "default_daily_spend_cap_usd": user.daily_spend_cap_usd},
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=rt.settings.is_production,
        max_age=72 * 3600,
    )
    return {"user": user.model_dump()}


@router.post("/api/auth/login")
def login(
    payload: LoginPayload,
    response: Response,
    rt: AppRuntime = Depends(get_runtime),
) -> dict:
    row = rt.repo.get_user_row_by_email(payload.email)
    if not row:
        verify_password(payload.password, _DUMMY_PASSWORD_HASH)
        raise HTTPException(status_code=401, detail="Invalid email or password.")
    if not verify_password(payload.password, row["password_hash"]):
        raise HTTPException(status_code=401, detail="Invalid email or password.")

    raw_token = generate_session_token()
    rt.repo.create_session(row["id"], hash_session_token(raw_token))
    user = rt.repo.get_user_profile(row["id"])
    assert user is not None
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="user_logged_in",
        entity_type="user",
        entity_id=user.id,
        payload={"email": user.email},
    )
    response.set_cookie(
        key=SESSION_COOKIE,
        value=raw_token,
        httponly=True,
        samesite="lax",
        secure=rt.settings.is_production,
        max_age=72 * 3600,
    )
    return {"user": user.model_dump()}


@router.post("/api/auth/logout")
def logout(
    request: Request,
    response: Response,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict:
    raw_token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header[7:].strip()
    if not raw_token:
        raw_token = request.cookies.get(SESSION_COOKIE)
    if raw_token:
        rt.repo.delete_session(hash_session_token(raw_token))
    response.delete_cookie(SESSION_COOKIE)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="user_logged_out",
        entity_type="user",
        entity_id=user.id,
        payload={"server_session_revoked": bool(raw_token)},
    )
    return {"status": "logged_out"}


@router.get("/api/auth/session")
def session_state(
    request: Request,
    rt: AppRuntime = Depends(get_runtime),
) -> dict:
    raw_token = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header[7:].strip()
    if not raw_token:
        raw_token = request.cookies.get(SESSION_COOKIE)
    if not raw_token:
        return {"authenticated": False, "user": None}
    user_id = rt.repo.get_user_id_for_session(hash_session_token(raw_token))
    if not user_id:
        return {"authenticated": False, "user": None}
    profile = rt.repo.get_user_profile(user_id)
    if not profile:
        return {"authenticated": False, "user": None}
    return {
        "authenticated": True,
        "user": profile.model_dump(),
        "environment": rt.settings.env,
        "local_test_fixture_enabled": rt.settings.enable_local_fixture,
        "storage_usage_bytes": rt.store.total_usage_bytes(),
    }


@router.get("/api/auth/me")
def me(
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict:
    return {
        "user": user.model_dump(),
        "environment": rt.settings.env,
        "local_test_fixture_enabled": rt.settings.enable_local_fixture,
        "storage_usage_bytes": rt.store.total_usage_bytes(),
    }


@router.patch("/api/settings")
def update_settings(
    payload: SettingsUpdatePayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> UserProfile:
    updated = rt.repo.update_user_settings(
        user.id,
        display_name=payload.display_name,
        daily_spend_cap_usd=payload.daily_spend_cap_usd,
        preferred_theme=payload.preferred_theme,
    )
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="user_settings_updated",
        entity_type="user",
        entity_id=user.id,
        payload={
            "daily_spend_cap_usd": updated.daily_spend_cap_usd,
            "preferred_theme": updated.preferred_theme,
        },
    )
    return updated


@router.get("/api/settings/credentials")
def list_credentials(
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[CredentialSummary]:
    # Strictly returns masked summaries only — NEVER returns plaintext keys or ciphertext!
    return rt.repo.list_credentials(user.id)


@router.post("/api/settings/credentials")
def save_credential(
    payload: CredentialUpsertPayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> CredentialSummary:
    encrypted = rt.vault.encrypt(payload.api_key)
    masked = mask_api_key(payload.api_key)
    summary = rt.repo.upsert_credential(
        user_id=user.id,
        provider=payload.provider,
        encrypted_key=encrypted,
        masked_key=masked,
        validation_note="Stored encrypted server-side; run Validate to verify connectivity.",
    )
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="provider_credential_saved",
        entity_type="provider_credential",
        entity_id=payload.provider,
        payload={"provider": payload.provider, "masked_key": masked},
    )
    return summary


@router.post("/api/settings/credentials/{provider}/validate")
def validate_credential(
    provider: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict:
    row = rt.repo.get_credential_row(user.id, provider)
    if not row or row["status"] != "active" or not row["encrypted_key"]:
        raise HTTPException(status_code=404, detail=f"No active credential found for '{provider}'.")
    plaintext = rt.vault.decrypt(row["encrypted_key"])
    if provider == "google":
        adapter = rt.providers.get_image_adapter("google_gemini_image")
        ok, note = adapter.validate_credential(plaintext)
    else:
        ok, note = True, f"Credential decrypted cleanly for provider '{provider}'."
    now = utcnow_iso()
    rt.repo.update_credential_validation(user.id, provider, now, note)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="provider_credential_validated",
        entity_type="provider_credential",
        entity_id=provider,
        payload={"provider": provider, "valid": ok, "note": note},
    )
    return {"provider": provider, "valid": ok, "note": note, "validated_at": now}


@router.delete("/api/settings/credentials/{provider}")
def revoke_credential(
    provider: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict:
    revoked = rt.repo.revoke_credential(user.id, provider)
    if not revoked:
        raise HTTPException(status_code=404, detail=f"No credential found for '{provider}'.")
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="provider_credential_revoked",
        entity_type="provider_credential",
        entity_id=provider,
        payload={"provider": provider},
    )
    return {"provider": provider, "status": "revoked"}
