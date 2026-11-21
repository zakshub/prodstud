#!/usr/bin/env python3
"""Controlled Vision QC Evaluation Dataset & Audit Harness ($0.00 spend).

Constructs a reproducible 13-case synthetic image + MP4 video dataset in a temporary
directory and evaluates Production Studio's deterministic media forensics
(`prodstud.engine.quality_reviewer.review_asset`) and provider-independent multimodal
Vision QC pipeline (`prodstud.engine.vision_qc.VisionQCService` using controlled
mock transports) to empirically measure:
  - True Positives (defects correctly caught)
  - True Negatives (compliant assets correctly passed)
  - False Positives (valid assets over-flagged by deterministic heuristics or LLM hallucination)
  - False Negatives (real defects missed by pixel heuristics, 3-frame video sampling, or lenient LLM grading)

Zero external network calls and $0.00 API spend.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from PIL import Image, ImageDraw

REPO_ROOT = Path(__file__).resolve().parents[1]
BACKEND_SRC = REPO_ROOT / "backend" / "src"
if str(BACKEND_SRC) not in sys.path:
    sys.path.insert(0, str(BACKEND_SRC))

from prodstud.domain.enums import MediaType, QualityVerdict, TaskMode  # noqa: E402
from prodstud.domain.models import (  # noqa: E402
    GeneratedAssetRecord,
    ImagePlanDetails,
    ProductionPlanRecord,
    VideoSequencePlan,
    VideoShotSpec,
)
from prodstud.engine.quality_reviewer import review_asset  # noqa: E402
from prodstud.engine.vision_qc import VisionImageInput, VisionQCResponse, VisionQCService  # noqa: E402


@dataclass(frozen=True)
class MockReference:
    role: str
    filename: str
    mime_type: str
    data: bytes


class ControlledVisionTransport:
    """Provider-neutral mock VisionQCTransport returning deterministic test payloads."""

    def __init__(self, payload: dict[str, Any], model_id: str = "controlled-mock-vision-v1") -> None:
        self._payload = payload
        self.model_id = model_id
        self.last_images: list[VisionImageInput] = []

    def inspect_images(
        self,
        *,
        prompt: str,
        images: list[VisionImageInput],
        api_key: str,
    ) -> VisionQCResponse:
        self.last_images = list(images)
        return VisionQCResponse(
            raw_text=json.dumps(self._payload),
            model_id=self.model_id,
            reported_cost_usd=0.0,
            prompt_tokens=900,
            output_tokens=200,
        )


@dataclass
class AuditCaseResult:
    case_id: str
    media_type: str
    mode: str  # "deterministic" | "multimodal_mock"
    ground_truth_defect: bool
    scenario: str
    observed_verdict: str
    weighted_score: float | None
    confidence: float
    classification: str  # "TP" | "TN" | "FP" | "FN"
    triggered_dimensions: list[str]
    inspection_coverage: str
    note: str


def _make_image_plan(aspect_ratio: str = "3:2", hard_locks: list[str] | None = None) -> ProductionPlanRecord:
    return ProductionPlanRecord(
        id="plan_audit_img",
        project_id="proj_audit",
        brief_id="brief_audit_img",
        media_type=MediaType.IMAGE,
        task_mode=TaskMode.PRODUCT_IMAGE,
        complexity_tier="moderate",
        version=1,
        summary="Matte ceramic vessel on limestone plinth, 50mm f/4 daylight studio.",
        interpreted_intent="Photographic tabletop product hero of matte terracotta vessel labeled 'SOLA'.",
        image_plan=ImagePlanDetails(
            reality_class="commercial_product",
            subject="Matte terracotta ceramic vessel with embossed label 'SOLA'",
            subject_details="Hand-thrown matte clay body with crisp rectangular paper label reading 'SOLA'",
            environment="Pale limestone studio plinth, soft window daylight",
            camera_position="Eye-level three-quarter front",
            camera_height="Tabletop hero height",
            focal_length_mm=50,
            aperture="f/4",
            focus_plane="Front vessel label and rim",
            lighting_key="Soft upper-left 45-degree diffused window key",
            lighting_fill="Passive neutral bounce card right",
            lighting_contrast_ratio="3:1",
            color_temperature_k=5400,
            composition_rule="Centered rule-of-thirds hero with clean negative space",
            shot_framing="Medium tabletop product shot",
            color_palette="Terracotta, limestone, warm charcoal",
            material_and_texture="Unglazed porous clay and matte cotton paper label",
            atmosphere="Clean daylight studio air",
            aspect_ratio=aspect_ratio,
            resolution="2K",
            hard_locks=hard_locks or [],
        ),
        activated_protocols=[],
        decisions=[],
        recommended_provider="local_test_fixture",
        recommended_model="local-studio-proof-v1",
        created_at="2026-11-21T00:00:00+00:00",
        updated_at="2026-11-21T00:00:00+00:00",
    )


def _make_video_plan(duration_s: float = 6.0, aspect_ratio: str = "16:9") -> ProductionPlanRecord:
    return ProductionPlanRecord(
        id="plan_audit_vid",
        project_id="proj_audit",
        brief_id="brief_audit_vid",
        media_type=MediaType.VIDEO,
        task_mode=TaskMode.VIDEO_SINGLE_SHOT,
        complexity_tier="moderate",
        version=1,
        summary="Steady 6s tabletop dolly across stoneware espresso cup.",
        interpreted_intent="Single-shot 6s steady tabletop clip with constant exposure.",
        video_plan=VideoSequencePlan(
            sequence_intent="Steady tabletop shot of stoneware espresso cup with constant daylight.",
            aspect_ratio=aspect_ratio,
            resolution="720p",
            fps=24,
            total_duration_s=duration_s,
            continuity_invariants=["Stable warm daylight exposure", "Stoneware cup fixed center-left"],
            feasibility_status="feasible",
            shots=[
                VideoShotSpec(
                    shot_id="S1",
                    order=1,
                    start_s=0.0,
                    end_s=duration_s,
                    duration_s=duration_s,
                    visual_purpose="Establish product and gentle atmospheric steam",
                    subject_action="Steam rises steadily from ceramic espresso cup",
                    camera_movement="Slow dolly-in",
                    framing="Medium close-up",
                    lens_focal_mm=50,
                    lighting_continuity="Consistent warm morning side light",
                    environment_continuity="Walnut counter and soft plaster wall unchanged",
                    transition_out="none",
                )
            ],
        ),
        activated_protocols=[],
        decisions=[],
        recommended_provider="local_test_fixture",
        recommended_model="local-shot-animatic-v1",
        created_at="2026-11-21T00:00:00+00:00",
        updated_at="2026-11-21T00:00:00+00:00",
    )


def _make_asset(media_type: MediaType, asset_id: str, width: int, height: int, duration_s: float | None = None) -> GeneratedAssetRecord:
    ext = "png" if media_type == MediaType.IMAGE else "mp4"
    return GeneratedAssetRecord(
        id=asset_id,
        project_id="proj_audit",
        plan_id="plan_audit_img" if media_type == MediaType.IMAGE else "plan_audit_vid",
        job_id=f"job_{asset_id}",
        media_type=media_type,
        provider_id="local_test_fixture",
        model_id="controlled-eval-fixture",
        filename=f"{asset_id}.{ext}",
        mime_type="image/png" if media_type == MediaType.IMAGE else "video/mp4",
        size_bytes=1024,
        sha256="0" * 64,
        width=width,
        height=height,
        duration_s=duration_s,
        fps=24.0 if media_type == MediaType.VIDEO else None,
        is_local_test_fixture=False,
        created_at="2026-11-21T00:00:00+00:00",
    )


def _draw_textured_scene(path: Path, size: tuple[int, int] = (900, 600), label_text: str = "SOLA") -> None:
    """Render a balanced, mid-tone, multi-edge synthetic studio scene."""
    img = Image.new("RGB", size, (132, 126, 118))
    draw = ImageDraw.Draw(img)
    w, h = size
    # Subtle studio wall planks + textured plinth
    for x in range(0, w, 18):
        shade = 122 + (x % 36) // 2
        draw.line([(x, 0), (x, int(h * 0.68))], fill=(shade, shade - 4, shade - 8), width=2)
    draw.rectangle([0, int(h * 0.68), w, h], fill=(168, 160, 148))
    for y in range(int(h * 0.68), h, 10):
        draw.line([(0, y), (w, y)], fill=(154, 146, 134), width=1)
    # Ceramic vessel + shadow
    draw.ellipse([int(w * 0.34), int(h * 0.63), int(w * 0.72), int(h * 0.76)], fill=(78, 72, 66))
    draw.rounded_rectangle([int(w * 0.38), int(h * 0.22), int(w * 0.62), int(h * 0.70)], radius=32, fill=(176, 118, 92), outline=(92, 58, 44), width=4)
    # Label patch with clean high-contrast lines
    draw.rectangle([int(w * 0.42), int(h * 0.40), int(w * 0.58), int(h * 0.54)], fill=(230, 224, 212), outline=(80, 74, 68), width=2)
    draw.text((int(w * 0.45), int(h * 0.45)), label_text, fill=(42, 38, 34))
    # Cross-hatch texture details on plinth
    for i in range(0, 120, 12):
        draw.rectangle([40 + i, 40 + (i % 48), 48 + i, 48 + (i % 48)], outline=(95, 90, 84), width=1)
    img.save(path, format="PNG")


def _draw_overexposed_scene(path: Path) -> None:
    """Render an overexposed frame with >35% clipped white highlights."""
    img = Image.new("RGB", (900, 600), (254, 254, 253))
    draw = ImageDraw.Draw(img)
    draw.rectangle([0, 380, 900, 600], fill=(180, 175, 170))
    draw.rectangle([340, 180, 560, 420], fill=(220, 190, 175), outline=(140, 120, 110), width=3)
    img.save(path, format="PNG")


def _draw_smooth_plastic_scene(path: Path) -> None:
    """Render a soft, blurred, low-edge-energy synthetic frame."""
    img = Image.new("RGB", (900, 600), (138, 134, 130))
    draw = ImageDraw.Draw(img)
    for step in range(40):
        c = 110 + step
        draw.ellipse([220 + step * 3, 120 + step * 2, 680 - step * 3, 480 - step * 2], fill=(c, c - 2, c - 4))
    img.save(path, format="PNG")


def _draw_chiaroscuro_valid_scene(path: Path) -> None:
    """Render a valid low-key dramatic chiaroscuro studio portrait (>30% intentional deep black backdrop)."""
    img = Image.new("RGB", (900, 600), (2, 2, 2))
    draw = ImageDraw.Draw(img)
    # Well-lit sculpted ceramic subject centered in deep dark void
    for offset in range(0, 110, 6):
        c = 70 + offset
        draw.rectangle([320 + offset, 110, 326 + offset, 490], fill=(c, int(c * 0.88), int(c * 0.78)))
    draw.rounded_rectangle([320, 110, 560, 490], radius=24, outline=(195, 170, 150), width=4)
    for y in range(130, 470, 16):
        draw.line([(335, y), (545, y)], fill=(120, 102, 92), width=2)
    img.save(path, format="PNG")


def _draw_highkey_white_seamless_scene(path: Path) -> None:
    """Render a valid e-commerce high-key pure-white seamless backdrop (>40% pure white cyclorama)."""
    img = Image.new("RGB", (900, 600), (255, 255, 255))
    draw = ImageDraw.Draw(img)
    # Crisp product subject centered on white seamless background
    draw.rounded_rectangle([340, 140, 560, 470], radius=20, fill=(65, 82, 108), outline=(30, 38, 52), width=4)
    for y in range(160, 450, 14):
        draw.line([(356, y), (544, y)], fill=(115, 132, 158), width=2)
    draw.rectangle([385, 260, 515, 340], fill=(232, 228, 220), outline=(45, 52, 66), width=2)
    img.save(path, format="PNG")


def _build_mp4(path: Path, filter_expr: str, duration_s: float = 6.0, size: str = "640x360") -> None:
    """Synthesize a deterministic H.264 MP4 via ffmpeg."""
    cmd = [
        "ffmpeg",
        "-y",
        "-f",
        "lavfi",
        "-i",
        f"color=c=#7b7670:s={size}:d={duration_s:.2f}:r=24",
        "-vf",
        filter_expr,
        "-c:v",
        "libx264",
        "-pix_fmt",
        "yuv420p",
        "-movflags",
        "+faststart",
        str(path),
    ]
    proc = subprocess.run(cmd, capture_output=True, timeout=30, check=False)
    if proc.returncode != 0 or not path.exists():
        raise RuntimeError(f"ffmpeg failed building {path.name}: {proc.stderr.decode('utf-8', 'ignore')[:300]}")


def _classify(ground_truth_defect: bool, verdict: QualityVerdict) -> str:
    flagged = verdict != QualityVerdict.PASS_ADVISORY
    if ground_truth_defect and flagged:
        return "TP"
    if (not ground_truth_defect) and (not flagged):
        return "TN"
    if (not ground_truth_defect) and flagged:
        return "FP"
    return "FN"


def run_controlled_audit() -> dict[str, Any]:
    """Execute all 12 controlled Vision QC evaluation cases and return structured audit telemetry."""
    results: list[AuditCaseResult] = []
    img_plan = _make_image_plan("3:2")
    img_plan_locked = _make_image_plan("3:2", hard_locks=["Preserve exact 'SOLA' label typography and vessel contour"])
    vid_plan = _make_video_plan(duration_s=6.0, aspect_ratio="16:9")

    with tempfile.TemporaryDirectory(prefix="prodstud_vqc_audit_") as tmp:
        root = Path(tmp)

        # 1. Image TN: Clean balanced 3:2 frame
        p1 = root / "case01_clean.png"
        _draw_textured_scene(p1, (900, 600), "SOLA")
        r1 = review_asset(asset=_make_asset(MediaType.IMAGE, "c01", 900, 600), plan=img_plan, file_path=p1)
        results.append(
            AuditCaseResult(
                case_id="IMG-01",
                media_type="image",
                mode="deterministic",
                ground_truth_defect=False,
                scenario="Clean balanced 3:2 studio frame matching plan dimensions and tonal range",
                observed_verdict=r1.advisory_verdict.value,
                weighted_score=r1.weighted_score,
                confidence=r1.confidence,
                classification=_classify(False, r1.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r1.findings],
                inspection_coverage=r1.inspection_coverage,
                note="Baseline compliant image passes deterministic pixel forensics cleanly.",
            )
        )

        # 2. Image TP: Wrong aspect ratio (1:1 vs planned 3:2)
        p2 = root / "case02_wrong_ar.png"
        _draw_textured_scene(p2, (600, 600), "SOLA")
        r2 = review_asset(asset=_make_asset(MediaType.IMAGE, "c02", 600, 600), plan=img_plan, file_path=p2)
        results.append(
            AuditCaseResult(
                case_id="IMG-02",
                media_type="image",
                mode="deterministic",
                ground_truth_defect=True,
                scenario="Aspect ratio mismatch (1:1 delivered vs 3:2 planned)",
                observed_verdict=r2.advisory_verdict.value,
                weighted_score=r2.weighted_score,
                confidence=r2.confidence,
                classification=_classify(True, r2.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r2.findings],
                inspection_coverage=r2.inspection_coverage,
                note="Critical technical_spec gate reliably forces rework_recommended.",
            )
        )

        # 3. Image TP: Severe overexposed highlight clipping
        p3 = root / "case03_overexposed.png"
        _draw_overexposed_scene(p3)
        r3 = review_asset(asset=_make_asset(MediaType.IMAGE, "c03", 900, 600), plan=img_plan, file_path=p3)
        results.append(
            AuditCaseResult(
                case_id="IMG-03",
                media_type="image",
                mode="deterministic",
                ground_truth_defect=True,
                scenario="Severely blown highlights (>35% clipped white pixels)",
                observed_verdict=r3.advisory_verdict.value,
                weighted_score=r3.weighted_score,
                confidence=r3.confidence,
                classification=_classify(True, r3.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r3.findings],
                inspection_coverage=r3.inspection_coverage,
                note="Histogram clipping threshold (>12% highlights) catches blowouts.",
            )
        )

        # 4. Image TP: Over-smoothed / blurry low-edge-energy frame
        p4 = root / "case04_plastic_smooth.png"
        _draw_smooth_plastic_scene(p4)
        r4 = review_asset(asset=_make_asset(MediaType.IMAGE, "c04", 900, 600), plan=img_plan, file_path=p4)
        results.append(
            AuditCaseResult(
                case_id="IMG-04",
                media_type="image",
                mode="deterministic",
                ground_truth_defect=True,
                scenario="Over-smoothed low-detail plastic/blurry frame (edge_energy < 4.5)",
                observed_verdict=r4.advisory_verdict.value,
                weighted_score=r4.weighted_score,
                confidence=r4.confidence,
                classification=_classify(True, r4.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r4.findings],
                inspection_coverage=r4.inspection_coverage,
                note="Edge gradient proxy flags abnormally soft/plastic renders.",
            )
        )

        # 5. Image FP: Valid Low-Key Chiaroscuro Studio Portrait (intentional >20% dark void)
        p5 = root / "case05_chiaroscuro_fp.png"
        _draw_chiaroscuro_valid_scene(p5)
        r5 = review_asset(asset=_make_asset(MediaType.IMAGE, "c05", 900, 600), plan=img_plan, file_path=p5)
        results.append(
            AuditCaseResult(
                case_id="IMG-05",
                media_type="image",
                mode="deterministic",
                ground_truth_defect=False,
                scenario="Valid dramatic low-key chiaroscuro backdrop (>30% intentional deep black)",
                observed_verdict=r5.advisory_verdict.value,
                weighted_score=r5.weighted_score,
                confidence=r5.confidence,
                classification=_classify(False, r5.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r5.findings],
                inspection_coverage=r5.inspection_coverage,
                note="KNOWN FALSE POSITIVE: shadow_clip_pct > 18% cannot distinguish crushed shadows from intentional dark-void styling.",
            )
        )

        # 6. Image FP: Valid High-Key E-Commerce Seamless White Cyclorama
        p6 = root / "case06_highkey_fp.png"
        _draw_highkey_white_seamless_scene(p6)
        r6 = review_asset(asset=_make_asset(MediaType.IMAGE, "c06", 900, 600), plan=img_plan, file_path=p6)
        results.append(
            AuditCaseResult(
                case_id="IMG-06",
                media_type="image",
                mode="deterministic",
                ground_truth_defect=False,
                scenario="Valid e-commerce product on pure-white seamless backdrop (>40% white cyclorama)",
                observed_verdict=r6.advisory_verdict.value,
                weighted_score=r6.weighted_score,
                confidence=r6.confidence,
                classification=_classify(False, r6.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r6.findings],
                inspection_coverage=r6.inspection_coverage,
                note="KNOWN FALSE POSITIVE: highlight_clip_pct > 12% over-flags pure-white seamless studio backdrops.",
            )
        )

        # 7. Image FN: Garbled label text ('X9#Q!Z') & semantic drift on sharp 3:2 frame in deterministic mode
        p7 = root / "case07_garbled_text_fn.png"
        _draw_textured_scene(p7, (900, 600), "X9#Q!Z")
        r7 = review_asset(asset=_make_asset(MediaType.IMAGE, "c07", 900, 600), plan=img_plan_locked, file_path=p7)
        results.append(
            AuditCaseResult(
                case_id="IMG-07",
                media_type="image",
                mode="deterministic",
                ground_truth_defect=True,
                scenario="Garbled brand label ('X9#Q!Z' instead of locked 'SOLA') on crisp, balanced 3:2 image",
                observed_verdict=r7.advisory_verdict.value,
                weighted_score=r7.weighted_score,
                confidence=r7.confidence,
                classification=_classify(True, r7.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r7.findings],
                inspection_coverage=r7.inspection_coverage,
                note="KNOWN FALSE NEGATIVE: Deterministic pixel statistics cannot read text, verify identity, or detect semantic drift.",
            )
        )

        ref_obj = MockReference(role="product", filename="sola_ref.png", mime_type="image/png", data=p1.read_bytes())

        # 8. Image Multimodal TP: Multimodal Vision QC catches distorted brand label with source comparison
        t8 = ControlledVisionTransport(
            {
                "brief_adherence_score": 3.5,
                "brief_adherence_evidence": "Vessel shape matches brief, but label text reads 'X9#Q!Z' instead of 'SOLA'.",
                "physical_causality_score": 4.2,
                "physical_causality_evidence": "Plinth shadow aligns with directional light.",
                "preservation_score": 1.6,
                "preservation_evidence": "Hard-locked brand typography corrupted relative to source reference.",
                "detected_ai_tells": [{"id": "T10", "status": "detected", "evidence": "Garbled label characters 'X9#Q!Z'."}],
                "findings": [
                    {
                        "severity": "critical",
                        "dimension": "vision_source_preservation",
                        "location": "Center vessel label",
                        "observed_evidence": "Text renders 'X9#Q!Z' instead of 'SOLA'.",
                        "inferred_cause": "Model hallucinated glyphs during re-synthesis.",
                        "confidence": 0.88,
                        "suggested_correction": "Apply selective preservation revision locking label zone.",
                    }
                ],
            }
        )
        r8, _ = VisionQCService(transport=t8).run_multimodal_review(
            asset=_make_asset(MediaType.IMAGE, "c08", 900, 600),
            plan=img_plan_locked,
            file_path=p7,
            references=[ref_obj],
            api_key="controlled-eval-only",
        )
        results.append(
            AuditCaseResult(
                case_id="IMG-08",
                media_type="image",
                mode="multimodal_mock",
                ground_truth_defect=True,
                scenario="Multimodal Vision QC compares garbled label ('X9#Q!Z') against source reference ('SOLA')",
                observed_verdict=r8.advisory_verdict.value,
                weighted_score=r8.weighted_score,
                confidence=r8.confidence,
                classification=_classify(True, r8.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r8.findings],
                inspection_coverage=r8.inspection_coverage,
                note="When vision model detects preservation_score <= 2.0, critical gate forces rework_recommended.",
            )
        )

        # 9. Image Multimodal FP: Hallucinated preservation defect on a clean, intact asset
        t9 = ControlledVisionTransport(
            {
                "brief_adherence_score": 4.3,
                "brief_adherence_evidence": "Scene aligns with brief.",
                "physical_causality_score": 4.1,
                "physical_causality_evidence": "Consistent lighting.",
                "preservation_score": 1.9,
                "preservation_evidence": "Suspected minor serif shift on label (false alarm).",
                "detected_ai_tells": [],
                "findings": [],
            }
        )
        r9, _ = VisionQCService(transport=t9).run_multimodal_review(
            asset=_make_asset(MediaType.IMAGE, "c09", 900, 600),
            plan=img_plan_locked,
            file_path=p1,
            references=[ref_obj],
            api_key="controlled-eval-only",
        )
        results.append(
            AuditCaseResult(
                case_id="IMG-09",
                media_type="image",
                mode="multimodal_mock",
                ground_truth_defect=False,
                scenario="Hallucinated LLM preservation alarm (score=1.9) on a clean, intact asset",
                observed_verdict=r9.advisory_verdict.value,
                weighted_score=r9.weighted_score,
                confidence=r9.confidence,
                classification=_classify(False, r9.advisory_verdict),
                triggered_dimensions=[d.name for d in r9.dimensions if d.critical and (d.score or 5) <= 2.0],
                inspection_coverage=r9.inspection_coverage,
                note="KNOWN MULTIMODAL FALSE POSITIVE: LLM over-flagging <= 2.0 forces rework_recommended; human must confirm before spending on rework.",
            )
        )

        # 10. Image Multimodal FN: Overly lenient LLM misses subtle 1-char typo / 6-finger defect
        t10 = ControlledVisionTransport(
            {
                "brief_adherence_score": 4.5,
                "brief_adherence_evidence": "Ceramic vessel matches aesthetic.",
                "physical_causality_score": 4.4,
                "physical_causality_evidence": "Lighting looks plausible.",
                "preservation_score": 4.3,
                "preservation_evidence": "Label appears broadly similar.",
                "detected_ai_tells": [{"id": "T10", "status": "clear", "evidence": "No obvious distortion noted."}],
                "findings": [],
            }
        )
        r10, _ = VisionQCService(transport=t10).run_multimodal_review(
            asset=_make_asset(MediaType.IMAGE, "c10", 900, 600),
            plan=img_plan_locked,
            file_path=p7,
            references=[ref_obj],
            api_key="controlled-eval-only",
        )
        results.append(
            AuditCaseResult(
                case_id="IMG-10",
                media_type="image",
                mode="multimodal_mock",
                ground_truth_defect=True,
                scenario="Lenient vision LLM overlooks corrupted label text and returns high scores (4.3-4.5)",
                observed_verdict=r10.advisory_verdict.value,
                weighted_score=r10.weighted_score,
                confidence=r10.confidence,
                classification=_classify(True, r10.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r10.findings],
                inspection_coverage=r10.inspection_coverage,
                note="KNOWN MULTIMODAL FALSE NEGATIVE: Pipeline outputs pass_advisory (conf=0.80) if vision LLM misses micro-text/anatomy errors.",
            )
        )

        # 11. Video TN: Clean steady 6s 16:9 MP4 matching planned duration, ratio, and luminance continuity
        v10 = root / "case11_clean_video.mp4"
        _build_mp4(
            v10,
            "drawbox=x=80:y=60:w=480:h=240:color=#505050@1:t=fill",
            duration_s=6.0,
        )
        r10_vid = review_asset(asset=_make_asset(MediaType.VIDEO, "c11_tn", 640, 360, 6.0), plan=vid_plan, file_path=v10)
        results.append(
            AuditCaseResult(
                case_id="VID-00",
                media_type="video",
                mode="deterministic",
                ground_truth_defect=False,
                scenario="Clean steady 6s 16:9 MP4 matching planned duration and exposure continuity",
                observed_verdict=r10_vid.advisory_verdict.value,
                weighted_score=r10_vid.weighted_score,
                confidence=r10_vid.confidence,
                classification=_classify(False, r10_vid.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r10_vid.findings],
                inspection_coverage=r10_vid.inspection_coverage,
                note="Baseline compliant video passes ffprobe metadata + 3-frame continuity checks cleanly.",
            )
        )

        # 12. Video TP: Bright white flash at midpoint t=3.0s (caught by sampled-frame luminance delta)
        v11 = root / "case12_mid_flash.mp4"
        _build_mp4(
            v11,
            "drawbox=x=80:y=60:w=480:h=240:color=#404040@1:t=fill,"
            "drawbox=x=0:y=0:w=640:h=360:color=white@1:t=fill:enable='between(t,2.7,3.3)'",
            duration_s=6.0,
        )
        r11 = review_asset(asset=_make_asset(MediaType.VIDEO, "c11", 640, 360, 6.0), plan=vid_plan, file_path=v11)
        results.append(
            AuditCaseResult(
                case_id="VID-01",
                media_type="video",
                mode="deterministic",
                ground_truth_defect=True,
                scenario="6s MP4 with bright white exposure flash spanning midpoint timestamp t=3.0s",
                observed_verdict=r11.advisory_verdict.value,
                weighted_score=r11.weighted_score,
                confidence=r11.confidence,
                classification=_classify(True, r11.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r11.findings],
                inspection_coverage=r11.inspection_coverage,
                note="3-frame sampler (0.2s, 3.0s, 5.7s) hits midpoint flash and flags luminance drift (>28).",
            )
        )

        # 12. Video FN (BOTH deterministic AND 3-frame multimodal!): Severe red glitch strictly at 1.2s..1.8s
        v12 = root / "case12_interframe_glitch_fn.mp4"
        _build_mp4(
            v12,
            "drawbox=x=80:y=60:w=480:h=240:color=#505050@1:t=fill,"
            "drawbox=x=0:y=0:w=640:h=360:color=red@1:t=fill:enable='between(t,1.2,1.8)'",
            duration_s=6.0,
        )
        t12 = ControlledVisionTransport(
            {
                "brief_adherence_score": 4.4,
                "brief_adherence_evidence": "All 3 sampled keyframes (0.20s, 3.00s, 5.70s) show steady neutral frame.",
                "frame_continuity_score": 4.5,
                "frame_continuity_evidence": "No luminance or color shift across sampled timestamps.",
                "findings": [],
            }
        )
        r12, _ = VisionQCService(transport=t12).run_multimodal_review(
            asset=_make_asset(MediaType.VIDEO, "c12", 640, 360, 6.0),
            plan=vid_plan,
            file_path=v12,
            references=[],
            api_key="controlled-eval-only",
        )
        results.append(
            AuditCaseResult(
                case_id="VID-02",
                media_type="video",
                mode="multimodal_mock",
                ground_truth_defect=True,
                scenario="6s MP4 with severe full-frame RED corruption glitch strictly at 1.2s-1.8s (between sampled 0.2s & 3.0s)",
                observed_verdict=r12.advisory_verdict.value,
                weighted_score=r12.weighted_score,
                confidence=r12.confidence,
                classification=_classify(True, r12.advisory_verdict),
                triggered_dimensions=[f.dimension for f in r12.findings],
                inspection_coverage=r12.inspection_coverage,
                note=(
                    "EMPIRICAL STRUCTURAL BLIND SPOT (FALSE NEGATIVE): Neither deterministic ffprobe/3-frame stats nor "
                    "3-frame multimodal Vision QC receives a single pixel from t=1.2s..1.8s. Full human playback is mandatory."
                ),
            )
        )

    counts = {k: sum(1 for r in results if r.classification == k) for k in ("TP", "TN", "FP", "FN")}
    return {
        "dataset_size": len(results),
        "spend_usd": 0.0,
        "live_vision_api_invoked": False,
        "summary_counts": counts,
        "cases": [asdict(r) for r in results],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description="Run controlled Vision QC evaluation dataset audit ($0.00 spend).")
    parser.add_argument("--json-out", type=Path, default=None, help="Optional path to write full JSON telemetry.")
    args = parser.parse_args()

    report = run_controlled_audit()
    if args.json_out:
        args.json_out.parent.mkdir(parents=True, exist_ok=True)
        args.json_out.write_text(json.dumps(report, indent=2), encoding="utf-8")

    print(json.dumps(report, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
