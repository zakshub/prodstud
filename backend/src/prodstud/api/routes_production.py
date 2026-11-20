"""Production planning, explicit approval quotes, generation jobs, advisory QC, revisions, comparison, and export routes."""

from __future__ import annotations

from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import FileResponse, Response
from pydantic import BaseModel, Field

from prodstud.api.deps import get_current_user, get_runtime
from prodstud.domain.enums import ErrorCategory, MediaType
from prodstud.domain.models import (
    ApprovalQuote,
    AuditEventRecord,
    BatchApprovalQuote,
    BatchExecutionRecord,
    BriefInput,
    ImagePlanDetails,
    ProductionPlanRecord,
    ProviderModelCapability,
    QualityReviewRecord,
    RevisionRequest,
    UserProfile,
    VideoExtensionRequest,
    VideoSequencePlan,
    VisionQCQuote,
)
from prodstud.engine.revision_engine import apply_targeted_revision
from prodstud.engine.video_planner import build_video_extension_plan, revalidate_plan_against_capability
from prodstud.providers.base import ProviderAdapterError
from prodstud.runtime import AppRuntime
from prodstud.security import redact_secrets, sanitize_download_filename

router = APIRouter(tags=["production_workflow"])


class PlanUpdatePayload(BaseModel):
    summary: str | None = None
    image_plan: ImagePlanDetails | None = None
    video_plan: VideoSequencePlan | None = None
    recommended_provider: str | None = None
    recommended_model: str | None = None


class QuoteRequestPayload(BaseModel):
    provider_id: str | None = None
    model_id: str | None = None
    variation_count: int = Field(default=1, ge=1, le=4)


class GenerateSubmitPayload(BaseModel):
    quote_id: str
    confirmation_token: str
    explicit_user_confirmed: bool
    idempotency_key: str | None = None
    parent_asset_id: str | None = None
    run_async: bool = False


class BatchItemInput(BaseModel):
    plan_id: str
    provider_id: str | None = None
    model_id: str | None = None
    variation_count: int = Field(default=1, ge=1, le=4)


class BatchQuoteRequestPayload(BaseModel):
    items: list[BatchItemInput] = Field(..., min_length=1, max_length=12)


class BatchExecutePayload(BaseModel):
    batch_quote_id: str
    confirmation_token: str
    explicit_user_confirmed: bool


class VisionQCRunPayload(BaseModel):
    quote_id: str
    confirmation_token: str
    explicit_user_confirmed: bool


class HumanFeedbackPayload(BaseModel):
    status: str = Field(..., pattern="^(accepted|rejected|needs_rework)$")
    note: str = Field(default="", max_length=1500)


class BulkExportPayload(BaseModel):
    asset_ids: list[str] = Field(..., min_length=1, max_length=50)


def _provider_error_to_http(exc: ProviderAdapterError) -> HTTPException:
    status_code = (
        402
        if exc.category == ErrorCategory.SPEND_GUARD
        else 403
        if exc.category in {ErrorCategory.APPROVAL_REQUIRED, ErrorCategory.PROVIDER_AUTH}
        else 400
    )
    return HTTPException(
        status_code=status_code,
        detail={"category": exc.category.value, "message": redact_secrets(str(exc))},
    )


def _refresh_plan_feasibility(rt: AppRuntime, user_id: str, plan: ProductionPlanRecord) -> None:
    try:
        cap = rt.providers.resolve_capability(plan.media_type, plan.recommended_provider, plan.recommended_model)
    except ValueError as exc:
        plan.feasibility_ok = False
        plan.feasibility_warnings = [str(exc)]
        return
    brief_payload = rt.repo.get_brief_payload(user_id, plan.brief_id) or {}
    ref_ids = brief_payload.get("reference_ids") or []
    ref_rows = rt.repo.get_reference_rows(user_id, plan.project_id, ref_ids)
    has_start_end = any(r["role"] == "start_frame" for r in ref_rows) and any(r["role"] == "end_frame" for r in ref_rows)
    ok, warnings = revalidate_plan_against_capability(
        plan,
        cap,
        ref_count=len(ref_rows),
        has_start_and_end_refs=has_start_end,
    )
    plan.feasibility_ok = ok
    plan.feasibility_warnings = warnings


