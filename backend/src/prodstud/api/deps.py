"""FastAPI dependency injectors for runtime and authenticated user resolution."""

from __future__ import annotations

from fastapi import Depends, HTTPException, Request

from prodstud.domain.models import UserProfile
from prodstud.runtime import AppRuntime
from prodstud.security import hash_session_token


def get_runtime(request: Request) -> AppRuntime:
    return request.app.state.runtime


def get_current_user(request: Request, rt: AppRuntime = Depends(get_runtime)) -> UserProfile:
    raw_token: str | None = None
    auth_header = request.headers.get("Authorization", "")
    if auth_header.lower().startswith("bearer "):
        raw_token = auth_header[7:].strip()
    if not raw_token:
        raw_token = request.cookies.get("prodstud_session")
    if not raw_token:
        raise HTTPException(status_code=401, detail="Authentication required.")

    user_id = rt.repo.get_user_id_for_session(hash_session_token(raw_token))
    if not user_id:
        raise HTTPException(status_code=401, detail="Session expired or invalid. Please sign in again.")
    profile = rt.repo.get_user_profile(user_id)
    if not profile:
        raise HTTPException(status_code=401, detail="User account not found.")
    return profile
