"""Explicitly badged Local Test Fixture Adapters (Development & Test ONLY — strictly disabled in production).

Generates genuine deterministic binary PNG images (Pillow) and playable H.264 MP4 videos (FFmpeg)
at $0.00 cost so the full end-to-end production workflow (plan -> approve -> async job -> preview ->
forensic QC -> targeted revision -> export) can be verified without spending money or faking Google API results.
Every rendered artifact is visibly labeled 'LOCAL TEST RENDER · NON-BILLABLE WORKFLOW VERIFICATION'.
"""

from __future__ import annotations

import hashlib
import io
import math
import subprocess
import tempfile
import textwrap
from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

from prodstud.domain.enums import CapabilitySupport, ErrorCategory, JobStatus, MediaType
from prodstud.domain.models import ProductionPlanRecord, ProviderModelCapability
from prodstud.providers.base import (
    ImageProviderAdapter,
    ProviderAdapterError,
    ProviderSubmissionResult,
    ReferencePayload,
    VideoProviderAdapter,
)

IMAGE_DIMENSIONS = {
    "1:1": (1024, 1024),
    "3:2": (1200, 800),
    "2:3": (800, 1200),
    "4:5": (960, 1200),
    "5:4": (1200, 960),
    "4:3": (1152, 864),
    "3:4": (864, 1152),
    "16:9": (1280, 720),
    "9:16": (720, 1280),
    "21:9": (1344, 576),
}

VIDEO_DIMENSIONS = {
    "16:9": (960, 540),
    "9:16": (540, 960),
    "1:1": (720, 720),
}


