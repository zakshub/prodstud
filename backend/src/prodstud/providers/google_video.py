"""Verified Google Gemini Video Provider Adapter (Official Nov 2026 APIs: Gemini Omni 1.2 Flash & Veo 3.1 GA record).

Official documentation verified 2026-11-19:
- https://aistudio.google.com/docs/video
- https://aistudio.google.com/docs/omni
- https://aistudio.google.com/docs/models/gemini-omni-flash
- https://aistudio.google.com/docs/veo (Veo 3.1 Preview shut down in Gemini API on Oct 22, 2026)
- https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate
"""

from __future__ import annotations

import base64
from typing import Any

import httpx

from prodstud.domain.enums import CapabilitySupport, ErrorCategory, JobStatus, MediaType
from prodstud.domain.models import ProductionPlanRecord, ProviderModelCapability
from prodstud.providers.base import (
    ProviderAdapterError,
    ProviderSubmissionResult,
    ReferencePayload,
    VideoProviderAdapter,
    build_http_client,
)
from prodstud.security import redact_secrets

VERIFIED_DATE = "2026-11-19"


def _compile_google_video_directive(plan: ProductionPlanRecord) -> str:
    """Translate timed VideoSequencePlan (shots, camera moves, continuity, transitions) inside adapter boundary."""
    vp = plan.video_plan
    assert vp is not None
    is_extension = vp.extended_from_asset_id is not None and vp.extension_duration_s is not None
    if is_extension:
        # Focus continuation directive on newly appended tail shots while anchoring full continuity invariants
        seam_s = round(max(0.0, vp.total_duration_s - float(vp.extension_duration_s or 0.0)), 1)
        tail_shots = [s for s in vp.shots if s.start_s >= seam_s - 0.15] or vp.shots[-1:]
        lines = [
            f"MULTI-TURN VIDEO EXTENSION (+{vp.extension_duration_s:.1f}s continuation from {seam_s:.1f}s -> {vp.total_duration_s:.1f}s total)",
            f"SEQUENCE INTENT: {vp.sequence_intent}",
            f"FORMAT: {vp.extension_duration_s:.1f}s extension turn, {vp.fps} FPS, {vp.aspect_ratio} ({vp.resolution}).",
            "CONTINUATION SHOT LIST (SEAMLESSLY CONTINUE FROM CLOSING FRAME OF PRIOR TURN):",
        ]
        for s in tail_shots:
            lines.append(
                f"- {s.shot_id} [{s.start_s:.1f}s–{s.end_s:.1f}s, {s.duration_s:.1f}s]: "
                f"Framing: {s.framing} ({s.lens_focal_mm}mm). Action: {s.subject_action}. "
                f"Camera Movement: {s.camera_movement}. Lighting: {s.lighting_continuity}. "
                f"Environment: {s.environment_continuity}. Transition out: {s.transition_out}."
            )
    else:
        lines = [
            f"SEQUENCE INTENT: {vp.sequence_intent}",
            f"FORMAT: {vp.total_duration_s}s total, {vp.fps} FPS, {vp.aspect_ratio} ({vp.resolution}).",
            "TIMED SHOT LIST:",
        ]
        for s in vp.shots:
            lines.append(
                f"- {s.shot_id} [{s.start_s:.1f}s–{s.end_s:.1f}s, {s.duration_s:.1f}s]: "
                f"Framing: {s.framing} ({s.lens_focal_mm}mm). Action: {s.subject_action}. "
                f"Camera Movement: {s.camera_movement}. Lighting: {s.lighting_continuity}. "
                f"Environment: {s.environment_continuity}. Transition out: {s.transition_out}."
            )
    if vp.continuity_invariants:
        lines.append("CONTINUITY INVARIANTS (PRESERVE ACROSS ALL SHOTS): " + " | ".join(vp.continuity_invariants))
    return "\n".join(lines)


