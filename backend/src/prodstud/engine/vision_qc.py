"""Optional Multimodal Vision QC Engine (Phase 2 — Explicitly Gated, Honest Coverage & Limitations).

Combines deterministic media forensics (Pillow / ffprobe) with optional Google Gemini multimodal visual
inspection when explicitly quoted, approved, and within the user's Spend Guard cap.

Never fabricates confidence or claims objective quality certification.
"""

from __future__ import annotations

import base64
import json
import subprocess
import tempfile
from pathlib import Path
from typing import Any, Callable
from uuid import uuid4

import httpx

from prodstud.domain.enums import ErrorCategory, MediaType, QualityVerdict
from prodstud.domain.models import (
    GeneratedAssetRecord,
    ProductionPlanRecord,
    QualityDimensionScore,
    QualityFinding,
    QualityReviewRecord,
)
from prodstud.engine.quality_reviewer import KEY_AI_TELLS, review_asset
from prodstud.providers.base import ProviderAdapterError, ReferencePayload, build_http_client
from prodstud.security import redact_secrets
from prodstud.storage.asset_store import probe_video_metadata
from prodstud.storage.database import utcnow_iso

DEFAULT_VISION_QC_PROVIDER = "google_gemini_image"
DEFAULT_VISION_QC_MODEL = "gemini-3.5-flash-lite"
ESTIMATED_VISION_QC_SINGLE_USD = 0.0020
ESTIMATED_VISION_QC_COMPARE_USD = 0.0035


def _extract_video_keyframe_bytes(video_path: Path, duration_s: float) -> list[tuple[float, bytes]]:
    """Extract up to 3 real sampled PNG frames (start, midpoint, tail) via ffmpeg for multimodal inspection."""
    timestamps = [0.2, max(0.3, duration_s * 0.5), max(0.4, duration_s - 0.3)]
    frames: list[tuple[float, bytes]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, ts in enumerate(timestamps):
            out_png = Path(tmpdir) / f"vqc_frame_{idx}.png"
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-ss",
                    f"{ts:.2f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale='min(960,iw)':-2",
                    str(out_png),
                ],
                capture_output=True,
                timeout=20,
                check=False,
            )
            if proc.returncode == 0 and out_png.exists():
                frames.append((round(ts, 2), out_png.read_bytes()))
    return frames


def _build_vision_qc_prompt(
    *,
    asset: GeneratedAssetRecord,
    plan: ProductionPlanRecord,
    sampled_timestamps: list[float],
    includes_source_comparison: bool,
) -> str:
    if asset.media_type == MediaType.IMAGE and plan.image_plan:
        ip = plan.image_plan
        locks = "; ".join(ip.hard_locks) if ip.hard_locks else "None declared"
        return (
            "You are an advisory forensic photographic quality inspector. Inspect the generated image honestly.\n"
            "NEVER claim objective certification. Distinguish directly observed evidence from inferred causes.\n"
            f"PLANNED SUBJECT: {ip.subject}\n"
            f"PLANNED ENVIRONMENT: {ip.environment}\n"
            f"PLANNED OPTICS/LIGHTING: {ip.focal_length_mm}mm {ip.aperture}, key: {ip.lighting_key}, contrast: {ip.lighting_contrast_ratio}\n"
            f"HARD PRESERVATION LOCKS: {locks}\n"
            f"SOURCE REFERENCE IMAGES ATTACHED FOR COMPARISON: {'YES' if includes_source_comparison else 'NO'}\n"
            "Return STRICT JSON ONLY with this exact schema:\n"
            "{\n"
            '  "brief_adherence_score": <float 1.0..5.0>,\n'
            '  "brief_adherence_evidence": "<observed evidence>",\n'
            '  "physical_causality_score": <float 1.0..5.0>,\n'
            '  "physical_causality_evidence": "<observed lighting/shadow/DOF evidence>",\n'
            '  "preservation_score": <float 1.0..5.0 or null if no reference>,\n'
            '  "preservation_evidence": "<observed identity/product preservation evidence>",\n'
            '  "detected_ai_tells": [{"id": "T01", "status": "clear|suspected|detected", "evidence": "..."}],\n'
            '  "findings": [{"severity": "critical|warning|info", "dimension": "...", "location": "...", "observed_evidence": "...", "inferred_cause": "...", "confidence": 0.0..1.0, "suggested_correction": "..."}]\n'
            "}"
        )

    vp = plan.video_plan
    shots_desc = (
        "; ".join(f"{s.shot_id} ({s.start_s}s-{s.end_s}s): {s.subject_action}" for s in vp.shots)
        if vp
        else plan.summary
    )
    return (
        "You are an advisory forensic video quality inspector examining SAMPLED KEYFRAMES ONLY "
        f"(timestamps: {', '.join(f'{t:.2f}s' for t in sampled_timestamps)}).\n"
        "You CANNOT inspect full inter-frame motion smoothness or audio — explicitly limit claims to visible sampled frames.\n"
        f"PLANNED SHOTS: {shots_desc}\n"
        f"CONTINUITY INVARIANTS: {'; '.join(vp.continuity_invariants) if vp else 'Standard continuity'}\n"
        "Return STRICT JSON ONLY with this exact schema:\n"
        "{\n"
        '  "brief_adherence_score": <float 1.0..5.0>,\n'
        '  "brief_adherence_evidence": "<observed frame evidence>",\n'
        '  "frame_continuity_score": <float 1.0..5.0>,\n'
        '  "frame_continuity_evidence": "<observed lighting/subject/environment consistency across sampled frames>",\n'
        '  "findings": [{"severity": "critical|warning|info", "dimension": "...", "location": "<timestamp>", "observed_evidence": "...", "inferred_cause": "...", "confidence": 0.0..1.0, "suggested_correction": "..."}]\n'
        "}"
    )