@router.get("/api/capabilities")
def list_capabilities(
    media_type: MediaType | None = Query(default=None),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[ProviderModelCapability]:
    return rt.providers.list_capabilities(media_type)


@router.get("/api/protocols/summary")
def protocol_summary(
    layer: str | None = Query(default=None),
    disposition: str | None = Query(default=None),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    # Customer-safe semantic protocol view (does not expose private repo topology or internal prompts)
    summary = rt.protocols.summary()
    items = []
    for p in rt.protocols.entries:
        if layer and not p.source_layer.lower().startswith(layer.lower()):
            continue
        if disposition and p.disposition.value != disposition.lower():
            continue
        items.append(
            {
                "protocol_id": p.protocol_id,
                "protocol_code": p.protocol_code,
                "canonical_title": p.canonical_title,
                "source_layer": p.source_layer,
                "disposition": p.disposition.value,
                "decision_fields": p.decision_fields,
                "original_description": p.original_description,
            }
        )
    return {
        "registry_version": summary["registry_version"],
        "total_protocols": summary["total_protocols"],
        "dispositions": summary["dispositions"],
        "layers": summary["layers"],
        "protocols": items,
    }


@router.post("/api/projects/{project_id}/plans", status_code=201)
def create_production_plan(
    project_id: str,
    brief: BriefInput,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ProductionPlanRecord:
    if brief.project_id != project_id:
        brief = brief.model_copy(update={"project_id": project_id})
    project = rt.repo.get_project(user.id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")

    ref_rows = rt.repo.get_reference_rows(user.id, project_id, brief.reference_ids)
    refs = [rt.repo._row_to_reference(r) for r in ref_rows]

    try:
        cap = rt.providers.resolve_capability(brief.media_type, brief.provider_id, brief.model_id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    brief_id = rt.repo.save_brief(user.id, project_id, brief.media_type, brief.prompt_text, brief.model_dump())
    plan = rt.engine.create_plan(brief_id=brief_id, brief=brief, references=refs, capability=cap)
    rt.repo.save_plan(user.id, plan)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=project_id,
        event_type="production_plan_created",
        entity_type="production_plan",
        entity_id=plan.id,
        payload={
            "media_type": plan.media_type.value,
            "task_mode": plan.task_mode.value,
            "activated_protocols_count": len(plan.activated_protocols),
            "feasibility_ok": plan.feasibility_ok,
            "contradictions_count": len(plan.contradictions),
        },
    )
    return plan


@router.get("/api/plans/{plan_id}")
def get_plan(
    plan_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ProductionPlanRecord:
    plan = rt.repo.get_plan(user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found.")
    return plan


@router.patch("/api/plans/{plan_id}")
def edit_plan(
    plan_id: str,
    payload: PlanUpdatePayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ProductionPlanRecord:
    plan = rt.repo.get_plan(user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found.")
    if payload.summary is not None:
        plan.summary = payload.summary
    if payload.image_plan is not None and plan.media_type == MediaType.IMAGE:
        plan.image_plan = payload.image_plan
    if payload.video_plan is not None and plan.media_type == MediaType.VIDEO:
        plan.video_plan = payload.video_plan
    if payload.recommended_provider is not None:
        plan.recommended_provider = payload.recommended_provider
    if payload.recommended_model is not None:
        plan.recommended_model = payload.recommended_model
    # Re-validate feasibility immediately after edit and require fresh generation approval
    _refresh_plan_feasibility(rt, user.id, plan)
    plan.approved_for_generation = False
    updated = rt.repo.update_plan(user.id, plan)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=plan.project_id,
        event_type="production_plan_edited",
        entity_type="production_plan",
        entity_id=plan.id,
        payload={"version": plan.version, "feasibility_ok": plan.feasibility_ok},
    )
    return updated


@router.post("/api/plans/{plan_id}/quote")
def create_approval_quote(
    plan_id: str,
    payload: QuoteRequestPayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ApprovalQuote:
    plan = rt.repo.get_plan(user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found.")
    try:
        return rt.jobs.request_quote(
            user=user,
            plan=plan,
            provider_id=payload.provider_id,
            model_id=payload.model_id,
            variation_count=payload.variation_count,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/plans/{plan_id}/generate")
def submit_generation(
    plan_id: str,
    payload: GenerateSubmitPayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    plan = rt.repo.get_plan(user.id, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Production plan not found.")
    try:
        jobs, assets, reviews = rt.jobs.submit_approved_variations(
            user=user,
            plan=plan,
            quote_id=payload.quote_id,
            confirmation_token=payload.confirmation_token,
            explicit_user_confirmed=payload.explicit_user_confirmed,
            idempotency_key=payload.idempotency_key,
            parent_asset_id=payload.parent_asset_id,
            run_async=payload.run_async,
        )
    except ProviderAdapterError as exc:
        raise _provider_error_to_http(exc) from exc

    return {
        "job": jobs[0].model_dump(),
        "asset": assets[0].model_dump() if assets else None,
        "quality_review": reviews[0].model_dump() if reviews else None,
        "jobs": [j.model_dump() for j in jobs],
        "assets": [a.model_dump() for a in assets],
        "quality_reviews": [r.model_dump() for r in reviews],
    }


@router.post("/api/projects/{project_id}/batches/quote")
def create_batch_approval_quote(
    project_id: str,
    payload: BatchQuoteRequestPayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> BatchApprovalQuote:
    if not rt.repo.get_project(user.id, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        return rt.jobs.request_batch_quote(
            user=user,
            project_id=project_id,
            items=[it.model_dump() for it in payload.items],
        )
    except ProviderAdapterError as exc:
        raise _provider_error_to_http(exc) from exc
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@router.post("/api/projects/{project_id}/batches/execute")
def execute_approved_batch(
    project_id: str,
    payload: BatchExecutePayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    if not rt.repo.get_project(user.id, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    try:
        batch, jobs, assets, reviews = rt.jobs.submit_approved_batch(
            user=user,
            project_id=project_id,
            batch_quote_id=payload.batch_quote_id,
            confirmation_token=payload.confirmation_token,
            explicit_user_confirmed=payload.explicit_user_confirmed,
        )
    except ProviderAdapterError as exc:
        raise _provider_error_to_http(exc) from exc
    return {
        "batch": batch.model_dump(),
        "jobs": [j.model_dump() for j in jobs],
        "assets": [a.model_dump() for a in assets],
        "quality_reviews": [r.model_dump() for r in reviews],
    }


@router.get("/api/projects/{project_id}/batches")
def list_project_batches(
    project_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[BatchExecutionRecord]:
    if not rt.repo.get_project(user.id, project_id):
        raise HTTPException(status_code=404, detail="Project not found.")
    return rt.repo.list_batches(user.id, project_id)


@router.post("/api/assets/{asset_id}/extend", status_code=201)
def create_video_extension_plan(
    asset_id: str,
    payload: VideoExtensionRequest,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> ProductionPlanRecord:
    source_asset = rt.repo.get_asset(user.id, asset_id)
    if not source_asset:
        raise HTTPException(status_code=404, detail="Source video asset not found.")
    if source_asset.media_type != MediaType.VIDEO:
        raise HTTPException(status_code=400, detail="Video extension is only supported for generated video assets.")
    source_plan = rt.repo.get_plan(user.id, source_asset.plan_id)
    if not source_plan:
        raise HTTPException(status_code=404, detail="Source video production plan not found.")

    try:
        cap = rt.providers.resolve_capability(
            MediaType.VIDEO,
            payload.provider_id or source_asset.provider_id,
            payload.model_id or source_asset.model_id,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    source_job = rt.repo.get_job(user.id, source_asset.job_id)
    pjid = source_job.provider_job_id if source_job else None

    try:
        ext_plan = build_video_extension_plan(
            source_plan=source_plan,
            source_asset=source_asset,
            continuation_prompt=payload.continuation_prompt,
            extension_duration_s=payload.extension_duration_s,
            capability=cap,
            source_provider_job_id=pjid,
        )
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc

    rt.repo.save_plan(user.id, ext_plan)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=source_asset.project_id,
        event_type="video_extension_plan_created",
        entity_type="production_plan",
        entity_id=ext_plan.id,
        payload={
            "source_asset_id": source_asset.id,
            "source_plan_id": source_plan.id,
            "extension_duration_s": payload.extension_duration_s,
            "total_duration_s": ext_plan.video_plan.total_duration_s if ext_plan.video_plan else None,
            "feasibility_ok": ext_plan.feasibility_ok,
        },
    )
    return ext_plan


@router.get("/api/jobs/{job_id}")
def get_job(
    job_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    job = rt.repo.get_job(user.id, job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Generation job not found.")
    asset = rt.repo.get_asset(user.id, job.asset_id) if job.asset_id else None
    review = rt.repo.get_latest_review(user.id, job.asset_id) if job.asset_id else None
    return {
        "job": job.model_dump(),
        "asset": asset.model_dump() if asset else None,
        "quality_review": review.model_dump() if review else None,
    }


@router.post("/api/jobs/{job_id}/poll")
def poll_job(
    job_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    try:
        job, asset, review = rt.jobs.poll_job(user.id, job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Generation job not found.") from exc
    return {
        "job": job.model_dump(),
        "asset": asset.model_dump() if asset else None,
        "quality_review": review.model_dump() if review else None,
    }


@router.post("/api/jobs/{job_id}/cancel")
def cancel_job(
    job_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    try:
        job = rt.jobs.cancel_job(user.id, job_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail="Generation job not found.") from exc
    return {"job": job.model_dump()}


@router.get("/api/assets/{asset_id}/file")
def get_asset_file(
    asset_id: str,
    download: bool = Query(default=False),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> FileResponse:
    row = rt.repo.get_asset_row(user.id, asset_id)
    if not row:
        raise HTTPException(status_code=404, detail="Generated asset not found.")
    full_path = rt.store.resolve(row["storage_relpath"])
    disposition = "attachment" if download else "inline"
    safe_name = sanitize_download_filename(row["filename"])
    return FileResponse(
        full_path,
        media_type=row["mime_type"],
        filename=safe_name,
        headers={"Content-Disposition": f'{disposition}; filename="{safe_name}"'},
    )


def _build_sanitized_sidecar(rt: AppRuntime, user_id: str, asset_row: dict[str, Any]) -> dict[str, Any]:
    asset = rt.repo._row_to_asset(asset_row)
    plan = rt.repo.get_plan(user_id, asset.plan_id)
    review = rt.repo.get_latest_review(user_id, asset.id)
    return redact_secrets(
        {
            "product": "Production Studio",
            "asset_id": asset.id,
            "project_id": asset.project_id,
            "version_number": asset.version_number,
            "parent_asset_id": asset.parent_asset_id,
            "media_type": asset.media_type.value,
            "filename": asset.filename,
            "mime_type": asset.mime_type,
            "sha256": asset.sha256,
            "dimensions": {"width": asset.width, "height": asset.height},
            "duration_s": asset.duration_s,
            "fps": asset.fps,
            "provider_id": asset.provider_id,
            "model_id": asset.model_id,
            "is_local_test_fixture": asset.is_local_test_fixture,
            "created_at": asset.created_at,
            "approved_plan": {
                "plan_id": plan.id,
                "version": plan.version,
                "task_mode": plan.task_mode.value,
                "summary": plan.summary,
                "activated_protocols": [p.protocol_code for p in plan.activated_protocols],
                "image_plan": plan.image_plan.model_dump() if plan.image_plan else None,
                "video_plan": plan.video_plan.model_dump() if plan.video_plan else None,
            }
            if plan
            else None,
            "advisory_quality_review": {
                "advisory_verdict": review.advisory_verdict.value,
                "weighted_score": review.weighted_score,
                "confidence": review.confidence,
                "inspection_coverage": review.inspection_coverage,
                "limitations": review.limitations,
                "human_feedback_status": review.human_feedback_status,
            }
            if review
            else None,
        }
    )


@router.get("/api/assets/{asset_id}/export")
def export_asset_package(
    asset_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> Response:
    row = rt.repo.get_asset_row(user.id, asset_id)
    if not row:
        raise HTTPException(status_code=404, detail="Generated asset not found.")
    sidecar = _build_sanitized_sidecar(rt, user.id, row)
    zip_bytes = rt.store.build_export_zip([(row["storage_relpath"], row["filename"], sidecar)])
    rt.repo.record_audit(
        user_id=user.id,
        project_id=row["project_id"],
        event_type="asset_exported",
        entity_type="generated_asset",
        entity_id=asset_id,
        payload={"filename": row["filename"]},
    )
    pkg_name = sanitize_download_filename(f"{row['filename'].rsplit('.', 1)[0]}_export.zip", fallback="asset_export.zip")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{pkg_name}"'},
    )


@router.post("/api/projects/{project_id}/export-bulk")
def export_bulk_package(
    project_id: str,
    payload: BulkExportPayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> Response:
    project = rt.repo.get_project(user.id, project_id)
    if not project:
        raise HTTPException(status_code=404, detail="Project not found.")
    items: list[tuple[str, str, dict[str, Any]]] = []
    for aid in payload.asset_ids:
        row = rt.repo.get_asset_row(user.id, aid)
        if row and row["project_id"] == project_id:
            items.append((row["storage_relpath"], row["filename"], _build_sanitized_sidecar(rt, user.id, row)))
    if not items:
        raise HTTPException(status_code=404, detail="No matching project assets found to export.")
    zip_bytes = rt.store.build_export_zip(items)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=project_id,
        event_type="assets_bulk_exported",
        entity_type="project",
        entity_id=project_id,
        payload={"count": len(items)},
    )
    safe_pkg = sanitize_download_filename(f"prodstud_{project_id}_bulk_export.zip", fallback="bulk_export.zip")
    return Response(
        content=zip_bytes,
        media_type="application/zip",
        headers={"Content-Disposition": f'attachment; filename="{safe_pkg}"'},
    )


@router.get("/api/assets/{asset_id}/review")
def get_asset_review(
    asset_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> QualityReviewRecord:
    review = rt.repo.get_latest_review(user.id, asset_id)
    if not review:
        raise HTTPException(status_code=404, detail="Quality review not found for this asset.")
    return review


@router.get("/api/assets/{asset_id}/reviews")
def list_asset_reviews(
    asset_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[QualityReviewRecord]:
    if not rt.repo.get_asset(user.id, asset_id):
        raise HTTPException(status_code=404, detail="Generated asset not found.")
    return rt.repo.list_quality_reviews(user.id, asset_id)


@router.post("/api/assets/{asset_id}/review/vision/quote")
def create_vision_qc_quote(
    asset_id: str,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> VisionQCQuote:
    try:
        return rt.jobs.request_vision_qc_quote(user=user, asset_id=asset_id)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc


@router.post("/api/assets/{asset_id}/review/vision/run")
def run_vision_qc(
    asset_id: str,
    payload: VisionQCRunPayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> QualityReviewRecord:
    try:
        return rt.jobs.run_approved_vision_qc(
            user=user,
            asset_id=asset_id,
            quote_id=payload.quote_id,
            confirmation_token=payload.confirmation_token,
            explicit_user_confirmed=payload.explicit_user_confirmed,
        )
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ProviderAdapterError as exc:
        raise _provider_error_to_http(exc) from exc


@router.post("/api/reviews/{review_id}/feedback")
def submit_human_feedback(
    review_id: str,
    payload: HumanFeedbackPayload,
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> QualityReviewRecord:
    updated = rt.repo.record_human_feedback(user.id, review_id, payload.status, payload.note)
    if not updated:
        raise HTTPException(status_code=404, detail="Quality review not found.")
    if payload.status == "accepted":
        rt.repo.update_asset_organization(user.id, updated.asset_id, accepted=True)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=None,
        event_type="quality_feedback_recorded",
        entity_type="quality_review",
        entity_id=review_id,
        payload={"status": payload.status},
    )
    return updated


@router.post("/api/plans/{plan_id}/revise", status_code=201)
def revise_plan(
    plan_id: str,
    payload: RevisionRequest,
    source_asset_id: str | None = Query(default=None),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    source_plan = rt.repo.get_plan(user.id, plan_id)
    if not source_plan:
        raise HTTPException(status_code=404, detail="Source production plan not found.")
    cap = rt.providers.resolve_capability(
        source_plan.media_type,
        source_plan.recommended_provider,
        source_plan.recommended_model,
    )
    new_plan, revision = apply_targeted_revision(
        source_plan=source_plan,
        revision_request=payload,
        source_asset_id=source_asset_id,
        capability=cap,
    )
    _refresh_plan_feasibility(rt, user.id, new_plan)
    rt.repo.save_plan(user.id, new_plan)
    rt.repo.save_revision(user.id, revision)
    rt.repo.record_audit(
        user_id=user.id,
        project_id=source_plan.project_id,
        event_type="production_plan_revised",
        entity_type="revision",
        entity_id=revision.id,
        payload={
            "source_plan_id": source_plan.id,
            "new_plan_id": new_plan.id,
            "changed_fields": revision.changed_fields,
            "preserved_count": len(revision.preserved_fields),
            "feasibility_ok": new_plan.feasibility_ok,
        },
    )
    return {"plan": new_plan.model_dump(), "revision": revision.model_dump()}


@router.get("/api/assets/compare")
def compare_assets(
    left_id: str = Query(...),
    right_id: str = Query(...),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> dict[str, Any]:
    left = rt.repo.get_asset(user.id, left_id)
    right = rt.repo.get_asset(user.id, right_id)
    if not left or not right:
        raise HTTPException(status_code=404, detail="One or both assets were not found.")
    left_plan = rt.repo.get_plan(user.id, left.plan_id)
    right_plan = rt.repo.get_plan(user.id, right.plan_id)
    left_review = rt.repo.get_latest_review(user.id, left.id)
    right_review = rt.repo.get_latest_review(user.id, right.id)

    diffs: list[dict[str, Any]] = []
    if left_plan and right_plan and left_plan.image_plan and right_plan.image_plan:
        ld = left_plan.image_plan.model_dump()
        rd = right_plan.image_plan.model_dump()
        for k in sorted(ld.keys()):
            if ld[k] != rd[k]:
                diffs.append({"field": k, "left": ld[k], "right": rd[k]})
    elif left_plan and right_plan and left_plan.video_plan and right_plan.video_plan:
        ld = left_plan.video_plan.model_dump()
        rd = right_plan.video_plan.model_dump()
        for k in ("total_duration_s", "aspect_ratio", "resolution", "extension_duration_s", "shots"):
            if ld.get(k) != rd.get(k):
                diffs.append({"field": k, "left": ld.get(k), "right": rd.get(k)})

    return {
        "left": {"asset": left.model_dump(), "plan": left_plan.model_dump() if left_plan else None, "review": left_review.model_dump() if left_review else None},
        "right": {"asset": right.model_dump(), "plan": right_plan.model_dump() if right_plan else None, "review": right_review.model_dump() if right_review else None},
        "decision_diffs": diffs,
    }


@router.get("/api/audit")
def list_audit_events(
    project_id: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    user: UserProfile = Depends(get_current_user),
    rt: AppRuntime = Depends(get_runtime),
) -> list[AuditEventRecord]:
    return rt.repo.list_audit_events(user.id, project_id=project_id, limit=limit)
