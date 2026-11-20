"""Project workspace, reference asset uploads, asset library search/collections, and reusable templates routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel, Field

from prodstud.api.deps import get_current_user, get_runtime
from prodstud.domain.enums import MediaType, ReferenceRole
from prodstud.domain.models import (
    GeneratedAssetRecord,
    ProductionTemplateRecord,
    ProjectRecord,
    ReferenceAssetRecord,
    UserProfile,
)
from prodstud.runtime import AppRuntime
from prodstud.security import sanitize_download_filename
from prodstud.storage.asset_store import MediaValidationError

router = APIRouter(tags=["projects_and_assets"])


class ProjectCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=160)
    description: str = Field(default="", max_length=1000)


class ProjectUpdatePayload(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    description: str | None = Field(default=None, max_length=1000)
    archived: bool | None = None


class AssetOrganizePayload(BaseModel):
    tags: list[str] | None = None
    collection_name: str | None = None
    is_favorite: bool | None = None
    accepted: bool | None = None


class TemplateCreatePayload(BaseModel):
    name: str = Field(..., min_length=1, max_length=140)
    media_type: MediaType
    description: str = Field(default="", max_length=500)
    default_brief: dict[str, Any] = Field(default_factory=dict)


@router.get("/api/projects")
def list_projects(
    include_archived: bool = Query(default=False),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[ProjectRecord]:
    return rt.repo.list_projects(user.id, include_archived=include_archived)


@router.post("/api/projects", status_code=201)
def create_project(
    payload: ProjectCreatePayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ProjectRecord:
    project = rt.repo.create_project(user.id, payload.name, payload.description)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=project.id,
        event_type="project_created",
        entity_type="project",
        entity_id=project.id,
        payload={"name": project.name},
    )
    return project


@router.get("/api/projects/{project_id}")
def get_project_workspace(
    project_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    project = rt.repo.get_project(user.id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    return {
        "project": project.model_dump(),
        "references": [r.model_dump() for r in rt.repo.list_references(user.id, project_id)],
        "plans": [p.model_dump() for p in rt.repo.list_plans(user.id, project_id)],
        "jobs": [j.model_dump() for j in rt.repo.list_jobs(user.id, project_id)],
        "assets": [a.model_dump() for a in rt.repo.list_assets(user.id, project_id=project_id)],
        "revisions": [rv.model_dump() for rv in rt.repo.list_revisions(user.id, project_id)],
    }


@router.patch("/api/projects/{project_id}")
def update_project(
    project_id: str,
    payload: ProjectUpdatePayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ProjectRecord:
    updated = rt.repo.update_project(
        user.id,
        project_id,
        name=payload.name,
        description=payload.description,
        archived=payload.archived,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Project not found.")
    rt.repo.record_audit(
        user_id=user.id,
        project_id=project_id,
        event_type="project_updated",
        entity_type="project",
        entity_id=project_id,
        payload={"name": updated.name, "archived": updated.archived},
    )
    return updated


@router.post("/api/projects/{project_id}/references", status_code=201)
async def upload_reference(
    project_id: str,
    file: UploadFile = File(...),
    role: ReferenceRole = Form(default=ReferenceRole.STYLE),
    rights_confirmed: bool = Form(default=True),
    notes: str = Form(default=""),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ReferenceAssetRecord:
    project = rt.repo.get_project(user.id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    raw_bytes = await file.read()
    try:
        stored = rt.store.store_reference_image(raw_bytes, declared_mime=file.content_type)
    except MediaValidationError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    safe_name = sanitize_download_filename(file.filename or "", fallback=f"reference_{stored.sha256[:8]}.png")
    ref = rt.repo.create_reference(
        project_id=project_id,
        user_id=user.id,
        filename=safe_name,
        storage_relpath=stored.relpath,
        mime_type=stored.mime_type,
        size_bytes=stored.size_bytes,
        sha256=stored.sha256,
        width=stored.width,
        height=stored.height,
        role=role,
        rights_confirmed=rights_confirmed,
        notes=notes,
    )
    rt.repo.record_audit(
        user_id=user.id,
        project_id=project_id,
        event_type="reference_uploaded",
        entity_type="reference_asset",
        entity_id=ref.id,
        payload={"filename": ref.filename, "role": role.value, "rights_confirmed": rights_confirmed, "sha256": ref.sha256},
    )
    return ref


@router.get("/api/references/{reference_id}/file")
def get_reference_file(
    reference_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> FileResponse:
    row = rt.repo.get_reference_row(user.id, reference_id)
    if not row:
        raise HTTPException(status_code=404, detail="Reference asset not found.")
    full_path = rt.store.resolve(row["storage_relpath"])
    return FileResponse(full_path, media_type=row["mime_type"], filename=sanitize_download_filename(row["filename"]))


@router.get("/api/assets")
def search_assets(
    project_id: str | None = Query(default=None),
    media_type: MediaType | None = Query(default=None),
    tag: str | None = Query(default=None),
    collection_name: str | None = Query(default=None),
    favorite_only: bool = Query(default=False),
    q: str | None = Query(default=None),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[GeneratedAssetRecord]:
    return rt.repo.list_assets(
        user.id,
        project_id=project_id,
        media_type=media_type,
        tag=tag,
        collection_name=collection_name,
        favorite_only=favorite_only,
        query=q,
    )


@router.patch("/api/assets/{asset_id}")
def organize_asset(
    asset_id: str,
    payload: AssetOrganizePayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> GeneratedAssetRecord:
    updated = rt.repo.update_asset_organization(
        user.id,
        asset_id,
        tags=payload.tags,
        collection_name=payload.collection_name,
        is_favorite=payload.is_favorite,
        accepted=payload.accepted,
    )
    if not updated:
        raise HTTPException(status_code=404, detail="Asset not found.")
    rt.repo.record_audit(
        user_id=user.id,
        project_id=updated.project_id,
        event_type="asset_updated",
        entity_type="generated_asset",
        entity_id=asset_id,
        payload={"tags": updated.tags, "collection_name": updated.collection_name, "is_favorite": updated.is_favorite, "accepted": updated.accepted},
    )
    return updated


@router.get("/api/templates")
def list_templates(
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[ProductionTemplateRecord]:
    return rt.repo.list_templates(user.id)


@router.post("/api/templates", status_code=201)
def create_template(
    payload: TemplateCreatePayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ProductionTemplateRecord:
    tpl = rt.repo.create_template(
        user_id=user.id,
        name=payload.name,
        media_type=payload.media_type,
        description=payload.description,
        default_brief=payload.default_brief,
    )
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="template_created",
        entity_type="production_template",
        entity_id=tpl.id,
        payload={"name": tpl.name, "media_type": tpl.media_type.value},
    )
    return tpl
