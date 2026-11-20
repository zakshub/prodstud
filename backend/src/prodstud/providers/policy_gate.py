"""Pre-execution Policy Evaluation Gate, Spend Guard ($0.00 default cap), and Explicit Approval Verification."""

from __future__ import annotations

import hashlib
import json
from datetime import datetime, timedelta, timezone
from typing import Any
from uuid import uuid4

from prodstud.domain.enums import CapabilitySupport, ErrorCategory, MediaType
from prodstud.domain.models import (
    ApprovalQuote,
    BatchApprovalQuote,
    BatchQuoteItem,
    ProductionPlanRecord,
    ProviderModelCapability,
    UserProfile,
    VisionQCQuote,
)
from prodstud.providers.base import ProviderAdapterError
from prodstud.security import ApprovalSigner
from prodstud.storage.database import utcnow_iso


def _plan_settings_summary(plan: ProductionPlanRecord, variation_count: int = 1) -> dict[str, Any]:
    if plan.media_type == MediaType.IMAGE and plan.image_plan:
        return {
            "media_type": "image",
            "aspect_ratio": plan.image_plan.aspect_ratio,
            "resolution": plan.image_plan.resolution,
            "focal_length_mm": plan.image_plan.focal_length_mm,
            "reality_class": plan.image_plan.reality_class,
            "hard_locks_count": len(plan.image_plan.hard_locks),
            "variation_count": variation_count,
            "plan_version": plan.version,
        }
    if plan.media_type == MediaType.VIDEO and plan.video_plan:
        return {
            "media_type": "video",
            "aspect_ratio": plan.video_plan.aspect_ratio,
            "resolution": plan.video_plan.resolution,
            "total_duration_s": plan.video_plan.total_duration_s,
            "fps": plan.video_plan.fps,
            "shot_count": len(plan.video_plan.shots),
            "extended_from_asset_id": plan.video_plan.extended_from_asset_id,
            "extension_duration_s": plan.video_plan.extension_duration_s,
            "plan_version": plan.version,
        }
    return {"media_type": plan.media_type.value, "plan_version": plan.version}


def estimate_cost_usd(plan: ProductionPlanRecord, capability: ProviderModelCapability) -> float | None:
    """Return reliable verified unit cost estimate where published; None when dynamic/unverified (never fabricate)."""
    if not capability.is_billable:
        return 0.0
    if capability.model_id == "gemini-nano-banana-2.1" and plan.image_plan:
        tier_prices = {"1K": 0.0336, "2K": 0.0504, "4K": 0.1130}
        return tier_prices.get(plan.image_plan.resolution, 0.0336)
    return capability.estimated_unit_cost_usd


