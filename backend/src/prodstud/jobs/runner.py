"""Durable JobService: persists intent before provider dispatch, handles async video polling, and blocks blind paid retries."""

from __future__ import annotations

import threading
import time
from typing import Any
from uuid import uuid4

from prodstud.domain.enums import ErrorCategory, JobStatus, MediaType
from prodstud.domain.models import (
    ApprovalQuote,
    BatchApprovalQuote,
    BatchExecutionRecord,
    GeneratedAssetRecord,
    GenerationJobRecord,
    ProductionPlanRecord,
    QualityReviewRecord,
    UserProfile,
    VisionQCQuote,
)
from prodstud.engine.quality_reviewer import review_asset
from prodstud.engine.vision_qc import DEFAULT_VISION_QC_PROVIDER, VisionQCService
from prodstud.providers.base import ProviderAdapterError, ReferencePayload
from prodstud.providers.google_vision_qc import GoogleVisionQCAdapter
from prodstud.providers.policy_gate import PolicyEvaluationGate
from prodstud.providers.registry import ProviderRegistry
from prodstud.security import SecretVault, redact_secrets
from prodstud.storage.asset_store import AssetStore
from prodstud.storage.database import utcnow_iso
from prodstud.storage.repositories import Repository

HALTING_ERROR_CATEGORIES = {
    ErrorCategory.TIMEOUT_UNKNOWN,
    ErrorCategory.PROVIDER_AUTH,
    ErrorCategory.QUOTA,
    ErrorCategory.SPEND_GUARD,
}


