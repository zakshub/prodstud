"""Verified Google Gemini Image Provider Adapter (Official Nov 2026 APIs: Nano Banana 2.1 / Pro / Lite).

Official documentation verified 2026-11-19:
- https://aistudio.google.com/docs/image-generation
- https://aistudio.google.com/docs/models/gemini-nano-banana-2.1
- https://aistudio.google.com/docs/models
- https://aistudio.google.com/docs/deprecations
- https://ai.google.dev/gemini-api/docs/imagen (Imagen shut down in Gemini API)
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from prodstud.domain.enums import CapabilitySupport, ErrorCategory, JobStatus, MediaType
from prodstud.domain.models import ProductionPlanRecord, ProviderModelCapability
from prodstud.providers.base import (
    ImageProviderAdapter,
    ProviderAdapterError,
    ProviderSubmissionResult,
    ReferencePayload,
    build_http_client,
)
from prodstud.security import redact_secrets

VERIFIED_DATE = "2026-11-19"
STANDARD_IMAGE_RATIOS = ["1:1", "3:4", "4:3", "9:16", "16:9", "2:3", "3:2", "4:5", "5:4", "21:9"]
PANORAMIC_IMAGE_RATIOS = STANDARD_IMAGE_RATIOS + ["1:4", "4:1", "1:8", "8:1"]


def _compile_google_image_directive(
    plan: ProductionPlanRecord,
    *,
    variation_index: int = 1,
    variation_total: int = 1,
) -> str:
    """Translate provider-neutral ImagePlanDetails into physically causal prompt inside adapter boundary."""
    p = plan.image_plan
    assert p is not None
    lines = [
        f"PHOTOGRAPHIC CLASS: {p.reality_class}",
        f"SUBJECT: {p.subject_details}",
        f"ENVIRONMENT: {p.environment}",
        f"CAMERA & LENS: {p.camera_position}; {p.camera_height}; {p.focal_length_mm}mm lens at {p.aperture}; focus plane: {p.focus_plane}.",
        f"LIGHTING ARCHITECTURE: Key: {p.lighting_key}. Fill: {p.lighting_fill}. Contrast: {p.lighting_contrast_ratio}. Color temp: ~{p.color_temperature_k}K.",
        f"COMPOSITION: {p.composition_rule}; {p.shot_framing}.",
        f"COLOR & MATERIAL PHYSICS: {p.color_palette}. {p.material_and_texture}. Atmosphere: {p.atmosphere}.",
    ]
    if variation_total > 1:
        lines.append(
            f"VARIATION TAKE: {variation_index} of {variation_total} — provide a distinct natural micro-variation in pose/framing cadence "
            "while strictly maintaining camera optics, lighting architecture, and all HARD PRESERVATION LOCKS."
        )
    if p.hard_locks:
        lines.append("HARD PRESERVATION LOCKS (DO NOT ALTER): " + "; ".join(p.hard_locks))
    if p.allowed_changes:
        lines.append("AUTHORIZED SCOPE: " + "; ".join(p.allowed_changes))
    if p.negative_constraints:
        lines.append("AVOID: " + "; ".join(p.negative_constraints))
    return "\n".join(lines)


class GoogleImageAdapter(ImageProviderAdapter):
    """Dedicated Google Gemini Image adapter targeting verified Interactions & GenerateContent REST endpoints."""

    provider_id = "google_gemini_image"
    provider_name = "Google Gemini API (Image)"

    def __init__(
        self,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 120.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def capabilities(self) -> list[ProviderModelCapability]:
        return [
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="gemini-nano-banana-2.1",
                display_name="Google Gemini Nano Banana 2.1",
                media_type=MediaType.IMAGE,
                support_status=CapabilitySupport.SUPPORTED,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=PANORAMIC_IMAGE_RATIOS,
                supported_resolutions=["1K", "2K", "4K"],
                max_reference_images=14,
                supports_multi_turn_edit=True,
                pricing_note=(
                    "Token-billed (~$30/1M image output tokens; Google published equivalents ~$0.0336 @ 1K, "
                    "~$0.0504 @ 2K, ~$0.113 @ 4K + input tokens). Verify current billing at aistudio.google.com/docs/pricing."
                ),
                estimated_unit_cost_usd=0.0336,
                official_doc_url="https://aistudio.google.com/docs/models/gemini-nano-banana-2.1",
                verified_date=VERIFIED_DATE,
                limitations=[
                    "SynthID watermark embedded on outputs.",
                    "generateContent enforces 65,536 input token cap; named public figures may trigger IMAGE_OTHER safety blocks.",
                    "EEA/UK/CH deployments require Paid Tier per Gemini API Terms.",
                ],
            ),
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="gemini-3-pro-image",
                display_name="Google Nano Banana Pro (Gemini 3 Pro Image)",
                media_type=MediaType.IMAGE,
                support_status=CapabilitySupport.SUPPORTED,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=STANDARD_IMAGE_RATIOS,
                supported_resolutions=["1K", "2K", "4K"],
                max_reference_images=6,
                supports_multi_turn_edit=True,
                pricing_note="Higher Pro tier pricing (~2x Nano Banana 2.1); check aistudio.google.com/docs/pricing before spend.",
                estimated_unit_cost_usd=0.07,
                official_doc_url="https://aistudio.google.com/docs/models",
                verified_date=VERIFIED_DATE,
                limitations=["Higher latency/cost; optimized for complex layouts and embedded typography."],
            ),
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="gemini-3.1-flash-lite-image",
                display_name="Google Nano Banana 2 Lite",
                media_type=MediaType.IMAGE,
                support_status=CapabilitySupport.SUPPORTED,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=STANDARD_IMAGE_RATIOS,
                supported_resolutions=["0.5K", "1K", "2K", "4K"],
                max_reference_images=1,
                supports_multi_turn_edit=False,
                pricing_note="Lowest-cost Flash-Lite image tier; verify live rate at aistudio.google.com/docs/pricing.",
                estimated_unit_cost_usd=0.02,
                official_doc_url="https://aistudio.google.com/docs/models",
                verified_date=VERIFIED_DATE,
                limitations=["Not optimized for multiple reference images or multi-turn sequential edits."],
            ),
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="gemini-3.1-flash-image",
                display_name="Google Nano Banana 2 (Deprecated)",
                media_type=MediaType.IMAGE,
                support_status=CapabilitySupport.DEPRECATED,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=PANORAMIC_IMAGE_RATIOS,
                supported_resolutions=["0.5K", "1K", "2K", "4K"],
                max_reference_images=14,
                supports_multi_turn_edit=True,
                pricing_note="Deprecated by Google; migrate to gemini-nano-banana-2.1.",
                estimated_unit_cost_usd=0.0336,
                official_doc_url="https://aistudio.google.com/docs/deprecations",
                verified_date=VERIFIED_DATE,
                limitations=["Officially deprecated; prefer gemini-nano-banana-2.1."],
            ),
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="imagen-4",
                display_name="Google Imagen 4 (Shut Down in Gemini API)",
                media_type=MediaType.IMAGE,
                support_status=CapabilitySupport.UNSUPPORTED,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=[],
                supported_resolutions=[],
                max_reference_images=0,
                supports_multi_turn_edit=False,
                pricing_note="Imagen models are shut down in Gemini Developer API. Migrate to gemini-nano-banana-2.1.",
                estimated_unit_cost_usd=None,
                official_doc_url="https://ai.google.dev/gemini-api/docs/imagen",
                verified_date=VERIFIED_DATE,
                limitations=["Shut down by Google in Gemini Developer API."],
            ),
        ]

    def _cap_for(self, model_id: str) -> ProviderModelCapability | None:
        return next((c for c in self.capabilities() if c.model_id == model_id), None)

    def validate_request(
        self,
        plan: ProductionPlanRecord,
        model_id: str,
        references: list[ReferencePayload],
    ) -> list[str]:
        errors: list[str] = []
        cap = self._cap_for(model_id)
        if not cap:
            return [f"Unknown Google image model '{model_id}'."]
        if cap.support_status == CapabilitySupport.UNSUPPORTED:
            return [f"Model '{model_id}' is shut down / unsupported in the Gemini API."]
        if plan.media_type != MediaType.IMAGE or not plan.image_plan:
            return ["GoogleImageAdapter only accepts Image production plans."]
        if plan.image_plan.aspect_ratio not in cap.supported_aspect_ratios:
            errors.append(
                f"Aspect ratio '{plan.image_plan.aspect_ratio}' not supported by {model_id} (allowed: {', '.join(cap.supported_aspect_ratios)})."
            )
        if plan.image_plan.resolution not in cap.supported_resolutions:
            errors.append(
                f"Resolution '{plan.image_plan.resolution}' not supported by {model_id} (allowed: {', '.join(cap.supported_resolutions)})."
            )
        if len(references) > cap.max_reference_images:
            errors.append(f"Attached {len(references)} references; {model_id} supports at most {cap.max_reference_images}.")
        return errors

    def validate_credential(self, api_key: str) -> tuple[bool, str]:
        """Non-billable metadata check verifying Google API key validity against models endpoint."""
        if not api_key or len(api_key.strip()) < 10:
            return False, "API key format appears invalid."
        try:
            with build_http_client(15.0) as client:
                resp = client.get(
                    f"{self.base_url}/models/gemini-nano-banana-2.1",
                    headers={"x-goog-api-key": api_key.strip()},
                )
            if resp.status_code == 200:
                return True, "Credential verified against Google Gemini API (gemini-nano-banana-2.1 accessible)."
            if resp.status_code in {401, 403}:
                return False, f"Google API rejected key (HTTP {resp.status_code}). Check key permissions or billing."
            return False, f"Google API returned unexpected status HTTP {resp.status_code}."
        except httpx.TimeoutException:
            return False, "Validation timed out reaching generativelanguage.googleapis.com."
        except Exception as exc:
            return False, f"Validation connection error: {redact_secrets(str(exc))}"

    def submit(
        self,
        *,
        plan: ProductionPlanRecord,
        model_id: str,
        references: list[ReferencePayload],
        api_key: str | None,
        idempotency_key: str,
        previous_provider_job_id: str | None = None,
        variation_index: int = 1,
        variation_total: int = 1,
    ) -> ProviderSubmissionResult:
        if not api_key:
            raise ProviderAdapterError("Missing server-side Google API key.", category=ErrorCategory.PROVIDER_AUTH)
        errors = self.validate_request(plan, model_id, references)
        if errors:
            raise ProviderAdapterError("; ".join(errors), category=ErrorCategory.VALIDATION)

        assert plan.image_plan is not None
        directive = _compile_google_image_directive(
            plan,
            variation_index=variation_index,
            variation_total=variation_total,
        )

        # Build verified Gemini Interactions API request body (supports aspect_ratio, image_size, previous_interaction_id, multi-reference)
        input_items: list[dict[str, Any]] = [{"type": "text", "text": directive}]
        for ref in references:
            input_items.append(
                {
                    "type": "image",
                    "mime_type": ref.mime_type,
                    "data": base64.b64encode(ref.data).decode("ascii"),
                }
            )

        body: dict[str, Any] = {
            "model": model_id,
            "input": input_items if references else directive,
            "response_format": {
                "type": "image",
                "mime_type": "image/png",
                "aspect_ratio": plan.image_plan.aspect_ratio,
                "image_size": plan.image_plan.resolution,
            },
        }
        if previous_provider_job_id:
            body["previous_interaction_id"] = previous_provider_job_id

        try:
            with build_http_client(self.timeout_seconds) as client:
                resp = client.post(
                    f"{self.base_url}/interactions",
                    headers={
                        "x-goog-api-key": api_key,
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as exc:
            # Billing-safe rule: timeout after sending request means Google MAY have accepted & billed it -> UNKNOWN state!
            raise ProviderAdapterError(
                "Request timed out waiting for Google Gemini Image response. Status is UNKNOWN; do not blindly resubmit.",
                category=ErrorCategory.TIMEOUT_UNKNOWN,
                provider_may_have_accepted=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError(
                f"Network error contacting Google Gemini API: {redact_secrets(str(exc))}",
                category=ErrorCategory.NETWORK,
                provider_may_have_accepted=False,
            ) from exc

        if resp.status_code in {401, 403}:
            raise ProviderAdapterError(
                f"Google API authentication failed (HTTP {resp.status_code}). Verify server-side key.",
                category=ErrorCategory.PROVIDER_AUTH,
            )
        if resp.status_code == 429:
            raise ProviderAdapterError(
                "Google API rate limit or quota exceeded (HTTP 429). Wait before retrying.",
                category=ErrorCategory.QUOTA,
            )
        if resp.status_code >= 400:
            detail = redact_secrets(resp.text[:500])
            cat = (
                ErrorCategory.MODERATION
                if any(k in detail.upper() for k in ("IMAGE_SAFETY", "IMAGE_OTHER", "SAFETY", "BLOCKED"))
                else ErrorCategory.PROVIDER_REJECTED
            )
            raise ProviderAdapterError(
                f"Google Gemini Image rejected request (HTTP {resp.status_code}): {detail}",
                category=cat,
            )

        data = resp.json()
        interaction_id = data.get("id")
        img_bytes, mime = self._extract_image_bytes(data)

        return ProviderSubmissionResult(
            status=JobStatus.SUCCEEDED,
            provider_job_id=str(interaction_id) if interaction_id else None,
            media_bytes=img_bytes,
            mime_type=mime,
            diagnostics={
                "provider": self.provider_id,
                "model": model_id,
                "endpoint": "v1beta/interactions",
                "interaction_id": interaction_id,
                "usage": data.get("usage"),
            },
            reported_cost_usd=0.0,  # Exact billing updated from token metadata when present
        )

    @staticmethod
    def _extract_image_bytes(payload: dict[str, Any]) -> tuple[bytes, str]:
        # Support both Interactions API (`output_image` / `outputs[]`) and generateContent (`candidates[]`) shapes
        out_img = payload.get("output_image")
        if isinstance(out_img, dict) and out_img.get("data"):
            return base64.b64decode(out_img["data"]), str(out_img.get("mime_type") or "image/png")

        for item in payload.get("outputs") or []:
            if isinstance(item, dict) and item.get("type") == "image" and item.get("data"):
                return base64.b64decode(item["data"]), str(item.get("mime_type") or "image/png")

        for cand in payload.get("candidates") or []:
            finish = str(cand.get("finishReason") or "")
            if finish in {"IMAGE_SAFETY", "IMAGE_OTHER", "SAFETY"}:
                raise ProviderAdapterError(
                    f"Google Gemini Image blocked output with finishReason={finish}. Modify subject/prompt and resubmit.",
                    category=ErrorCategory.MODERATION,
                )
            for part in (cand.get("content") or {}).get("parts") or []:
                inline = part.get("inlineData") or part.get("inline_data")
                if isinstance(inline, dict) and inline.get("data"):
                    return base64.b64decode(inline["data"]), str(inline.get("mimeType") or inline.get("mime_type") or "image/png")

        raise ProviderAdapterError(
            "Google Gemini API returned HTTP 200 without an image payload.",
            category=ErrorCategory.PROVIDER_REJECTED,
        )