def _extract_json_block(text: str) -> dict[str, Any]:
    cleaned = text.strip()
    if cleaned.startswith("```"):
        lines = cleaned.splitlines()
        cleaned = "\n".join(line for line in lines if not line.strip().startswith("```")).strip()
    start = cleaned.find("{")
    end = cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("Multimodal vision response did not contain a JSON object.")
    return json.loads(cleaned[start : end + 1])


def _clamp_score(val: Any) -> float | None:
    if val is None:
        return None
    try:
        return round(max(1.0, min(5.0, float(val))), 2)
    except Exception:
        return None


class VisionQCService:
    """Executes optional multimodal Vision QC via verified Gemini generateContent API with honest coverage disclosures."""

    def __init__(
        self,
        *,
        base_url: str = "https://generativelanguage.googleapis.com/v1beta",
        model_id: str = DEFAULT_VISION_QC_MODEL,
        timeout_seconds: float = 60.0,
        http_client_factory: Callable[[float], httpx.Client] = build_http_client,
    ):
        self.base_url = base_url.rstrip("/")
        self.model_id = model_id
        self.timeout_seconds = timeout_seconds
        self.http_client_factory = http_client_factory

    def estimate_review(
        self,
        *,
        asset: GeneratedAssetRecord,
        references: list[ReferencePayload],
    ) -> tuple[int, bool, float, str]:
        """Return (frames_to_inspect, includes_source_comparison, estimated_cost_usd, pricing_disclosure)."""
        if asset.media_type == MediaType.IMAGE:
            includes_src = len(references) > 0
            frames = 1 + min(2, len(references))
            cost = ESTIMATED_VISION_QC_COMPARE_USD if includes_src else ESTIMATED_VISION_QC_SINGLE_USD
        else:
            includes_src = False
            frames = 3
            cost = ESTIMATED_VISION_QC_COMPARE_USD

        disclosure = (
            f"Optional multimodal Vision QC via {self.model_id} (~$0.30/1M input, $2.50/1M output tokens; "
            f"estimated ~${cost:.4f} for {frames} frame(s)). Advisory inspection only — not objective certification."
        )
        return frames, includes_src, cost, disclosure

    def run_multimodal_review(
        self,
        *,
        asset: GeneratedAssetRecord,
        plan: ProductionPlanRecord,
        file_path: Path,
        references: list[ReferencePayload],
        api_key: str,
    ) -> tuple[QualityReviewRecord, float]:
        """Run deterministic forensics + approved multimodal Gemini vision check and merge honestly."""
        if not api_key or len(api_key.strip()) < 10:
            raise ProviderAdapterError(
                "Active Google Gemini API key is required for optional multimodal Vision QC.",
                category=ErrorCategory.PROVIDER_AUTH,
            )

        base_review = review_asset(asset=asset, plan=plan, file_path=file_path)
        parts: list[dict[str, Any]] = []
        sampled_timestamps: list[float] = []
        includes_source_comparison = False

        if asset.media_type == MediaType.IMAGE:
            img_bytes = file_path.read_bytes()
            includes_source_comparison = len(references) > 0
            prompt = _build_vision_qc_prompt(
                asset=asset,
                plan=plan,
                sampled_timestamps=[],
                includes_source_comparison=includes_source_comparison,
            )
            parts.append({"text": prompt})
            parts.append({"text": "GENERATED ASSET TO INSPECT:"})
            parts.append(
                {
                    "inlineData": {
                        "mimeType": asset.mime_type or "image/png",
                        "data": base64.b64encode(img_bytes).decode("ascii"),
                    }
                }
            )
            for ref in references[:2]:
                parts.append({"text": f"SOURCE REFERENCE ({ref.role}, {ref.filename}):"})
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": ref.mime_type or "image/png",
                            "data": base64.b64encode(ref.data).decode("ascii"),
                        }
                    }
                )
        else:
            probe = probe_video_metadata(file_path)
            dur = float(probe.get("duration_s") or asset.duration_s or 4.0)
            frames = _extract_video_keyframe_bytes(file_path, dur)
            if not frames:
                raise ProviderAdapterError(
                    "Unable to extract sampled video keyframes via ffmpeg for multimodal Vision QC.",
                    category=ErrorCategory.INTERNAL,
                )
            sampled_timestamps = [ts for ts, _ in frames]
            prompt = _build_vision_qc_prompt(
                asset=asset,
                plan=plan,
                sampled_timestamps=sampled_timestamps,
                includes_source_comparison=False,
            )
            parts.append({"text": prompt})
            for ts, fbytes in frames:
                parts.append({"text": f"SAMPLED VIDEO KEYFRAME AT {ts:.2f}s:"})
                parts.append(
                    {
                        "inlineData": {
                            "mimeType": "image/png",
                            "data": base64.b64encode(fbytes).decode("ascii"),
                        }
                    }
                )

        body = {
            "contents": [{"role": "user", "parts": parts}],
            "generationConfig": {"temperature": 0.1, "responseMimeType": "application/json"},
        }

        try:
            with self.http_client_factory(self.timeout_seconds) as client:
                resp = client.post(
                    f"{self.base_url}/models/{self.model_id}:generateContent",
                    headers={
                        "x-goog-api-key": api_key.strip(),
                        "Content-Type": "application/json",
                    },
                    json=body,
                )
        except httpx.TimeoutException as exc:
            raise ProviderAdapterError(
                "Multimodal Vision QC request timed out. Status is UNKNOWN; do not blindly resubmit.",
                category=ErrorCategory.TIMEOUT_UNKNOWN,
                provider_may_have_accepted=True,
            ) from exc
        except httpx.RequestError as exc:
            raise ProviderAdapterError(
                f"Network error contacting Google Gemini Vision QC: {redact_secrets(str(exc))}",
                category=ErrorCategory.NETWORK,
            ) from exc

        if resp.status_code in {401, 403}:
            raise ProviderAdapterError(
                f"Google API rejected Vision QC request (HTTP {resp.status_code}).",
                category=ErrorCategory.PROVIDER_AUTH,
            )
        if resp.status_code == 429:
            raise ProviderAdapterError(
                "Google API quota/rate limit exceeded during Vision QC (HTTP 429).",
                category=ErrorCategory.QUOTA,
            )
        if resp.status_code >= 400:
            raise ProviderAdapterError(
                f"Google Gemini Vision QC rejected request (HTTP {resp.status_code}): {redact_secrets(resp.text[:400])}",
                category=ErrorCategory.PROVIDER_REJECTED,
            )

        payload = resp.json()
        raw_text = ""
        for cand in payload.get("candidates") or []:
            for part in (cand.get("content") or {}).get("parts") or []:
                if isinstance(part, dict) and part.get("text"):
                    raw_text += str(part["text"])
        try:
            parsed = _extract_json_block(raw_text)
        except Exception as exc:
            raise ProviderAdapterError(
                f"Multimodal Vision QC returned unparseable JSON response: {redact_secrets(str(exc))}",
                category=ErrorCategory.PROVIDER_REJECTED,
            ) from exc

        # Estimate actual token cost if usageMetadata present
        usage = payload.get("usageMetadata") or {}
        in_tok = int(usage.get("promptTokenCount") or 0)
        out_tok = int(usage.get("candidatesTokenCount") or 0)
        if in_tok > 0 or out_tok > 0:
            reported_cost = round((in_tok / 1_000_000) * 0.30 + (out_tok / 1_000_000) * 2.50, 6)
        else:
            _, _, reported_cost, _ = self.estimate_review(asset=asset, references=references)

        # Merge multimodal scores into deterministic dimensions cleanly
        dimensions = [d.model_copy(deep=True) for d in base_review.dimensions]
        findings = list(base_review.findings)
        ai_tells = [dict(t) for t in base_review.ai_tell_checklist]

        if asset.media_type == MediaType.IMAGE:
            brief_score = _clamp_score(parsed.get("brief_adherence_score"))
            phys_score = _clamp_score(parsed.get("physical_causality_score"))
            pres_score = _clamp_score(parsed.get("preservation_score")) if includes_source_comparison else None

            # Replace uninspected semantic placeholder with real multimodal dimensions
            dimensions = [d for d in dimensions if d.name != "semantic_preservation_and_causality"]
            if brief_score is not None:
                dimensions.append(
                    QualityDimensionScore(
                        name="vision_brief_adherence",
                        label="Multimodal Brief Adherence",
                        weight=0.18,
                        score=brief_score,
                        critical=True,
                        observed_evidence=str(parsed.get("brief_adherence_evidence") or "Evaluated via multimodal vision."),
                        inferred_notes=f"Advisory multimodal evaluation ({self.model_id}).",
                    )
                )
            if phys_score is not None:
                dimensions.append(
                    QualityDimensionScore(
                        name="vision_physical_causality",
                        label="Multimodal Physical Lighting & Optical Causality",
                        weight=0.18,
                        score=phys_score,
                        critical=False,
                        observed_evidence=str(parsed.get("physical_causality_evidence") or "Evaluated via multimodal vision."),
                        inferred_notes=f"Advisory multimodal evaluation ({self.model_id}).",
                    )
                )
            if includes_source_comparison and pres_score is not None:
                dimensions.append(
                    QualityDimensionScore(
                        name="vision_source_preservation",
                        label="Multimodal Source Preservation Fidelity",
                        weight=0.20,
                        score=pres_score,
                        critical=True,
                        observed_evidence=str(parsed.get("preservation_evidence") or "Compared against attached source reference(s)."),
                        inferred_notes="Critical gate: score <= 2.0 forces rework_recommended.",
                    )
                )

            # Update AI Tells checklist from multimodal observations
            tell_map = {
                str(item.get("id")): item
                for item in (parsed.get("detected_ai_tells") or [])
                if isinstance(item, dict) and item.get("id")
            }
            for tell in ai_tells:
                obs = tell_map.get(tell["id"])
                if obs:
                    status = str(obs.get("status") or "requires_human_visual_check")
                    tell["check_status"] = f"vision_{status}"
                    if obs.get("evidence"):
                        tell["evidence"] = str(obs["evidence"])

            coverage = (
                f"deterministic_pixel_forensics_plus_multimodal_vision ({self.model_id}; "
                f"source_reference_comparison={'yes' if includes_source_comparison else 'no'})"
            )
            limitations = [
                f"Combines deterministic Pillow pixel forensics with advisory multimodal visual inspection ({self.model_id}).",
                "Vision models can miss subtle anatomical anomalies, micro-text typos, or exact brand color deltas — final human approval remains required.",
                "This evaluation is strictly advisory and is NOT an objective quality certification.",
            ]
            confidence = 0.80 if includes_source_comparison else 0.76
        else:
            brief_score = _clamp_score(parsed.get("brief_adherence_score"))
            cont_score = _clamp_score(parsed.get("frame_continuity_score"))
            dimensions = [d for d in dimensions if d.name != "motion_and_subject_continuity"]
            if brief_score is not None:
                dimensions.append(
                    QualityDimensionScore(
                        name="vision_sampled_brief_adherence",
                        label="Sampled-Frame Brief & Shot Alignment",
                        weight=0.20,
                        score=brief_score,
                        critical=True,
                        observed_evidence=str(parsed.get("brief_adherence_evidence") or "Evaluated across sampled video frames."),
                        inferred_notes=f"Evaluated on {len(sampled_timestamps)} sampled frames ONLY ({self.model_id}).",
                    )
                )
            if cont_score is not None:
                dimensions.append(
                    QualityDimensionScore(
                        name="vision_sampled_continuity",
                        label="Sampled-Frame Visual Continuity",
                        weight=0.20,
                        score=cont_score,
                        critical=False,
                        observed_evidence=str(parsed.get("frame_continuity_evidence") or "Evaluated across sampled video frames."),
                        inferred_notes="Cannot detect inter-frame flicker or temporal morphing between sampled timestamps.",
                    )
                )
            coverage = (
                f"ffprobe_stream_metadata_plus_{len(sampled_timestamps)}_sampled_frames_multimodal_vision "
                f"({self.model_id}) — NOT full frame-by-frame playback"
            )
            limitations = [
                f"Multimodal video inspection examined ONLY {len(sampled_timestamps)} sampled keyframes ({', '.join(f'{t:.2f}s' for t in sampled_timestamps)}) — NOT full frame-by-frame motion playback.",
                "Inter-frame morphing, camera jitter, audio sync, and rapid mid-shot glitches require human full-clip playback.",
                "This evaluation is strictly advisory and is NOT an objective quality certification.",
            ]
            confidence = 0.71

        # Add multimodal findings cleanly
        for fitem in parsed.get("findings") or []:
            if not isinstance(fitem, dict):
                continue
            sev = str(fitem.get("severity") or "info").lower()
            if sev not in {"critical", "warning", "info"}:
                sev = "info"
            findings.append(
                QualityFinding(
                    severity=sev,
                    dimension=str(fitem.get("dimension") or "multimodal_vision"),
                    location_or_timestamp=str(fitem.get("location") or "Frame"),
                    observed_evidence=str(fitem.get("observed_evidence") or "Visual anomaly noted by vision model."),
                    inferred_cause=str(fitem.get("inferred_cause") or "Advisory multimodal visual inference."),
                    confidence=round(max(0.1, min(0.95, float(fitem.get("confidence") or 0.7))), 2),
                    suggested_correction=str(fitem.get("suggested_correction") or "Review asset visually and apply targeted revision if confirmed."),
                )
            )

        # Normalize dimension weights visibly
        total_w = sum(d.weight for d in dimensions if d.weight > 0)
        if total_w > 0:
            for d in dimensions:
                d.weight = round(d.weight / total_w, 4)

        scored = [d for d in dimensions if d.score is not None]
        w_sum = sum(d.weight for d in scored)
        weighted_score = round(sum((d.weight / w_sum) * float(d.score) for d in scored), 2) if scored and w_sum > 0 else None

        critical_fail = any(d.critical and d.score is not None and d.score <= 2.0 for d in dimensions)
        has_warnings = any(f.severity in {"critical", "warning"} for f in findings)
        if critical_fail:
            verdict = QualityVerdict.REWORK_RECOMMENDED
        elif has_warnings or (weighted_score is not None and weighted_score < 4.0):
            verdict = QualityVerdict.REVIEW_RECOMMENDED
        else:
            verdict = QualityVerdict.PASS_ADVISORY

        review = QualityReviewRecord(
            id=f"qcr_{uuid4().hex[:14]}",
            asset_id=asset.id,
            plan_id=plan.id,
            media_type=asset.media_type,
            advisory_verdict=verdict,
            weighted_score=weighted_score,
            confidence=confidence,
            inspection_coverage=coverage,
            limitations=limitations,
            dimensions=dimensions,
            findings=findings,
            ai_tell_checklist=ai_tells,
            design_fit_notes=base_review.design_fit_notes,
            created_at=utcnow_iso(),
        )
        return review, reported_cost