class JobService:
    """Orchestrates explicit-approval generation jobs, multi-output variations, batches, and optional Vision QC."""

    def __init__(
        self,
        *,
        repo: Repository,
        store: AssetStore,
        vault: SecretVault,
        providers: ProviderRegistry,
        policy_gate: PolicyEvaluationGate,
        vision_qc: VisionQCService | None = None,
    ):
        self.repo = repo
        self.store = store
        self.vault = vault
        self.providers = providers
        self.policy_gate = policy_gate
        self.vision_qc = vision_qc or VisionQCService(transport=GoogleVisionQCAdapter())

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
        variation_count: int = 1,
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
            variation_count=variation_count,
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
                "variation_count": quote.variation_count,
                "is_billable": cap.is_billable,
                "estimated_cost_usd": quote.estimated_cost_usd,
                "spend_guard_allows": quote.spend_guard_allows,
            },
        )
        return quote

    def submit_approved_variations(
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
    ) -> tuple[list[GenerationJobRecord], list[GeneratedAssetRecord], list[QualityReviewRecord]]:
        """Verify quote and submit 1..4 approved outputs with idempotency and fail-closed halt on uncertain/billing errors."""
        idem_base = (idempotency_key or f"idem_{quote_id}").strip()

        # Idempotency check for single-output and multi-output keys
        existing_single = self.repo.get_job_by_idempotency(user.id, idem_base)
        if existing_single:
            asset = self.repo.get_asset(user.id, existing_single.asset_id) if existing_single.asset_id else None
            review = self.repo.get_latest_review(user.id, existing_single.asset_id) if existing_single.asset_id else None
            return [existing_single], ([asset] if asset else []), ([review] if review else [])

        existing_v1 = self.repo.get_job_by_idempotency(user.id, f"{idem_base}_v1")
        if existing_v1:
            jobs_found: list[GenerationJobRecord] = []
            assets_found: list[GeneratedAssetRecord] = []
            reviews_found: list[QualityReviewRecord] = []
            for idx in range(1, 5):
                j = self.repo.get_job_by_idempotency(user.id, f"{idem_base}_v{idx}")
                if not j:
                    break
                jobs_found.append(j)
                if j.asset_id:
                    a = self.repo.get_asset(user.id, j.asset_id)
                    r = self.repo.get_latest_review(user.id, j.asset_id)
                    if a:
                        assets_found.append(a)
                    if r:
                        reviews_found.append(r)
            return jobs_found, assets_found, reviews_found

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

        # Fresh user spend snapshot + Fail-closed Policy & SpendGuard check
        fresh_user = self.repo.get_user_profile(user.id) or user
        self.policy_gate.verify_before_submit(
            user=fresh_user,
            plan=plan,
            capability=cap,
            quote=quote,
            submitted_token=confirmation_token,
            explicit_user_confirmed=explicit_user_confirmed,
            quote_consumed=bool(qrow["consumed"]),
            has_active_credential=bool(api_key),
            validation_errors=val_errors,
        )

        # Atomic compare-and-swap quote consumption closes concurrent replay race before any provider call
        if not self.repo.consume_quote_atomically(user.id, quote_id):
            raise ProviderAdapterError(
                "Approval quote has already been consumed. Request a fresh approval quote to prevent duplicate submissions.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        plan.approved_for_generation = True
        self.repo.update_plan(user.id, plan)

        total_variations = max(1, min(4, int(quote.variation_count)))
        effective_parent_id = parent_asset_id or (
            plan.video_plan.extended_from_asset_id if (plan.media_type == MediaType.VIDEO and plan.video_plan) else None
        )

        jobs_out: list[GenerationJobRecord] = []
        assets_out: list[GeneratedAssetRecord] = []
        reviews_out: list[QualityReviewRecord] = []

        for var_idx in range(1, total_variations + 1):
            idem_key = idem_base if total_variations == 1 else f"{idem_base}_v{var_idx}"
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
                estimated_cost_usd=quote.unit_estimated_cost_usd if total_variations > 1 else quote.estimated_cost_usd,
                diagnostics={
                    "quote_id": quote_id,
                    "parent_asset_id": effective_parent_id,
                    "variation_index": var_idx,
                    "variation_total": total_variations,
                },
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
                    "variation_index": var_idx,
                    "variation_total": total_variations,
                },
            )

            if run_async and total_variations == 1:
                thread = threading.Thread(
                    target=self._execute_job_worker,
                    args=(
                        user.id,
                        job.id,
                        plan,
                        cap.provider_id,
                        cap.model_id,
                        refs,
                        api_key,
                        effective_parent_id,
                        var_idx,
                        total_variations,
                    ),
                    daemon=True,
                )
                thread.start()
                return [job], [], []

            done_job, done_asset, done_review = self._execute_job_worker(
                user.id,
                job.id,
                plan,
                cap.provider_id,
                cap.model_id,
                refs,
                api_key,
                effective_parent_id,
                var_idx,
                total_variations,
            )
            jobs_out.append(done_job)
            if done_asset:
                assets_out.append(done_asset)
            if done_review:
                reviews_out.append(done_review)

            # Fail-closed safety: NEVER continue submitting variations after UNKNOWN or auth/quota/spend failure
            if total_variations > 1 and (
                done_job.status == JobStatus.UNKNOWN
                or (done_job.error_category in HALTING_ERROR_CATEGORIES)
            ):
                self.repo.record_audit(
                    user_id=user.id,
                    project_id=plan.project_id,
                    event_type="generation_variations_halted",
                    entity_type="approval_quote",
                    entity_id=quote_id,
                    payload={
                        "halted_after_variation": var_idx,
                        "total_variations": total_variations,
                        "status": done_job.status.value,
                        "error_category": done_job.error_category.value if done_job.error_category else None,
                    },
                )
                break

        return jobs_out, assets_out, reviews_out

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
        """Backwards-compatible single-output wrapper returning primary (job, asset, review)."""
        jobs, assets, reviews = self.submit_approved_variations(
            user=user,
            plan=plan,
            quote_id=quote_id,
            confirmation_token=confirmation_token,
            explicit_user_confirmed=explicit_user_confirmed,
            idempotency_key=idempotency_key,
            parent_asset_id=parent_asset_id,
            run_async=run_async,
        )
        return (
            jobs[0],
            assets[0] if assets else None,
            reviews[0] if reviews else None,
        )

    # ── Batch Generation with Combined Cost Approval (Phase 2) ────────────
    def _evaluate_batch_specs(
        self,
        user: UserProfile,
        project_id: str,
        item_specs: list[dict[str, Any]],
    ) -> list[tuple[ProductionPlanRecord, Any, int, bool, list[str], list[ReferencePayload]]]:
        seen_plans: set[str] = set()
        total_outputs = 0
        evaluated = []
        for spec in item_specs:
            plan_id = str(spec["plan_id"])
            if plan_id in seen_plans:
                raise ProviderAdapterError(
                    f"Duplicate plan '{plan_id}' in batch request; adjust variation_count instead of repeating plan IDs.",
                    category=ErrorCategory.VALIDATION,
                )
            seen_plans.add(plan_id)
            plan = self.repo.get_plan(user.id, plan_id)
            if not plan or plan.project_id != project_id:
                raise ProviderAdapterError(
                    f"Plan '{plan_id}' was not found in project '{project_id}'.",
                    category=ErrorCategory.VALIDATION,
                )
            cap = self.providers.resolve_capability(
                plan.media_type,
                spec.get("provider_id") or plan.recommended_provider,
                spec.get("model_id") or plan.recommended_model,
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
            count = 1 if plan.media_type == MediaType.VIDEO else max(1, min(4, int(spec.get("variation_count", 1))))
            total_outputs += count
            if total_outputs > 24:
                raise ProviderAdapterError(
                    "Batch exceeds maximum safe ceiling of 24 total outputs per approved batch.",
                    category=ErrorCategory.VALIDATION,
                )
            evaluated.append((plan, cap, count, has_cred, val_errors, refs))
        return evaluated

    def request_batch_quote(
        self,
        *,
        user: UserProfile,
        project_id: str,
        items: list[dict[str, Any]],
    ) -> BatchApprovalQuote:
        if not items or len(items) > 12:
            raise ProviderAdapterError("Batch must contain between 1 and 12 plan items.", category=ErrorCategory.VALIDATION)
        evaluated_full = self._evaluate_batch_specs(user, project_id, items)
        evaluated_gate = [(p, c, cnt, hc, ve) for (p, c, cnt, hc, ve, _) in evaluated_full]
        quote = self.policy_gate.create_batch_quote(
            user=user,
            project_id=project_id,
            evaluated_items=evaluated_gate,
        )
        self.repo.save_batch_quote(user.id, quote)
        self.repo.record_audit(
            user_id=user.id,
            project_id=project_id,
            event_type="batch_quote_created",
            entity_type="batch_quote",
            entity_id=quote.batch_quote_id,
            payload={
                "item_count": len(quote.items),
                "total_requested_outputs": quote.total_requested_outputs,
                "total_estimated_cost_usd": quote.total_estimated_cost_usd,
                "spend_guard_allows": quote.spend_guard_allows,
            },
        )
        return quote

    def submit_approved_batch(
        self,
        *,
        user: UserProfile,
        project_id: str,
        batch_quote_id: str,
        confirmation_token: str,
        explicit_user_confirmed: bool,
    ) -> tuple[BatchExecutionRecord, list[GenerationJobRecord], list[GeneratedAssetRecord], list[QualityReviewRecord]]:
        qrow = self.repo.get_batch_quote_row(user.id, batch_quote_id)
        if not qrow:
            raise ProviderAdapterError("Batch approval quote not found.", category=ErrorCategory.APPROVAL_REQUIRED)
        quote = BatchApprovalQuote.model_validate_json(qrow["quote_json"])
        if quote.project_id != project_id:
            raise ProviderAdapterError("Batch quote does not belong to this project.", category=ErrorCategory.APPROVAL_REQUIRED)

        specs = [
            {
                "plan_id": it.plan_id,
                "provider_id": it.provider_id,
                "model_id": it.model_id,
                "variation_count": it.variation_count,
            }
            for it in quote.items
        ]
        evaluated_full = self._evaluate_batch_specs(user, project_id, specs)
        evaluated_gate = [(p, c, cnt, hc, ve) for (p, c, cnt, hc, ve, _) in evaluated_full]

        # Fresh user spend snapshot before gate verification
        fresh_user = self.repo.get_user_profile(user.id) or user
        self.policy_gate.verify_batch_before_submit(
            user=fresh_user,
            quote=quote,
            submitted_token=confirmation_token,
            explicit_user_confirmed=explicit_user_confirmed,
            quote_consumed=bool(qrow["consumed"]),
            evaluated_items=evaluated_gate,
        )

        # Atomic compare-and-swap batch quote consumption closes concurrent replay race
        if not self.repo.consume_batch_quote_atomically(user.id, batch_quote_id):
            raise ProviderAdapterError(
                "Batch approval quote has already been consumed. Request a fresh batch quote.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        now = utcnow_iso()
        batch = BatchExecutionRecord(
            batch_id=f"bat_{uuid4().hex[:14]}",
            project_id=project_id,
            batch_quote_id=batch_quote_id,
            status="running",
            total_requested_outputs=quote.total_requested_outputs,
            completed_outputs=0,
            failed_outputs=0,
            halted_reason=None,
            job_ids=[],
            asset_ids=[],
            total_recorded_cost_usd=0.0,
            created_at=now,
            updated_at=now,
        )
        self.repo.save_batch(user.id, batch)

        all_jobs: list[GenerationJobRecord] = []
        all_assets: list[GeneratedAssetRecord] = []
        all_reviews: list[QualityReviewRecord] = []
        halted = False

        for item_idx, ((plan, cap, count, _hc, _ve, refs), qitem) in enumerate(zip(evaluated_full, quote.items, strict=True), start=1):
            plan.approved_for_generation = True
            self.repo.update_plan(user.id, plan)
            api_key = self._decrypt_api_key(user.id, cap.provider_id) if cap.requires_credential else None
            effective_parent = (
                plan.video_plan.extended_from_asset_id if (plan.media_type == MediaType.VIDEO and plan.video_plan) else None
            )

            for var_idx in range(1, count + 1):
                # Re-verify live Spend Guard before each billable dispatch inside the batch
                if cap.is_billable:
                    live_user = self.repo.get_user_profile(user.id) or fresh_user
                    unit_floor = qitem.unit_estimated_cost_usd if qitem.unit_estimated_cost_usd is not None else 0.01
                    if live_user.daily_spend_cap_usd <= 0.0 or (live_user.spent_today_usd + unit_floor) > live_user.daily_spend_cap_usd:
                        batch.status = "partial_halted"
                        batch.halted_reason = (
                            f"Spend Guard halted remaining batch outputs before item {item_idx} variation {var_idx} "
                            f"(today's spend ${live_user.spent_today_usd:.4f} vs cap ${live_user.daily_spend_cap_usd:.2f})."
                        )
                        halted = True
                        break

                idem_key = f"idem_{batch.batch_id}_i{item_idx}_v{var_idx}"
                jnow = utcnow_iso()
                job = GenerationJobRecord(
                    id=f"job_{uuid4().hex[:14]}",
                    project_id=project_id,
                    plan_id=plan.id,
                    provider_id=cap.provider_id,
                    model_id=cap.model_id,
                    media_type=plan.media_type,
                    status=JobStatus.SUBMITTED,
                    idempotency_key=idem_key,
                    is_billable=cap.is_billable,
                    is_local_test_fixture=cap.is_local_test_fixture,
                    estimated_cost_usd=qitem.unit_estimated_cost_usd,
                    diagnostics={
                        "batch_id": batch.batch_id,
                        "batch_quote_id": batch_quote_id,
                        "parent_asset_id": effective_parent,
                        "variation_index": var_idx,
                        "variation_total": count,
                    },
                    created_at=jnow,
                    updated_at=jnow,
                )
                self.repo.create_job(user.id, job)
                done_job, done_asset, done_review = self._execute_job_worker(
                    user.id,
                    job.id,
                    plan,
                    cap.provider_id,
                    cap.model_id,
                    refs,
                    api_key,
                    effective_parent,
                    var_idx,
                    count,
                )
                all_jobs.append(done_job)
                batch.job_ids.append(done_job.id)
                if done_asset:
                    all_assets.append(done_asset)
                    batch.asset_ids.append(done_asset.id)
                    batch.completed_outputs += 1
                    if cap.is_billable:
                        batch.total_recorded_cost_usd = round(
                            batch.total_recorded_cost_usd + float(qitem.unit_estimated_cost_usd or 0.0), 6
                        )
                elif done_job.status in {JobStatus.QUEUED, JobStatus.PROCESSING}:
                    batch.completed_outputs += 1
                else:
                    batch.failed_outputs += 1

                if done_review:
                    all_reviews.append(done_review)

                if done_job.status == JobStatus.UNKNOWN:
                    batch.status = "unknown_halted"
                    batch.halted_reason = (
                        f"Halted remaining batch outputs after job {done_job.id} entered UNKNOWN state "
                        "(provider acceptance uncertain — never blindly continue or retry)."
                    )
                    halted = True
                    break
                if done_job.error_category in HALTING_ERROR_CATEGORIES:
                    batch.status = "partial_halted"
                    batch.halted_reason = (
                        f"Halted remaining batch outputs after {done_job.error_category.value} error on job {done_job.id}."
                    )
                    halted = True
                    break

            if halted:
                break

        if not halted:
            if batch.failed_outputs == 0:
                batch.status = "completed"
            elif batch.completed_outputs > 0:
                batch.status = "partial_halted"
            else:
                batch.status = "failed"

        self.repo.update_batch(user.id, batch)
        self.repo.record_audit(
            user_id=user.id,
            project_id=project_id,
            event_type="generation_batch_finished",
            entity_type="generation_batch",
            entity_id=batch.batch_id,
            payload={
                "status": batch.status,
                "completed_outputs": batch.completed_outputs,
                "failed_outputs": batch.failed_outputs,
                "halted_reason": batch.halted_reason,
            },
        )
        return batch, all_jobs, all_assets, all_reviews

    # ── Optional Multimodal Vision QC (Phase 2 — Explicitly Gated) ────────
    def request_vision_qc_quote(self, *, user: UserProfile, asset_id: str) -> VisionQCQuote:
        asset = self.repo.get_asset(user.id, asset_id)
        if not asset:
            raise KeyError("Generated asset not found.")
        plan = self.repo.get_plan(user.id, asset.plan_id)
        if not plan:
            raise KeyError("Source production plan not found.")
        refs = self._load_references(user.id, plan)
        frames, includes_src, est_cost, disclosure = self.vision_qc.estimate_review(asset=asset, references=refs)
        key_slot = self.providers.credential_provider_key(DEFAULT_VISION_QC_PROVIDER)
        cred_row = self.repo.get_credential_row(user.id, key_slot)
        has_cred = bool(cred_row and cred_row["status"] == "active" and cred_row["encrypted_key"])

        quote = self.policy_gate.create_vision_qc_quote(
            user=user,
            asset_id=asset.id,
            provider_id=DEFAULT_VISION_QC_PROVIDER,
            model_id=self.vision_qc.model_id,
            frames_to_inspect=frames,
            includes_source_comparison=includes_src,
            estimated_cost_usd=est_cost,
            pricing_disclosure=disclosure,
            has_active_credential=has_cred,
        )
        self.repo.save_vision_quote(user.id, quote)
        self.repo.record_audit(
            user_id=user.id,
            project_id=asset.project_id,
            event_type="vision_qc_quote_created",
            entity_type="vision_qc_quote",
            entity_id=quote.quote_id,
            payload={
                "asset_id": asset.id,
                "model_id": quote.model_id,
                "estimated_cost_usd": quote.estimated_cost_usd,
                "spend_guard_allows": quote.spend_guard_allows,
                "credential_ready": quote.credential_ready,
            },
        )
        return quote

    def run_approved_vision_qc(
        self,
        *,
        user: UserProfile,
        asset_id: str,
        quote_id: str,
        confirmation_token: str,
        explicit_user_confirmed: bool,
    ) -> QualityReviewRecord:
        asset_row = self.repo.get_asset_row(user.id, asset_id)
        if not asset_row:
            raise KeyError("Generated asset not found.")
        asset = self.repo._row_to_asset(asset_row)
        plan = self.repo.get_plan(user.id, asset.plan_id)
        if not plan:
            raise KeyError("Source production plan not found.")

        qrow = self.repo.get_vision_quote_row(user.id, quote_id)
        if not qrow:
            raise ProviderAdapterError("Vision QC quote not found.", category=ErrorCategory.APPROVAL_REQUIRED)
        quote = VisionQCQuote.model_validate_json(qrow["quote_json"])
        if quote.asset_id != asset.id:
            raise ProviderAdapterError("Vision QC quote does not match target asset.", category=ErrorCategory.APPROVAL_REQUIRED)

        api_key = self._decrypt_api_key(user.id, DEFAULT_VISION_QC_PROVIDER)
        fresh_user = self.repo.get_user_profile(user.id) or user
        self.policy_gate.verify_vision_qc_before_submit(
            user=fresh_user,
            quote=quote,
            submitted_token=confirmation_token,
            explicit_user_confirmed=explicit_user_confirmed,
            quote_consumed=bool(qrow["consumed"]),
            has_active_credential=bool(api_key),
        )
        if not self.repo.consume_vision_quote_atomically(user.id, quote_id):
            raise ProviderAdapterError(
                "Vision QC quote has already been consumed. Request a fresh quote.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )

        refs = self._load_references(user.id, plan)
        file_path = self.store.resolve(asset_row["storage_relpath"])
        assert api_key is not None
        try:
            review, reported_cost = self.vision_qc.run_multimodal_review(
                asset=asset,
                plan=plan,
                file_path=file_path,
                references=refs,
                api_key=api_key,
            )
        except ProviderAdapterError as exc:
            if exc.provider_may_have_accepted:
                # Conservatively reserve estimated Vision QC cost if timeout left acceptance uncertain
                self.repo.record_spend(
                    user_id=user.id,
                    job_id=f"vqc_unknown_{quote_id}",
                    provider_id=quote.provider_id,
                    model_id=quote.model_id,
                    estimated_cost_usd=quote.estimated_cost_usd,
                    reported_cost_usd=quote.estimated_cost_usd,
                )
            raise
        except (ValueError, RuntimeError) as exc:
            raise ProviderAdapterError(
                f"Multimodal Vision QC failed processing response: {redact_secrets(str(exc))}",
                category=ErrorCategory.PROVIDER_REJECTED,
            ) from exc

        self.repo.save_quality_review(user.id, review)
        self.repo.record_spend(
            user_id=user.id,
            job_id=review.id,
            provider_id=quote.provider_id,
            model_id=quote.model_id,
            estimated_cost_usd=quote.estimated_cost_usd,
            reported_cost_usd=reported_cost,
        )
        self.repo.record_audit(
            user_id=user.id,
            project_id=asset.project_id,
            event_type="vision_qc_completed",
            entity_type="quality_review",
            entity_id=review.id,
            payload={
                "asset_id": asset.id,
                "model_id": quote.model_id,
                "advisory_verdict": review.advisory_verdict.value,
                "weighted_score": review.weighted_score,
                "recorded_cost_usd": reported_cost,
            },
        )
        return review

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
        variation_index: int = 1,
        variation_total: int = 1,
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
                    variation_index=variation_index,
                    variation_total=variation_total,
                )
            else:
                adapter = self.providers.get_video_adapter(provider_id)
                prev_pjid = plan.video_plan.source_provider_job_id if plan.video_plan else None
                result = adapter.submit(
                    plan=plan,
                    model_id=model_id,
                    references=refs,
                    api_key=api_key,
                    idempotency_key=job.idempotency_key,
                    previous_provider_job_id=prev_pjid,
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

            return self._finalize_success(
                user_id,
                job,
                plan,
                result,
                parent_asset_id,
                variation_index=variation_index,
                variation_total=variation_total,
            )

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
            # Conservatively reserve estimated spend when a billable request enters UNKNOWN so cap cannot be overspent
            if next_status == JobStatus.UNKNOWN and job.is_billable:
                reserved = float(job.estimated_cost_usd) if job.estimated_cost_usd is not None else 0.01
                self.repo.record_spend(
                    user_id=user_id,
                    job_id=job.id,
                    provider_id=job.provider_id,
                    model_id=job.model_id,
                    estimated_cost_usd=reserved,
                    reported_cost_usd=reserved,
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
        variation_index: int = 1,
        variation_total: int = 1,
    ) -> tuple[GenerationJobRecord, GeneratedAssetRecord, QualityReviewRecord]:
        if not result.media_bytes or not result.mime_type:
            raise ProviderAdapterError("Provider succeeded without returning media bytes.", category=ErrorCategory.PROVIDER_REJECTED)

        stored = self.store.store_generated_media(result.media_bytes, result.mime_type)
        version_num = self.repo.next_version_number(plan.project_id, plan.media_type)
        ext = ".mp4" if plan.media_type == MediaType.VIDEO else ".png"
        prefix = "fixture_" if job.is_local_test_fixture else ""
        var_suffix = f"_var{variation_index}of{variation_total}" if variation_total > 1 else ""
        filename = f"{prefix}{plan.media_type.value}_v{version_num:02d}{var_suffix}_{stored.sha256[:8]}{ext}"

        metadata = {
            "plan_version": plan.version,
            "task_mode": plan.task_mode.value,
            "summary": plan.summary,
            "provider_id": job.provider_id,
            "model_id": job.model_id,
            "is_local_test_fixture": job.is_local_test_fixture,
            "activated_protocol_codes": [p.protocol_code for p in plan.activated_protocols],
            "provider_job_id": result.provider_job_id,
            "variation_index": variation_index,
            "variation_total": variation_total,
            "extended_from_asset_id": plan.video_plan.extended_from_asset_id if plan.video_plan else None,
            "extension_duration_s": plan.video_plan.extension_duration_s if plan.video_plan else None,
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
                "variation_index": variation_index,
                "variation_total": variation_total,
                "sha256": stored.sha256,
                "advisory_verdict": review.advisory_verdict.value,
                "recorded_cost_usd": recorded_cost,
            },
        )
        return job, asset, review
