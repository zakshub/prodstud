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
    ProductionPlanRecord,
    ProviderModelCapability,
    UserProfile,
)
from prodstud.providers.base import ProviderAdapterError
from prodstud.security import ApprovalSigner
from prodstud.storage.database import utcnow_iso


def _plan_settings_summary(plan: ProductionPlanRecord) -> dict[str, Any]:
    if plan.media_type == MediaType.IMAGE and plan.image_plan:
        return {
            "media_type": "image",
            "aspect_ratio": plan.image_plan.aspect_ratio,
            "resolution": plan.image_plan.resolution,
            "focal_length_mm": plan.image_plan.focal_length_mm,
            "reality_class": plan.image_plan.reality_class,
            "hard_locks_count": len(plan.image_plan.hard_locks),
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
            "plan_version": plan.version,
        }
    return {"media_type": plan.media_type.value, "plan_version": plan.version}


def estimate_cost_usd(plan: ProductionPlanRecord, capability: ProviderModelCapability) -> float | None:
    """Return reliable verified cost estimate where published; None when dynamic/unverified (never fabricate)."""
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
    ) -> ApprovalQuote:
        quote_id = f"qte_{uuid4().hex[:14]}"
        expires = (datetime.now(timezone.utc) + timedelta(minutes=15)).replace(microsecond=0).isoformat().replace("+00:00", "Z")
        settings = _plan_settings_summary(plan)
        est_cost = estimate_cost_usd(plan, capability)

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
            spend_reason = "Non-billable local test verification render ($0.00)."
        else:
            effective_cost = est_cost if est_cost is not None else 0.01  # Conservative floor when dynamic token billing applies
            if user.daily_spend_cap_usd <= 0.0:
                spend_ok = False
                spend_reason = (
                    "Spend Guard active: Daily spend cap is $0.00. Increase your daily spend cap in Settings "
                    "to authorize live paid provider requests."
                )
            elif (user.spent_today_usd + effective_cost) > user.daily_spend_cap_usd:
                spend_ok = False
                spend_reason = (
                    f"Spend Guard blocked: Today's spend (${user.spent_today_usd:.4f}) + estimated request "
                    f"(${effective_cost:.4f}) exceeds daily cap (${user.daily_spend_cap_usd:.2f})."
                )
            else:
                spend_ok = True
                spend_reason = (
                    f"Within daily spend cap (${user.spent_today_usd:.4f} / ${user.daily_spend_cap_usd:.2f} used today)."
                )

        feasibility_warnings = list(plan.feasibility_warnings) + list(validation_errors)
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
            "settings_hash": hashlib.sha256(json.dumps(settings, sort_keys=True).encode("utf-8")).hexdigest(),
            "estimated_cost_usd": est_cost,
            "expires_at": expires,
        }
        token = self.signer.sign_quote(sign_payload)

        return ApprovalQuote(
            quote_id=quote_id,
            plan_id=plan.id,
            provider_id=capability.provider_id,
            model_id=capability.model_id,
            media_type=plan.media_type,
            is_billable=capability.is_billable,
            is_local_test_fixture=capability.is_local_test_fixture,
            estimated_cost_usd=est_cost,
            pricing_disclosure=capability.pricing_note,
            user_daily_spend_cap_usd=user.daily_spend_cap_usd,
            user_spent_today_usd=user.spent_today_usd,
            spend_guard_allows=spend_ok,
            spend_guard_reason=spend_reason,
            credential_ready=cred_ok,
            credential_reason=cred_reason,
            settings_summary=settings,
            feasibility_warnings=feasibility_warnings,
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

        settings = _plan_settings_summary(plan)
        sign_payload = {
            "quote_id": quote.quote_id,
            "user_id": user.id,
            "plan_id": plan.id,
            "provider_id": capability.provider_id,
            "model_id": capability.model_id,
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
            effective_cost = quote.estimated_cost_usd if quote.estimated_cost_usd is not None else 0.01
            if user.daily_spend_cap_usd <= 0.0:
                raise ProviderAdapterError(
                    "Spend Guard blocked billable generation: daily spend cap is $0.00.",
                    category=ErrorCategory.SPEND_GUARD,
                )
            if (user.spent_today_usd + effective_cost) > user.daily_spend_cap_usd:
                raise ProviderAdapterError(
                    f"Spend Guard blocked billable generation: estimated total exceeds daily cap (${user.daily_spend_cap_usd:.2f}).",
                    category=ErrorCategory.SPEND_GUARD,
                )