def _load_font(size: int) -> ImageFont.ImageFont | ImageFont.FreeTypeFont:
    for candidate in (
        "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    ):
        if Path(candidate).exists():
            try:
                return ImageFont.truetype(candidate, size)
            except Exception:
                pass
    return ImageFont.load_default()


def _kelvin_accent(kelvin: int) -> tuple[int, int, int]:
    if kelvin <= 3600:
        return (224, 145, 58)  # Warm tungsten
    if kelvin >= 6000:
        return (104, 166, 224)  # Cool daylight
    return (188, 178, 162)  # Balanced studio neutral


def _render_blueprint_png(plan: ProductionPlanRecord, references: list[ReferencePayload]) -> bytes:
    assert plan.image_plan is not None
    ip = plan.image_plan
    w, h = IMAGE_DIMENSIONS.get(ip.aspect_ratio, (1200, 800))

    seed_bytes = hashlib.sha256(f"{plan.id}:{ip.subject}:{ip.color_temperature_k}:{plan.version}".encode()).digest()
    accent = _kelvin_accent(ip.color_temperature_k)

    img = Image.new("RGB", (w, h), (22, 25, 30))
    draw = ImageDraw.Draw(img)

    # Subtle calibrated light-field gradient simulating motivated key direction from camera left
    for y in range(0, h, 4):
        for x in range(0, w, 8):
            nx = x / max(1, w)
            ny = y / max(1, h)
            # Key falloff from upper-left toward lower-right
            dist = math.hypot((nx - 0.25) * 1.1, (ny - 0.30) * 1.1)
            glow = max(0.0, 1.0 - dist * 1.05)
            r = int(20 + glow * (accent[0] * 0.32))
            g = int(23 + glow * (accent[1] * 0.32))
            b = int(28 + glow * (accent[2] * 0.32))
            draw.rectangle([x, y, x + 8, y + 4], fill=(min(245, r), min(245, g), min(245, b)))

    # Rule-of-thirds optical viewfinder frame & safe margins
    margin = int(min(w, h) * 0.06)
    draw.rectangle([margin, margin, w - margin, h - margin], outline=(82, 92, 106), width=2)
    for frac in (1 / 3, 2 / 3):
        gx = int(margin + (w - 2 * margin) * frac)
        gy = int(margin + (h - 2 * margin) * frac)
        draw.line([(gx, margin), (gx, h - margin)], fill=(54, 60, 70), width=1)
        draw.line([(margin, gy), (w - margin, gy)], fill=(54, 60, 70), width=1)

    # Subject geometric focal target & contact shadow demonstration
    cx, cy = int(w * 0.50), int(h * 0.50)
    rad = int(min(w, h) * 0.16)
    draw.ellipse([cx - rad + 22, cy + rad - 12, cx + rad + 30, cy + rad + 20], fill=(12, 14, 17))
    draw.ellipse([cx - rad, cy - rad, cx + rad, cy + rad], fill=(42, 47, 56), outline=accent, width=3)
    draw.ellipse([cx - rad // 2, cy - rad // 2, cx + rad // 4, cy + rad // 4], fill=(min(255, accent[0]), min(255, accent[1]), min(255, accent[2])))

    # Reference thumbnail strip if references were attached
    if references:
        rx = margin + 16
        ry = h - margin - 92
        for ref in references[:4]:
            try:
                with Image.open(io.BytesIO(ref.data)) as rimg:
                    thumb = rimg.convert("RGB")
                    thumb.thumbnail((72, 72))
                    img.paste(thumb, (rx, ry))
                    draw.rectangle([rx - 1, ry - 1, rx + thumb.width + 1, ry + thumb.height + 1], outline=accent, width=2)
                    rx += thumb.width + 14
            except Exception:
                continue

    font_lg = _load_font(22)
    font_md = _load_font(15)
    font_sm = _load_font(13)

    # Honest non-billable test render banner
    draw.rectangle([margin, margin, w - margin, margin + 38], fill=(38, 30, 20))
    draw.text(
        (margin + 14, margin + 11),
        "LOCAL TEST RENDER  ·  NON-BILLABLE WORKFLOW VERIFICATION (NOT GOOGLE LIVE)",
        fill=(242, 180, 92),
        font=font_sm,
    )

    # Production telemetry overlay
    title_lines = textwrap.wrap(f"SUBJECT: {ip.subject}", width=58)[:2]
    ty = margin + 54
    for line in title_lines:
        draw.text((margin + 18, ty), line, fill=(241, 243, 245), font=font_lg)
        ty += 28

    meta_lines = [
        f"PLAN v{plan.version}  |  MODE: {plan.task_mode.value}  |  CLASS: {ip.reality_class}",
        f"OPTICS: {ip.focal_length_mm}mm · {ip.aperture} · {ip.aspect_ratio} ({w}x{h}px) · {ip.resolution}",
        f"LIGHTING: ~{ip.color_temperature_k}K · {ip.lighting_contrast_ratio}",
        f"ENVIRONMENT: {ip.environment[:76]}",
        f"LOCKS: {len(ip.hard_locks)} hard lock(s) · {len(references)} reference(s) · SIG:{seed_bytes.hex()[:8]}",
    ]
    my = h - margin - (len(meta_lines) * 20) - (100 if references else 14)
    for mline in meta_lines:
        draw.text((margin + 18, my), mline, fill=(178, 186, 198), font=font_md)
        my += 21

    out = io.BytesIO()
    img.save(out, format="PNG")
    return out.getvalue()


class LocalTestImageAdapter(ImageProviderAdapter):
    """Non-billable local verification image adapter (development/test only)."""

    provider_id = "local_test_fixture"
    provider_name = "Local Test Fixture (Non-Billable Dev/Test)"

    def capabilities(self) -> list[ProviderModelCapability]:
        return [
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="local-optical-slate-v1",
                display_name="Local Optical Slate Fixture (Non-Billable Test Render)",
                media_type=MediaType.IMAGE,
                support_status=CapabilitySupport.SUPPORTED,
                is_billable=False,
                is_local_test_fixture=True,
                requires_credential=False,
                supported_aspect_ratios=list(IMAGE_DIMENSIONS.keys()),
                supported_resolutions=["1K", "2K", "4K"],
                max_reference_images=14,
                supports_multi_turn_edit=True,
                pricing_note="$0.00 — Non-billable local workflow verification render (NOT a live Google AI generation).",
                estimated_unit_cost_usd=0.0,
                official_doc_url="https://github.com/zakshub/prodstud/blob/main/docs/DECISIONS.md",
                verified_date="2026-11-19",
                limitations=[
                    "Renders deterministic optical slate diagrams for local E2E testing only.",
                    "Disabled automatically in production environment.",
                ],
            )
        ]

    def validate_request(self, plan: ProductionPlanRecord, model_id: str, references: list[ReferencePayload]) -> list[str]:
        if plan.media_type != MediaType.IMAGE or not plan.image_plan:
            return ["Requires an Image production plan."]
        if plan.image_plan.aspect_ratio not in IMAGE_DIMENSIONS:
            return [f"Aspect ratio '{plan.image_plan.aspect_ratio}' unsupported by local test fixture."]
        return []

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
        png_bytes = _render_blueprint_png(plan, references)
        return ProviderSubmissionResult(
            status=JobStatus.SUCCEEDED,
            provider_job_id=f"local_img_{idempotency_key[:12]}",
            media_bytes=png_bytes,
            mime_type="image/png",
            diagnostics={"provider": self.provider_id, "model": model_id, "is_local_test_fixture": True},
            reported_cost_usd=0.0,
        )


class LocalTestVideoAdapter(VideoProviderAdapter):
    """Non-billable local verification video adapter generating real playable H.264 MP4 clips via FFmpeg."""

    provider_id = "local_test_fixture"
    provider_name = "Local Test Fixture (Non-Billable Dev/Test)"

    def __init__(self) -> None:
        self._completed: dict[str, tuple[bytes, str]] = {}

    def capabilities(self) -> list[ProviderModelCapability]:
        return [
            ProviderModelCapability(
                provider_id=self.provider_id,
                provider_name=self.provider_name,
                model_id="local-shot-animatic-v1",
                display_name="Local Shot-Animatic Fixture (Non-Billable MP4 Test Render)",
                media_type=MediaType.VIDEO,
                support_status=CapabilitySupport.SUPPORTED,
                is_billable=False,
                is_local_test_fixture=True,
                requires_credential=False,
                supported_aspect_ratios=list(VIDEO_DIMENSIONS.keys()),
                supported_resolutions=["360p", "720p", "1080p"],
                min_duration_s=3,
                max_duration_s=15,
                max_reference_images=6,
                supports_multi_turn_edit=True,
                supports_first_last_frame=True,
                supports_video_extension=True,
                supports_cancellation=True,
                pricing_note="$0.00 — Non-billable local animated shot-slate MP4 for workflow testing (NOT live Google AI video).",
                estimated_unit_cost_usd=0.0,
                official_doc_url="https://github.com/zakshub/prodstud/blob/main/docs/DECISIONS.md",
                verified_date="2026-11-19",
                limitations=[
                    "Renders deterministic timed shot-slate MP4 animatics for local E2E testing only.",
                    "Disabled automatically in production environment.",
                ],
            )
        ]

    def validate_request(self, plan: ProductionPlanRecord, model_id: str, references: list[ReferencePayload]) -> list[str]:
        if plan.media_type != MediaType.VIDEO or not plan.video_plan:
            return ["Requires a timed Video production plan."]
        if plan.video_plan.aspect_ratio not in VIDEO_DIMENSIONS:
            return [f"Aspect ratio '{plan.video_plan.aspect_ratio}' unsupported by local test video fixture."]
        if not (3.0 <= plan.video_plan.total_duration_s <= 15.0):
            return ["Local test video fixture supports 3–15s clips matching Gemini Omni 1.2 Flash single-clip window."]
        return []

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
        errors = self.validate_request(plan, model_id, references)
        if errors:
            raise ProviderAdapterError("; ".join(errors), category=ErrorCategory.VALIDATION)

        mp4_bytes = self._render_animatic_mp4(plan)
        pjid = f"local_vid_{idempotency_key[:12]}"
        self._completed[pjid] = (mp4_bytes, "video/mp4")
        return ProviderSubmissionResult(
            status=JobStatus.PROCESSING,
            provider_job_id=pjid,
            diagnostics={"provider": self.provider_id, "model": model_id, "is_local_test_fixture": True},
            reported_cost_usd=0.0,
        )

    def poll_status(self, *, provider_job_id: str, model_id: str, api_key: str | None) -> ProviderSubmissionResult:
        item = self._completed.pop(provider_job_id, None)
        if not item:
            raise ProviderAdapterError("Local test video job result already consumed or missing.", category=ErrorCategory.INTERNAL)
        mp4_bytes, mime = item
        return ProviderSubmissionResult(
            status=JobStatus.SUCCEEDED,
            provider_job_id=provider_job_id,
            media_bytes=mp4_bytes,
            mime_type=mime,
            diagnostics={"provider": self.provider_id, "model": model_id, "is_local_test_fixture": True},
            reported_cost_usd=0.0,
        )

    def cancel(self, *, provider_job_id: str, api_key: str | None) -> bool:
        self._completed.pop(provider_job_id, None)
        return True

    def _render_animatic_mp4(self, plan: ProductionPlanRecord) -> bytes:
        assert plan.video_plan is not None
        vp = plan.video_plan
        w, h = VIDEO_DIMENSIONS.get(vp.aspect_ratio, (960, 540))
        fps = 24
        # Render keyframe per 0.5s (2 Hz input upsampled cleanly to 24 FPS H.264 MP4) -> fast (<0.8s) & valid playable MP4!
        sample_hz = 2
        total_samples = max(6, int(round(vp.total_duration_s * sample_hz)))
        font_lg = _load_font(20)
        font_md = _load_font(14)
        font_sm = _load_font(12)

        with tempfile.TemporaryDirectory() as tmpdir:
            tmp = Path(tmpdir)
            for idx in range(total_samples):
                t = idx / sample_hz
                active_shot = vp.shots[-1]
                for shot in vp.shots:
                    if shot.start_s <= t < shot.end_s:
                        active_shot = shot
                        break

                img = Image.new("RGB", (w, h), (20, 23, 28))
                draw = ImageDraw.Draw(img)
                # Subtle progress sweep bar simulating camera motion across shot
                shot_progress = min(1.0, max(0.0, (t - active_shot.start_s) / max(0.1, active_shot.duration_s)))
                accent = (224, 145, 46)
                margin = 28
                draw.rectangle([margin, margin, w - margin, h - margin], outline=(68, 76, 88), width=2)
                draw.rectangle([margin, margin, w - margin, margin + 32], fill=(40, 31, 19))
                draw.text(
                    (margin + 12, margin + 9),
                    "LOCAL TEST ANIMATIC  ·  NON-BILLABLE WORKFLOW VERIFICATION (NOT GOOGLE LIVE)",
                    fill=(242, 180, 92),
                    font=font_sm,
                )

                # Moving viewfinder marker
                bar_x0 = margin + 24
                bar_x1 = w - margin - 24
                bar_y = h // 2
                draw.line([(bar_x0, bar_y), (bar_x1, bar_y)], fill=(60, 68, 80), width=4)
                marker_x = int(bar_x0 + (bar_x1 - bar_x0) * shot_progress)
                draw.ellipse([marker_x - 10, bar_y - 10, marker_x + 10, bar_y + 10], fill=accent)

                draw.text(
                    (margin + 18, margin + 48),
                    f"{active_shot.shot_id} ({active_shot.order}/{len(vp.shots)})  ·  TC 00:{t:04.1f} / 00:{vp.total_duration_s:04.1f}  ·  {active_shot.lens_focal_mm}mm",
                    fill=(241, 243, 245),
                    font=font_lg,
                )
                draw.text((margin + 18, margin + 80), f"FRAMING: {active_shot.framing[:68]}", fill=(200, 208, 218), font=font_md)
                draw.text((margin + 18, margin + 104), f"CAMERA:  {active_shot.camera_movement[:68]}", fill=(200, 208, 218), font=font_md)
                draw.text((margin + 18, margin + 128), f"ACTION:  {active_shot.subject_action[:68]}", fill=(170, 178, 190), font=font_md)
                draw.text((margin + 18, h - margin - 52), f"CONTINUITY: {active_shot.lighting_continuity[:68]}", fill=(150, 160, 174), font=font_sm)
                draw.text((margin + 18, h - margin - 30), f"TRANSITION: {active_shot.transition_out[:68]}  |  PLAN v{plan.version}", fill=(150, 160, 174), font=font_sm)

                img.save(tmp / f"f_{idx:04d}.png", format="PNG")

            out_mp4 = tmp / "out.mp4"
            proc = subprocess.run(
                [
                    "ffmpeg",
                    "-y",
                    "-framerate",
                    str(sample_hz),
                    "-i",
                    str(tmp / "f_%04d.png"),
                    "-t",
                    f"{vp.total_duration_s:.2f}",
                    "-r",
                    str(fps),
                    "-c:v",
                    "libx264",
                    "-pix_fmt",
                    "yuv420p",
                    "-movflags",
                    "+faststart",
                    str(out_mp4),
                ],
                capture_output=True,
                timeout=30,
                check=False,
            )
            if proc.returncode != 0 or not out_mp4.exists():
                raise ProviderAdapterError(
                    f"FFmpeg failed rendering local test animatic: {proc.stderr.decode('utf-8', errors='ignore')[:300]}",
                    category=ErrorCategory.INTERNAL,
                )
            return out_mp4.read_bytes()
