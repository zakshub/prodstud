"""Durable JobService: persists intent before provider dispatch, handles async video polling, and blocks blind paid retries."""

from __future__ import annotations

import threading
import time
from typing import Any
from uuid import uuid4

from prodstud.domain.enums import ErrorCategory, JobStatus, MediaType
from prodstud.domain.models import (
    ApprovalQuote,
    GeneratedAssetRecord,
    GenerationJobRecord,
    ProductionPlanRecord,
    QualityReviewRecord,
    UserProfile,
)
from prodstud.engine.quality_reviewer import review_asset
from prodstud.providers.base import ProviderAdapterError, ReferencePayload
from prodstud.providers.policy_gate import PolicyEvaluationGate
from prodstud.providers.registry import ProviderRegistry
from prodstud.security import SecretVault, redact_secrets
from prodstud.storage.asset_store import AssetStore
from prodstud.storage.database import utcnow_iso
from prodstud.storage.repositories import Repository


class JobService:
    """Orchestrates explicit-approval generation jobs with durable SQLite state transitions."""

    def __init__(
        self,
        *,
        repo: Repository,
        store: AssetStore,
        vault: SecretVault,
        providers: ProviderRegistry,
        policy_gate: PolicyEvaluationGate,
    ):
        self.repo = repo
        self.store = store
        self.vault = vault
        self.providers = providers
        self.policy_gate = policy_gate

    def _load_references(self, user_id: str, plan: ProductionPlanRecord) -> list[ReferencePayload]:
        brief_payload = self.repo.get_brief_payload(user_id, plan.brief_id) or {}
        ref_ids = brief_payload.get("reference_ids") or []
        rows = self.repo.get_reference_rows(user_id, plan.project_id, ref_ids)
        out: list[ReferencePayload] = []
        for r in rows:
            out.append(
                ReferencePayload(
                    reference_id=r["id"],
                    filename=r["filename"],
                    role=r["role"],
                    mime_type=r["mime_type"],
                    data=self.store.read_bytes(r["storage_relpath"]),
                )
            )
        return out

    def _decrypt_api_key(self, user_id: str, provider_id: str) -> str | None:
        key_slot = self.providers.credential_provider_key(provider_id)
        row = self.repo.get_credential_row(user_id, key_slot)
        if not row or row["status"] != "active" or not row["encrypted_key"]:
            return None
        return self.vault.decrypt(row["encrypted_key"])

    def request_quote(
        self,
        *,
        user: UserProfile,
        plan: ProductionPlanRecord,
        provider_id: str | None = None,
        model_id: str | None = None,
    ) -> ApprovalQuote:
        cap = self.providers.resolve_capability(
            plan.media_type,
            provider_id or plan.recommended_provider,
            model_id or plan.recommended_model,
        )
        refs = self._load_references(user.id, plan)
        adapter = (
            self.providers.get_image_adapter(cap.provider_id)
            if plan.media_type == MediaType.IMAGE
            else self.providers.get_video_adapter(cap.provider_id)
        )
        val_errors = adapter.validate_request(plan, cap.model_id, refs)
        key_slot = self.providers.credential_provider_key(cap.provider_id)
        cred_row = self.repo.get_credential_row(user.id, key_slot)
        has_cred = bool(cred_row and cred_row["status"] == "active" and cred_row["encrypted_key"])

        quote = self.policy_gate.create_quote(
            user=user,
            plan=plan,
            capability=cap,
            has_active_credential=has_cred,
            validation_errors=val_errors,
        )
        self.repo.save_quote(user.id, quote)
        self.repo.record_audit(
            user_id=user.id,
            project_id=plan.project_id,
            event_type="approval_quote_created",
            entity_type="approval_quote",
            entity_id=quote.quote_id,
            payload={
                "plan_id": plan.id,
                "provider_id": cap.provider_id,
                "model_id": cap.model_id,
                "is_billable": cap.is_billable,
                "estimated_cost_usd": quote.estimated_cost_usd,
                "spend_guard_allows": quote.spend_guard_allows,
            },
        )
        return quote

    def submit_approved_job(
        self,
        *,
        user: UserProfile,
        plan: ProductionPlanRecord,
        quote_id: str,
        confirmation_token: str,
        explicit_user_confirmed: bool,
        idempotency_key: str | None = None,
        parent_asset_id: str | None = None,
        run_async: bool = False,
    ) -> tuple[GenerationJobRecord, GeneratedAssetRecord | None, QualityReviewRecord | None]:
        """Verify quote, persist job intent BEFORE provider dispatch, execute safely, and persist asset + advisory QC."""
        idem_key = (idempotency_key or f"idem_{quote_id}").strip()
        existing_job = self.repo.get_job_by_idempotency(user.id, idem_key)
        if existing_job:
            # Idempotency protection: NEVER duplicate a paid submission!
            asset = self.repo.get_asset(user.id, existing_job.asset_id) if existing_job.asset_id else None
            review = self.repo.get_latest_review(user.id, existing_job.asset_id) if existing_job.asset_id else None
            return existing_job, asset, review

        qrow = self.repo.get_quote_row(user.id, quote_id)
        if not qrow:
            raise ProviderAdapterError("Approval quote not found.", category=ErrorCategory.APPROVAL_REQUIRED)
        quote = ApprovalQuote.model_validate_json(qrow["quote_json"])
        cap = self.providers.resolve_capability(plan.media_type, quote.provider_id, quote.model_id)
        refs = self._load_references(user.id, plan)
        adapter = (
            self.providers.get_image_adapter(cap.provider_id)
            if plan.media_type == MediaType.IMAGE
            else self.providers.get_video_adapter(cap.provider_id)
        )
        val_errors = adapter.validate_request(plan, cap.model_id, refs)
        api_key = self._decrypt_api_key(user.id, cap.provider_id) if cap.requires_credential else None

        # Fail-closed Policy & SpendGuard check
        self.policy_gate.verify_before_submit(
            user=user,
            plan=plan,
            capability=cap,
            quote=quote,
            submitted_token=confirmation_token,
            explicit_user_confirmed=explicit_user_confirmed,
            quote_consumed=bool(qrow["consumed"]),
            has_active_credential=bool(api_key),
            validation_errors=val_errors,
        )

        # Mark quote consumed & plan approved, then persist job intent BEFORE calling provider!
        self.repo.mark_quote_consumed(quote_id)
        plan.approved_for_generation = True
        self.repo.update_plan(user.id, plan)

        now = utcnow_iso()
        job = GenerationJobRecord(
            id=f"job_{uuid4().hex[:14]}",
            project_id=plan.project_id,
            plan_id=plan.id,
            provider_id=cap.provider_id,
            model_id=cap.model_id,
            media_type=plan.media_type,
            status=JobStatus.SUBMITTED,
            idempotency_key=idem_key,
            is_billable=cap.is_billable,
            is_local_test_fixture=cap.is_local_test_fixture,
            estimated_cost_usd=quote.estimated_cost_usd,
            diagnostics={"quote_id": quote_id, "parent_asset_id": parent_asset_id},
            created_at=now,
            updated_at=now,
        )
        self.repo.create_job(user.id, job)
        self.repo.record_audit(
            user_id=user.id,
            project_id=plan.project_id,
            event_type="generation_job_submitted",
            entity_type="generation_job",
            entity_id=job.id,
            payload={
                "plan_id": plan.id,
                "provider_id": cap.provider_id,
                "model_id": cap.model_id,
                "is_billable": cap.is_billable,
                "idempotency_key": idem_key,
            },
        )

        if run_async:
            thread = threading.Thread(
                target=self._execute_job_worker,
                args=(user.id, job.id, plan, cap.provider_id, cap.model_id, refs, api_key, parent_asset_id),
                daemon=True,
            )
            thread.start()
            return job, None, None

        return self._execute_job_worker(user.id, job.id, plan, cap.provider_id, cap.model_id, refs, api_key, parent_asset_id)

    def _execute_job_worker(
        self,
        user_id: str,
        job_id: str,
        plan: ProductionPlanRecord,
        provider_id: str,
        model_id: str,
        refs: list[ReferencePayload],
        api_key: str | None,
        parent_asset_id: str | None,
    ) -> tuple[GenerationJobRecord, GeneratedAssetRecord | None, QualityReviewRecord | None]:
        job = self.repo.update_job(job_id, status=JobStatus.PROCESSING)
        try:
            if plan.media_type == MediaType.IMAGE:
                adapter = self.providers.get_image_adapter(provider_id)
                result = adapter.submit(
                    plan=plan,
                    model_id=model_id,
                    references=refs,
                    api_key=api_key,
                    idempotency_key=job.idempotency_key,
                )
            else:
                adapter = self.providers.get_video_adapter(provider_id)
                result = adapter.submit(
                    plan=plan,
                    model_id=model_id,
                    references=refs,
                    api_key=api_key,
                    idempotency_key=job.idempotency_key,
                )
                if result.status in {JobStatus.QUEUED, JobStatus.PROCESSING} and result.provider_job_id:
                    job = self.repo.update_job(
                        job_id,
                        status=result.status,
                        provider_job_id=result.provider_job_id,
                        diagnostics=result.diagnostics,
                    )
                    # Local fixture completes on first poll; real remote async video stays processing for client poll
                    if job.is_local_test_fixture:
                        time.sleep(0.05)
                        result = adapter.poll_status(
                            provider_job_id=result.provider_job_id,
                            model_id=model_id,
                            api_key=api_key,
                        )
                    else:
                        return job, None, None

            return self._finalize_success(user_id, job, plan, result, parent_asset_id)

        except ProviderAdapterError as exc:
            # CRITICAL BILLING SAFETY: Timeout/uncertain acceptance transitions to UNKNOWN, NEVER auto-retried!
            next_status = JobStatus.UNKNOWN if exc.provider_may_have_accepted else JobStatus.FAILED
            job = self.repo.update_job(
                job_id,
                status=next_status,
                provider_job_id=exc.provider_job_id,
                error_category=exc.category,
                error_message=str(exc),
                provider_may_have_accepted=exc.provider_may_have_accepted,
            )
            self.repo.record_audit(
                user_id=user_id,
                project_id=plan.project_id,
                event_type=f"generation_job_{next_status.value}",
                entity_type="generation_job",
                entity_id=job_id,
                payload={
                    "error_category": exc.category.value,
                    "provider_may_have_accepted": exc.provider_may_have_accepted,
                    "message": redact_secrets(str(exc)),
                },
            )
            return job, None, None
        except Exception as exc:
            job = self.repo.update_job(
                job_id,
                status=JobStatus.FAILED,
                error_category=ErrorCategory.INTERNAL,
                error_message=f"Internal execution error: {redact_secrets(str(exc))}",
                provider_may_have_accepted=False,
            )
            return job, None, None

    def poll_job(self, user_id: str, job_id: str) -> tuple[GenerationJobRecord, GeneratedAssetRecord | None, QualityReviewRecord | None]:
        """Safely check provider job status without ever triggering duplicate paid submissions."""
        job = self.repo.get_job(user_id, job_id)
        if not job:
            raise KeyError("Job not found")
        if job.status == JobStatus.SUCCEEDED and job.asset_id:
            return job, self.repo.get_asset(user_id, job.asset_id), self.repo.get_latest_review(user_id, job.asset_id)
        if job.status not in {JobStatus.QUEUED, JobStatus.PROCESSING, JobStatus.UNKNOWN} or not job.provider_job_id:
            return job, None, None
        if job.media_type != MediaType.VIDEO:
            return job, None, None

        plan = self.repo.get_plan(user_id, job.plan_id)
        if not plan:
            return job, None, None
        adapter = self.providers.get_video_adapter(job.provider_id)
        api_key = self._decrypt_api_key(user_id, job.provider_id) if not job.is_local_test_fixture else None

        try:
            result = adapter.poll_status(provider_job_id=job.provider_job_id, model_id=job.model_id, api_key=api_key)
            if result.status == JobStatus.SUCCEEDED:
                parent_id = job.diagnostics.get("parent_asset_id")
                return self._finalize_success(user_id, job, plan, result, parent_id)
            job = self.repo.update_job(job_id, status=result.status, diagnostics=result.diagnostics)
            return job, None, None
        except ProviderAdapterError as exc:
            next_status = JobStatus.UNKNOWN if exc.provider_may_have_accepted else JobStatus.FAILED
            job = self.repo.update_job(
                job_id,
                status=next_status,
                error_category=exc.category,
                error_message=str(exc),
                provider_may_have_accepted=exc.provider_may_have_accepted,
            )
            return job, None, None

    def cancel_job(self, user_id: str, job_id: str) -> GenerationJobRecord:
        job = self.repo.get_job(user_id, job_id)
        if not job:
            raise KeyError("Job not found")
        if job.status in {JobStatus.SUCCEEDED, JobStatus.FAILED, JobStatus.CANCELLED}:
            return job
        if job.media_type == MediaType.VIDEO and job.provider_job_id:
            adapter = self.providers.get_video_adapter(job.provider_id)
            api_key = self._decrypt_api_key(user_id, job.provider_id) if not job.is_local_test_fixture else None
            adapter.cancel(provider_job_id=job.provider_job_id, api_key=api_key)
        updated = self.repo.update_job(job_id, status=JobStatus.CANCELLED, error_message="Cancelled by user.")
        self.repo.record_audit(
            user_id=user_id,
            project_id=job.project_id,
            event_type="generation_job_cancelled",
            entity_type="generation_job",
            entity_id=job_id,
            payload={"provider_job_id": job.provider_job_id},
        )
        return updated

    def _finalize_success(
        self,
        user_id: str,
        job: GenerationJobRecord,
        plan: ProductionPlanRecord,
        result: Any,
        parent_asset_id: str | None,
    ) -> tuple[GenerationJobRecord, GeneratedAssetRecord, QualityReviewRecord]:
        if not result.media_bytes or not result.mime_type:
            raise ProviderAdapterError("Provider succeeded without returning media bytes.", category=ErrorCategory.PROVIDER_REJECTED)

        stored = self.store.store_generated_media(result.media_bytes, result.mime_type)
        version_num = self.repo.next_version_number(plan.project_id, plan.media_type)
        ext = ".mp4" if plan.media_type == MediaType.VIDEO else ".png"
        prefix = "fixture_" if job.is_local_test_fixture else ""
        filename = f"{prefix}{plan.media_type.value}_v{version_num:02d}_{stored.sha256[:8]}{ext}"

        metadata = {
            "plan_version": plan.version,
            "task_mode": plan.task_mode.value,
            "summary": plan.summary,
            "provider_id": job.provider_id,
            "model_id": job.model_id,
            "is_local_test_fixture": job.is_local_test_fixture,
            "activated_protocol_codes": [p.protocol_code for p in plan.activated_protocols],
            "provider_job_id": result.provider_job_id,
            "aspect_ratio": plan.image_plan.aspect_ratio if plan.image_plan else (plan.video_plan.aspect_ratio if plan.video_plan else None),
            "resolution": plan.image_plan.resolution if plan.image_plan else (plan.video_plan.resolution if plan.video_plan else None),
            "shot_count": len(plan.video_plan.shots) if plan.video_plan else None,
        }

        asset = self.repo.create_asset(
            user_id=user_id,
            project_id=plan.project_id,
            plan_id=plan.id,
            job_id=job.id,
            parent_asset_id=parent_asset_id,
            version_number=version_num,
            media_type=plan.media_type,
            provider_id=job.provider_id,
            model_id=job.model_id,
            is_local_test_fixture=job.is_local_test_fixture,
            filename=filename,
            storage_relpath=stored.relpath,
            mime_type=stored.mime_type,
            size_bytes=stored.size_bytes,
            sha256=stored.sha256,
            width=stored.width,
            height=stored.height,
            duration_s=stored.duration_s,
            fps=stored.fps,
            metadata=metadata,
        )

        # Record spend telemetry (actual or estimated for billable; $0.00 for local fixture)
        recorded_cost = (
            float(result.reported_cost_usd or job.estimated_cost_usd or 0.0) if job.is_billable else 0.0
        )
        self.repo.record_spend(
            user_id=user_id,
            job_id=job.id,
            provider_id=job.provider_id,
            model_id=job.model_id,
            estimated_cost_usd=float(job.estimated_cost_usd or 0.0),
            reported_cost_usd=recorded_cost,
        )

        # Run automatic Advisory Quality Review on the newly stored real file
        review = review_asset(asset=asset, plan=plan, file_path=stored.full_path)
        self.repo.save_quality_review(user_id, review)

        job = self.repo.update_job(
            job.id,
            status=JobStatus.SUCCEEDED,
            provider_job_id=result.provider_job_id,
            asset_id=asset.id,
            diagnostics=result.diagnostics,
        )
        self.repo.record_audit(
            user_id=user_id,
            project_id=plan.project_id,
            event_type="generation_job_succeeded",
            entity_type="generated_asset",
            entity_id=asset.id,
            payload={
                "job_id": job.id,
                "version_number": version_num,
                "sha256": stored.sha256,
                "advisory_verdict": review.advisory_verdict.value,
                "recorded_cost_usd": recorded_cost,
            },
        )
        return job, asset, review