class GoogleVideoAdapter(VideoProviderAdapter):
    """Dedicated async Google Gemini Video adapter (Gemini Omni 1.2 Flash via Interactions API)."""

    provider_id = "google_gemini_video"
    provider_name = "Google Gemini API (Video)"

    def __init__(
        self,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        timeout_seconds: float = 90.0,
    ):
        self.base_url = base_url.rstrip("/")
        self.timeout_seconds = timeout_seconds

    def capabilities(self) -> list[ProviderModelCapability]:
        return [
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="gemini-omni-1.2-flash",
                display_name="Google Gemini Omni 1.2 Flash (Video)",
                media_type=MediaType.VIDEO,
                support_status=CapabilitySupport.SUPPORTED,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=["16:9", "9:16", "1:1"],
                supported_resolutions=["360p", "720p", "1080p", "4K"],
                min_duration_s=3,
                max_duration_s=15,
                max_reference_images=6,
                supports_multi_turn_edit=True,
                supports_first_last_frame=True,
                supports_video_extension=True,
                supports_cancellation=True,
                pricing_note=(
                    "Paid Tier ONLY (Free tier unsupported). Token/per-second billing varies by resolution; "
                    "verify exact rate at aistudio.google.com/docs/pricing#gemini-omni-1.2-flash before approval."
                ),
                estimated_unit_cost_usd=None,  # Dynamic token billing — do not invent fixed USD guess
                official_doc_url="https://aistudio.google.com/docs/models/gemini-omni-flash",
                verified_date=VERIFIED_DATE,
                limitations=[
                    "3–15s single-turn clips (3–10s for first/last frame interpolation and per-turn extension up to 30s total).",
                    "Paid Tier required; generates native synchronized audio alongside video (24 FPS MP4).",
                    "GET /v1beta/interactions/{id} returns inline base64 MP4 on completion.",
                ],
            ),
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="veo-3.1-generate-001",
                display_name="Google Veo 3.1 GA (Enterprise Agent Platform / Vertex AI)",
                media_type=MediaType.VIDEO,
                support_status=CapabilitySupport.PROVIDER_CONDITIONAL,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=["16:9", "9:16"],
                supported_resolutions=["720p", "1080p"],
                supported_durations_s=[4, 6, 8],
                min_duration_s=4,
                max_duration_s=8,
                max_reference_images=3,
                supports_multi_turn_edit=False,
                supports_first_last_frame=True,
                supports_video_extension=True,
                supports_cancellation=False,
                pricing_note="Google Cloud Vertex / Gemini Enterprise Agent Platform billing; requires GCP Project, ADC OAuth, and GCS bucket.",
                estimated_unit_cost_usd=None,
                official_doc_url="https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate",
                verified_date=VERIFIED_DATE,
                limitations=[
                    "Requires Google Cloud OAuth/ADC and GCS output bucket (not accessible via simple Gemini Developer API key).",
                    "Reference-image mode and 1080p require exactly 8s duration.",
                ],
            ),
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="veo-3.1-generate-preview",
                display_name="Veo 3.1 Preview (Shut Down in Gemini API 2026-10-22)",
                media_type=MediaType.VIDEO,
                support_status=CapabilitySupport.UNSUPPORTED,
                is_billable=True,
                requires_credential=True,
                supported_aspect_ratios=[],
                supported_resolutions=[],
                max_reference_images=0,
                pricing_note="Shut down on October 22, 2026 in Gemini Developer API. Migrate to gemini-omni-1.2-flash.",
                estimated_unit_cost_usd=None,
                official_doc_url="https://aistudio.google.com/docs/veo",
                verified_date=VERIFIED_DATE,
                limitations=["Shut down October 22, 2026."],
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
            return [f"Unknown Google video model '{model_id}'."]
        if cap.support_status in {CapabilitySupport.UNSUPPORTED, CapabilitySupport.PROVIDER_CONDITIONAL}:
            return [f"Model '{model_id}' status is '{cap.support_status.value}': {cap.pricing_note}"]
        if plan.media_type != MediaType.VIDEO or not plan.video_plan:
            return ["GoogleVideoAdapter only accepts timed Video production plans."]
        vp = plan.video_plan
        is_extension = vp.extended_from_asset_id is not None or vp.extension_duration_s is not None
        if vp.aspect_ratio not in cap.supported_aspect_ratios:
            errors.append(f"Aspect ratio '{vp.aspect_ratio}' unsupported by {model_id}.")
        if vp.resolution not in cap.supported_resolutions:
            errors.append(f"Resolution '{vp.resolution}' unsupported by {model_id}.")
        if is_extension:
            if not cap.supports_video_extension:
                errors.append(f"Model '{model_id}' does not support multi-turn video extension.")
            ext_dur = float(vp.extension_duration_s or 0.0)
            if not (3.0 <= ext_dur <= 10.0):
                errors.append(f"Extension duration {ext_dur:.1f}s must be between 3s and 10s for {model_id}.")
            if vp.total_duration_s > 30.0:
                errors.append(f"Cumulative extended duration {vp.total_duration_s:.1f}s exceeds 30s multi-turn ceiling for {model_id}.")
            if not vp.source_provider_job_id:
                errors.append(
                    f"Multi-turn extension on {model_id} requires a source Google previous_interaction_id from a prior Google video job."
                )
        else:
            if cap.min_duration_s and vp.total_duration_s < cap.min_duration_s:
                errors.append(f"Duration {vp.total_duration_s}s is below minimum {cap.min_duration_s}s for {model_id}.")
            if cap.max_duration_s and vp.total_duration_s > cap.max_duration_s:
                errors.append(f"Duration {vp.total_duration_s}s exceeds single-clip maximum {cap.max_duration_s}s for {model_id}.")
        if len(references) > cap.max_reference_images:
            errors.append(f"{len(references)} references exceed {model_id} maximum of {cap.max_reference_images}.")
        return errors

    def validate_credential(self, api_key: str) -> tuple[bool, str]:
        if not api_key or len(api_key.strip()) < 10:
            return False, "API key format appears invalid."
        try:
            with build_http_client(15.0) as client:
                resp = client.get(
                    f"{self.base_url}/models/gemini-omni-1.2-flash",
                    headers={"x-goog-api-key": api_key.strip()},
                )
            if resp.status_code == 200:
                return True, "Credential verified against Google Gemini API (gemini-omni-1.2-flash accessible)."
            if resp.status_code in {401, 403}:
                return False, f"Google API rejected key (HTTP {resp.status_code})."
            return False, f"Google API returned HTTP {resp.status_code}."
        except Exception as exc:
            return False, f"Validation error: {redact_secrets(str(exc))}"

    def submit(
        self,
        *,
        plan: ProductionPlanRecord,
        model_id: str,
        references: list[ReferencePayload],
        api_key: str | None,
        idempotency_key: str,
        previous_provider_job_id: str | None = None,
    ) -> ProviderSubmissionResult:
        if not api_key:
            raise ProviderAdapterError("Missing server-side Google API key.", category=ErrorCategory.PROVIDER_AUTH)
        errors = self.validate_request(plan, model_id, references)
        if errors:
            raise ProviderAdapterError("; ".join(errors), category=ErrorCategory.VALIDATION)

        assert plan.video_plan is not None
        vp = plan.video_plan
        is_extension = vp.extended_from_asset_id is not None and vp.extension_duration_s is not None
        turn_duration_s = int(round(vp.extension_duration_s)) if is_extension and vp.extension_duration_s else int(round(vp.total_duration_s))
        effective_prev_id = previous_provider_job_id or vp.source_provider_job_id
        directive = _compile_google_video_directive(plan)

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
            "background": True,
            "input": input_items if references else directive,
            "response_format": {
                "type": "video",
                "aspect_ratio": vp.aspect_ratio,
                "resolution": vp.resolution,
                "duration": turn_duration_s,
            },
        }
        if effective_prev_id:
            body["previous_interaction_id"] = effective_prev_id

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
            raise ProviderAdapterError(
                "Video submission timed out. Provider acceptance is UNKNOWN — do not blindly resubmit.",
                category=ErrorCategory.TIMEOUT_UNKNOWN,
                provider_may_have_accepted=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError(
                f"Network error contacting Google Gemini Video API: {redact_secrets(str(exc))}",
                category=ErrorCategory.NETWORK,
            ) from exc

        if resp.status_code in {401, 403}:
            raise ProviderAdapterError(f"Google Video API auth failed (HTTP {resp.status_code}).", category=ErrorCategory.PROVIDER_AUTH)
        if resp.status_code == 429:
            raise ProviderAdapterError("Google Video API quota/rate limit exceeded (HTTP 429).", category=ErrorCategory.QUOTA)
        if resp.status_code >= 400:
            detail = redact_secrets(resp.text[:500])
            cat = ErrorCategory.MODERATION if "SAFETY" in detail.upper() or "BLOCK" in detail.upper() else ErrorCategory.PROVIDER_REJECTED
            raise ProviderAdapterError(f"Google Gemini Video rejected request (HTTP {resp.status_code}): {detail}", category=cat)

        data = resp.json()
        interaction_id = str(data.get("id") or "")
        return self._parse_interaction_response(data, model_id, interaction_id)

    def poll_status(self, *, provider_job_id: str, model_id: str, api_key: str | None) -> ProviderSubmissionResult:
        if not api_key:
            raise ProviderAdapterError("Missing server-side Google API key for status polling.", category=ErrorCategory.PROVIDER_AUTH)
        try:
            with build_http_client(self.timeout_seconds) as client:
                resp = client.get(
                    f"{self.base_url}/interactions/{provider_job_id}",
                    headers={"x-goog-api-key": api_key},
                )
        except httpx.TimeoutException as exc:
            raise ProviderAdapterError(
                "Polling timed out; job state remains UNKNOWN until next status check.",
                category=ErrorCategory.TIMEOUT_UNKNOWN,
                provider_may_have_accepted=True,
                provider_job_id=provider_job_id,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError(f"Polling network error: {redact_secrets(str(exc))}", category=ErrorCategory.NETWORK) from exc

        if resp.status_code >= 400:
            raise ProviderAdapterError(
                f"Google Video status poll error (HTTP {resp.status_code}): {redact_secrets(resp.text[:400])}",
                category=ErrorCategory.PROVIDER_REJECTED,
                provider_job_id=provider_job_id,
            )
        return self._parse_interaction_response(resp.json(), model_id, provider_job_id)

    def cancel(self, *, provider_job_id: str, api_key: str | None) -> bool:
        if not api_key or not provider_job_id:
            return False
        try:
            with build_http_client(20.0) as client:
                resp = client.post(
                    f"{self.base_url}/interactions/{provider_job_id}:cancel",
                    headers={"x-goog-api-key": api_key},
                )
            return resp.status_code < 400
        except Exception:
            return False

    def _parse_interaction_response(
        self,
        data: dict[str, Any],
        model_id: str,
        interaction_id: str,
    ) -> ProviderSubmissionResult:
        raw_status = str(data.get("status") or "").lower()
        if raw_status in {"in_progress", "queued", "running", "pending"}:
            mapped = JobStatus.QUEUED if raw_status in {"queued", "pending"} else JobStatus.PROCESSING
            return ProviderSubmissionResult(
                status=mapped,
                provider_job_id=interaction_id or None,
                diagnostics={"provider": self.provider_id, "model": model_id, "interaction_status": raw_status},
            )
        if raw_status in {"failed", "cancelled"}:
            raise ProviderAdapterError(
                f"Google Video interaction ended with status '{raw_status}': {redact_secrets(str(data.get('error') or ''))}",
                category=ErrorCategory.PROVIDER_REJECTED,
                provider_job_id=interaction_id or None,
            )

        # Completed -> extract inline base64 MP4
        for key in ("output_video", "video"):
            vid = data.get(key)
            if isinstance(vid, dict) and vid.get("data"):
                return ProviderSubmissionResult(
                    status=JobStatus.SUCCEEDED,
                    provider_job_id=interaction_id or None,
                    media_bytes=base64.b64decode(vid["data"]),
                    mime_type=str(vid.get("mime_type") or "video/mp4"),
                    diagnostics={"provider": self.provider_id, "model": model_id, "usage": data.get("usage")},
                )
        for item in data.get("outputs") or []:
            if isinstance(item, dict) and item.get("type") == "video" and item.get("data"):
                return ProviderSubmissionResult(
                    status=JobStatus.SUCCEEDED,
                    provider_job_id=interaction_id or None,
                    media_bytes=base64.b64decode(item["data"]),
                    mime_type=str(item.get("mime_type") or "video/mp4"),
                    diagnostics={"provider": self.provider_id, "model": model_id, "usage": data.get("usage")},
                )

        return ProviderSubmissionResult(
            status=JobStatus.PROCESSING,
            provider_job_id=interaction_id or None,
            diagnostics={"provider": self.provider_id, "model": model_id, "interaction_status": raw_status or "submitted"},
        )