class PolicyEvaluationGate:
    """Enforces explicit user approval, capability support, credential availability, and hard spend caps."""

    def __init__(self, signer: ApprovalSigner):
        self.signer = signer

    def create_quote(
        self,
        *,
        user: UserProfile,
        plan: ProductionPlanRecord,
        capability: ProviderModelCapability,
        has_active_credential: bool,
        validation_errors: list[str],
        variation_count: int = 1,
    ) -> ApprovalQuote:
        count = max(1, min(4, int(variation_count)))
        all_val_errors = list(validation_errors)
        if plan.media_type == MediaType.VIDEO and count > 1:
            all_val_errors.append("Multi-output variations (>1) are supported for Image plans only; use Batch Generation for multiple video plans.")
            count = 1

        quote_id = f"qte_{uuid4().hex[:14]}"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        settings = _plan_settings_summary(plan, variation_count=count)
        unit_cost = estimate_cost_usd(plan, capability)
        total_cost = round(unit_cost * count, 6) if unit_cost is not None else None
        prev_pjid = plan.video_plan.source_provider_job_id if (plan.media_type == MediaType.VIDEO and plan.video_plan) else None

        # Credential check
        if capability.requires_credential and not has_active_credential:
            cred_ok = False
            cred_reason = (
                f"Active server-side API credential for '{capability.provider_id}' is required. "
                "Add your key in Settings -> Provider Credentials."
            )
        else:
            cred_ok = True
            cred_reason = (
                "No external credential required (non-billable local test fixture)."
                if capability.is_local_test_fixture
                else f"Active encrypted server-side credential found for '{capability.provider_id}'."
            )

        # Spend guard check ($0.00 default hard lock)
        if not capability.is_billable:
            spend_ok = True
            spend_reason = f"Non-billable local test verification render ($0.00 for {count} output(s))."
        else:
            effective_cost = total_cost if total_cost is not None else round(0.01 * count, 6)
            if user.daily_spend_cap_usd <= 0.0:
                spend_ok = False
                spend_reason = (
                    "Spend Guard active: Daily spend cap is $0.00. Increase your daily spend cap in Settings "
                    "to authorize live paid provider requests."
                )
            elif (user.spent_today_usd + effective_cost) > user.daily_spend_cap_usd:
                spend_ok = False
                spend_reason = (
                    f"Spend Guard blocked: Today's spend (${user.spent_today_usd:.4f}) + estimated {count} output(s) "
                    f"(${effective_cost:.4f}) exceeds daily cap (${user.daily_spend_cap_usd:.2f})."
                )
            else:
                spend_ok = True
                spend_reason = (
                    f"Within daily spend cap (${user.spent_today_usd:.4f} + ${effective_cost:.4f} / ${user.daily_spend_cap_usd:.2f} today)."
                )

        feasibility_warnings = list(plan.feasibility_warnings) + all_val_errors
        if capability.support_status in {CapabilitySupport.UNSUPPORTED, CapabilitySupport.PROVIDER_CONDITIONAL}:
            feasibility_warnings.append(
                f"Model '{capability.model_id}' status is '{capability.support_status.value}' and cannot execute directly."
            )

        sign_payload = {
            "quote_id": quote_id,
            "user_id": user.id,
            "plan_id": plan.id,
            "provider_id": capability.provider_id,
            "model_id": capability.model_id,
            "variation_count": count,
            "previous_provider_job_id": prev_pjid,
            "settings_hash": hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest(),
            "estimated_cost_usd": total_cost,
            "expires_at": expires,
        }
        token = self.signer.sign_quote(sign_payload)

        return ApprovalQuote(
            quote_id=quote_id,
            plan_id=plan.id,
            provider_id=capability.provider_id,
            model_id=capability.model_id,
            media_type=plan.media_type,
            variation_count=count,
            is_billable=capability.is_billable,
            is_local_test_fixture=capability.is_local_test_fixture,
            unit_estimated_cost_usd=unit_cost,
            estimated_cost_usd=total_cost,
            pricing_disclosure=capability.pricing_note,
            user_daily_spend_cap_usd=user.daily_spend_cap_usd,
            user_spent_today_usd=user.spent_today_usd,
            spend_guard_allows=spend_ok,
            spend_guard_reason=spend_reason,
            credential_ready=cred_ok,
            credential_reason=cred_reason,
            settings_summary=settings,
            feasibility_warnings=feasibility_warnings,
            previous_provider_job_id=prev_pjid,
            confirmation_token=token,
            expires_at=expires,
        )

    def verify_before_submit(
        self,
        *,
        user: UserProfile,
        plan: ProductionPlanRecord,
        capability: ProviderModelCapability,
        quote: ApprovalQuote,
        submitted_token: str,
        explicit_user_confirmed: bool,
        quote_consumed: bool,
        has_active_credential: bool,
        validation_errors: list[str],
    ) -> None:
        """Fail-closed policy & budget verification before any provider invocation."""
        if not explicit_user_confirmed:
            raise ProviderAdapterError(
                "Explicit user confirmation is mandatory before submitting any generation job.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if quote_consumed:
            raise ProviderAdapterError(
                "Approval quote has already been consumed. Request a fresh approval quote to prevent duplicate submissions.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if quote.expires_at <= utcnow_iso():
            raise ProviderAdapterError(
                "Approval quote has expired. Request a fresh quote before generating.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if quote.plan_id != plan.id or quote.provider_id != capability.provider_id or quote.model_id != capability.model_id:
            raise ProviderAdapterError(
                "Approval quote does not match target plan, provider, or model.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )

        settings = _plan_settings_summary(plan, variation_count=quote.variation_count)
        prev_pjid = plan.video_plan.source_provider_job_id if (plan.media_type == MediaType.VIDEO and plan.video_plan) else None
        sign_payload = {
            "quote_id": quote.quote_id,
            "user_id": user.id,
            "plan_id": plan.id,
            "provider_id": capability.provider_id,
            "model_id": capability.model_id,
            "variation_count": quote.variation_count,
            "previous_provider_job_id": prev_pjid,
            "settings_hash": hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest(),
            "estimated_cost_usd": quote.estimated_cost_usd,
            "expires_at": quote.expires_at,
        }
        if not self.signer.verify_quote(sign_payload, submitted_token):
            raise ProviderAdapterError(
                "Invalid or tampered confirmation token (plan settings may have changed since quote was generated).",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )

        if capability.support_status in {CapabilitySupport.UNSUPPORTED, CapabilitySupport.PROVIDER_CONDITIONAL}:
            raise ProviderAdapterError(
                f"Model '{capability.model_id}' is marked '{capability.support_status.value}' and cannot execute in this configuration.",
                category=ErrorCategory.VALIDATION,
            )

        if validation_errors:
            raise ProviderAdapterError(
                "Request failed capability validation: " + "; ".join(validation_errors),
                category=ErrorCategory.VALIDATION,
            )

        if any(c.severity == "blocking" for c in plan.contradictions):
            raise ProviderAdapterError(
                "Plan has unresolved blocking contradictions that must be fixed before generation.",
                category=ErrorCategory.VALIDATION,
            )

        if capability.requires_credential and not has_active_credential:
            raise ProviderAdapterError(
                f"No active server-side credential configured for provider '{capability.provider_id}'.",
                category=ErrorCategory.PROVIDER_AUTH,
            )

        if capability.is_billable:
            effective_cost = quote.estimated_cost_usd if quote.estimated_cost_usd is not None else round(0.01 * quote.variation_count, 6)
            if user.daily_spend_cap_usd <= 0.0:
                raise ProviderAdapterError(
                    "Spend Guard blocked billable generation: daily spend cap is $0.00.",
                    category=ErrorCategory.SPEND_GUARD,
                )
            if (user.spent_today_usd + effective_cost) > user.daily_spend_cap_usd:
                raise ProviderAdapterError(
                    f"Spend Guard blocked billable generation: estimated total (${effective_cost:.4f}) exceeds daily cap (${user.daily_spend_cap_usd:.2f}).",
                    category=ErrorCategory.SPEND_GUARD,
                )

    # ── Batch Combined-Cost Quote & Verification (Phase 2) ────────────────
    def create_batch_quote(
        self,
        *,
        user: UserProfile,
        project_id: str,
        evaluated_items: list[tuple[ProductionPlanRecord, ProviderModelCapability, int, bool, list[str]]],
    ) -> BatchApprovalQuote:
        """Create a single signed approval quote covering combined multi-plan / multi-variation cost."""
        batch_quote_id = f"bqte_{uuid4().hex[:14]}"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        items: list[BatchQuoteItem] = []
        feasibility_warnings: list[str] = []
        missing_creds: list[str] = []
        total_outputs = 0
        has_billable = False
        has_dynamic = False
        known_cost_sum = 0.0
        effective_floor_sum = 0.0

        for plan, cap, raw_count, has_cred, val_errors in evaluated_items:
            count = 1 if plan.media_type == MediaType.VIDEO else max(1, min(4, int(raw_count)))
            item_errors = list(val_errors)
            if cap.support_status in {CapabilitySupport.UNSUPPORTED, CapabilitySupport.PROVIDER_CONDITIONAL}:
                item_errors.append(f"Model '{cap.model_id}' status is '{cap.support_status.value}'.")
            if any(c.severity == "blocking" for c in plan.contradictions):
                item_errors.append("Plan has unresolved blocking contradictions.")
            if cap.requires_credential and not has_cred:
                missing_creds.append(cap.provider_id)

            unit_cost = estimate_cost_usd(plan, cap)
            subtotal = round(unit_cost * count, 6) if unit_cost is not None else None
            if cap.is_billable:
                has_billable = True
                if subtotal is None:
                    has_dynamic = True
                    effective_floor_sum += round(0.01 * count, 6)
                else:
                    known_cost_sum += subtotal
                    effective_floor_sum += subtotal

            total_outputs += count
            settings = _plan_settings_summary(plan, variation_count=count)
            items.append(
                BatchQuoteItem(
                    plan_id=plan.id,
                    plan_summary=plan.summary,
                    media_type=plan.media_type,
                    provider_id=cap.provider_id,
                    model_id=cap.model_id,
                    variation_count=count,
                    is_billable=cap.is_billable,
                    is_local_test_fixture=cap.is_local_test_fixture,
                    unit_estimated_cost_usd=unit_cost,
                    subtotal_estimated_cost_usd=subtotal,
                    pricing_disclosure=cap.pricing_note,
                    validation_errors=item_errors,
                    settings_summary=settings,
                )
            )
            for warn in list(plan.feasibility_warnings) + item_errors:
                feasibility_warnings.append(f"[{plan.id}] {warn}")

        total_estimated = None if (has_billable and has_dynamic) else round(known_cost_sum, 6)

        if missing_creds:
            cred_ok = False
            cred_reason = f"Missing active server-side credential(s) for: {', '.join(sorted(set(missing_creds)))}."
        else:
            cred_ok = True
            cred_reason = (
                "No external credential required (non-billable local test fixtures)."
                if not has_billable
                else "Active encrypted server-side credential(s) verified for all billable batch items."
            )

        if not has_billable:
            spend_ok = True
            spend_reason = f"Non-billable local test batch ($0.00 across {total_outputs} output(s))."
        else:
            if user.daily_spend_cap_usd <= 0.0:
                spend_ok = False
                spend_reason = (
                    "Spend Guard active: Daily spend cap is $0.00. Increase your daily cap in Settings "
                    "before approving billable batch execution."
                )
            elif (user.spent_today_usd + effective_floor_sum) > user.daily_spend_cap_usd:
                spend_ok = False
                spend_reason = (
                    f"Spend Guard blocked batch: today's spend (${user.spent_today_usd:.4f}) + combined batch estimate "
                    f"(${effective_floor_sum:.4f}) exceeds daily cap (${user.daily_spend_cap_usd:.2f})."
                )
            else:
                spend_ok = True
                spend_reason = (
                    f"Combined batch within daily spend cap (${user.spent_today_usd:.4f} + ${effective_floor_sum:.4f} / ${user.daily_spend_cap_usd:.2f})."
                )

        items_sig = [
            {
                "plan_id": it.plan_id,
                "provider_id": it.provider_id,
                "model_id": it.model_id,
                "variation_count": it.variation_count,
                "settings": it.settings_summary,
                "subtotal": it.subtotal_estimated_cost_usd,
            }
            for it in items
        ]
        sign_payload = {
            "batch_quote_id": batch_quote_id,
            "user_id": user.id,
            "project_id": project_id,
            "items_hash": hashlib.sha256(json.dumps(items_sig, sort_keys=True).encode("utf-8")).hexdigest(),
            "total_estimated_cost_usd": total_estimated,
            "expires_at": expires,
        }
        token = self.signer.sign_quote(sign_payload)

        return BatchApprovalQuote(
            batch_quote_id=batch_quote_id,
            project_id=project_id,
            items=items,
            total_requested_outputs=total_outputs,
            has_billable_items=has_billable,
            has_dynamic_pricing_items=has_dynamic,
            total_estimated_cost_usd=total_estimated,
            user_daily_spend_cap_usd=user.daily_spend_cap_usd,
            user_spent_today_usd=user.spent_today_usd,
            spend_guard_allows=spend_ok,
            spend_guard_reason=spend_reason,
            credential_ready=cred_ok,
            credential_reason=cred_reason,
            feasibility_warnings=feasibility_warnings,
            confirmation_token=token,
            expires_at=expires,
        )

    def verify_batch_before_submit(
        self,
        *,
        user: UserProfile,
        quote: BatchApprovalQuote,
        submitted_token: str,
        explicit_user_confirmed: bool,
        quote_consumed: bool,
        evaluated_items: list[tuple[ProductionPlanRecord, ProviderModelCapability, int, bool, list[str]]],
    ) -> None:
        if not explicit_user_confirmed:
            raise ProviderAdapterError(
                "Explicit user confirmation is mandatory before executing a generation batch.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if quote_consumed:
            raise ProviderAdapterError(
                "Batch approval quote has already been consumed. Request a fresh batch quote.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if quote.expires_at <= utcnow_iso():
            raise ProviderAdapterError(
                "Batch approval quote has expired. Request a fresh batch quote.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )

        items_sig = []
        effective_floor = 0.0
        for (plan, cap, count, has_cred, val_errors), qitem in zip(evaluated_items, quote.items, strict=True):
            if plan.id != qitem.plan_id or cap.provider_id != qitem.provider_id or cap.model_id != qitem.model_id:
                raise ProviderAdapterError(
                    "Batch plan list does not match quoted batch items.",
                    category=ErrorCategory.APPROVAL_REQUIRED,
                )
            if cap.support_status in {CapabilitySupport.UNSUPPORTED, CapabilitySupport.PROVIDER_CONDITIONAL}:
                raise ProviderAdapterError(
                    f"Batch item model '{cap.model_id}' is '{cap.support_status.value}' and cannot execute.",
                    category=ErrorCategory.VALIDATION,
                )
            if val_errors:
                raise ProviderAdapterError(
                    f"Batch item '{plan.id}' failed validation: " + "; ".join(val_errors),
                    category=ErrorCategory.VALIDATION,
                )
            if any(c.severity == "blocking" for c in plan.contradictions):
                raise ProviderAdapterError(
                    f"Batch item '{plan.id}' has unresolved blocking contradictions.",
                    category=ErrorCategory.VALIDATION,
                )
            if cap.requires_credential and not has_cred:
                raise ProviderAdapterError(
                    f"Missing active server-side credential for provider '{cap.provider_id}'.",
                    category=ErrorCategory.PROVIDER_AUTH,
                )
            settings = _plan_settings_summary(plan, variation_count=count)
            items_sig.append(
                {
                    "plan_id": plan.id,
                    "provider_id": cap.provider_id,
                    "model_id": cap.model_id,
                    "variation_count": count,
                    "settings": settings,
                    "subtotal": qitem.subtotal_estimated_cost_usd,
                }
            )
            if cap.is_billable:
                effective_floor += qitem.subtotal_estimated_cost_usd if qitem.subtotal_estimated_cost_usd is not None else round(0.01 * count, 6)

        sign_payload = {
            "batch_quote_id": quote.batch_quote_id,
            "user_id": user.id,
            "project_id": quote.project_id,
            "items_hash": hashlib.sha256(json.dumps(items_sig, sort_keys=True).encode("utf-8")).hexdigest(),
            "total_estimated_cost_usd": quote.total_estimated_cost_usd,
            "expires_at": quote.expires_at,
        }
        if not self.signer.verify_quote(sign_payload, submitted_token):
            raise ProviderAdapterError(
                "Invalid or tampered batch confirmation token (plan settings may have changed since quote was generated).",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )

        if quote.has_billable_items:
            if user.daily_spend_cap_usd <= 0.0:
                raise ProviderAdapterError(
                    "Spend Guard blocked billable batch: daily spend cap is $0.00.",
                    category=ErrorCategory.SPEND_GUARD,
                )
            if (user.spent_today_usd + effective_floor) > user.daily_spend_cap_usd:
                raise ProviderAdapterError(
                    f"Spend Guard blocked billable batch: combined total (${effective_floor:.4f}) exceeds daily cap (${user.daily_spend_cap_usd:.2f}).",
                    category=ErrorCategory.SPEND_GUARD,
                )

    # ── Optional Multimodal Vision QC Quote & Verification (Phase 2) ──────
    def create_vision_qc_quote(
        self,
        *,
        user: UserProfile,
        asset_id: str,
        provider_id: str,
        model_id: str,
        frames_to_inspect: int,
        includes_source_comparison: bool,
        estimated_cost_usd: float,
        pricing_disclosure: str,
        has_active_credential: bool,
    ) -> VisionQCQuote:
        quote_id = f"vqte_{uuid4().hex[:14]}"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).replace(microsecond=0).isoformat().replace("+00:00", "Z")

        if not has_active_credential:
            cred_ok = False
            cred_reason = (
                "Active server-side Google Gemini API key is required for optional multimodal Vision QC. "
                "Add your key in Settings -> Provider Credentials."
            )
        else:
            cred_ok = True
            cred_reason = "Active encrypted server-side Google API key found."

        if user.daily_spend_cap_usd <= 0.0:
            spend_ok = False
            spend_reason = (
                "Spend Guard active: Daily spend cap is $0.00. Increase your daily cap in Settings "
                "to authorize billable multimodal Vision QC."
            )
        elif (user.spent_today_usd + estimated_cost_usd) > user.daily_spend_cap_usd:
            spend_ok = False
            spend_reason = (
                f"Spend Guard blocked Vision QC: today's spend (${user.spent_today_usd:.4f}) + estimated review "
                f"(${estimated_cost_usd:.4f}) exceeds daily cap (${user.daily_spend_cap_usd:.2f})."
            )
        else:
            spend_ok = True
            spend_reason = (
                f"Within daily spend cap (${user.spent_today_usd:.4f} + ${estimated_cost_usd:.4f} / ${user.daily_spend_cap_usd:.2f})."
            )

        sign_payload = {
            "quote_id": quote_id,
            "user_id": user.id,
            "asset_id": asset_id,
            "provider_id": provider_id,
            "model_id": model_id,
            "estimated_cost_usd": estimated_cost_usd,
            "expires_at": expires,
        }
        token = self.signer.sign_quote(sign_payload)
        return VisionQCQuote(
            quote_id=quote_id,
            asset_id=asset_id,
            provider_id=provider_id,
            model_id=model_id,
            is_billable=True,
            estimated_cost_usd=estimated_cost_usd,
            pricing_disclosure=pricing_disclosure,
            frames_to_inspect=frames_to_inspect,
            includes_source_comparison=includes_source_comparison,
            user_daily_spend_cap_usd=user.daily_spend_cap_usd,
            user_spent_today_usd=user.spent_today_usd,
            spend_guard_allows=spend_ok,
            spend_guard_reason=spend_reason,
            credential_ready=cred_ok,
            credential_reason=cred_reason,
            confirmation_token=token,
            expires_at=expires,
        )

    def verify_vision_qc_before_submit(
        self,
        *,
        user: UserProfile,
        quote: VisionQCQuote,
        submitted_token: str,
        explicit_user_confirmed: bool,
        quote_consumed: bool,
        has_active_credential: bool,
    ) -> None:
        if not explicit_user_confirmed:
            raise ProviderAdapterError(
                "Explicit user confirmation is required before running billable multimodal Vision QC.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if quote_consumed:
            raise ProviderAdapterError(
                "Vision QC quote has already been consumed. Request a fresh quote.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if quote.expires_at <= utcnow_iso():
            raise ProviderAdapterError(
                "Vision QC quote has expired. Request a fresh quote.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        sign_payload = {
            "quote_id": quote.quote_id,
            "user_id": user.id,
            "asset_id": quote.asset_id,
            "provider_id": quote.provider_id,
            "model_id": quote.model_id,
            "estimated_cost_usd": quote.estimated_cost_usd,
            "expires_at": quote.expires_at,
        }
        if not self.signer.verify_quote(sign_payload, submitted_token):
            raise ProviderAdapterError(
                "Invalid or tampered Vision QC confirmation token.",
                category=ErrorCategory.APPROVAL_REQUIRED,
            )
        if not has_active_credential:
            raise ProviderAdapterError(
                "No active server-side Google Gemini API key configured for multimodal Vision QC.",
                category=ErrorCategory.PROVIDER_AUTH,
            )
        if user.daily_spend_cap_usd <= 0.0:
            raise ProviderAdapterError(
                "Spend Guard blocked billable multimodal Vision QC: daily spend cap is $0.00.",
                category=ErrorCategory.SPEND_GUARD,
            )
        if (user.spent_today_usd + quote.estimated_cost_usd) > user.daily_spend_cap_usd:
            raise ProviderAdapterError(
                f"Spend Guard blocked billable Vision QC: estimated cost exceeds daily cap (${user.daily_spend_cap_usd:.2f}).",
                category=ErrorCategory.SPEND_GUARD,
            )

