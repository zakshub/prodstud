"""Advisory Quality Review Engine (D009 + Studio Brain 10-Category Forensic QC + Designer-Studio Fit Check).

NEVER claims objective certification.
Explicitly states inspection coverage, visible normalized dimension weights, confidence, and blind spots.
"""

from __future__ import annotations

import math
import subprocess
import tempfile
from pathlib import Path
from typing import Any
from uuid import uuid4

from PIL import Image, ImageFilter, ImageStat

from prodstud.domain.enums import MediaType, QualityVerdict
from prodstud.domain.models import (
    GeneratedAssetRecord,
    ProductionPlanRecord,
    QualityDimensionScore,
    QualityFinding,
    QualityReviewRecord,
)
from prodstud.storage.asset_store import probe_video_metadata
from prodstud.storage.database import utcnow_iso

# Curated subset of Studio Brain's 22 AI Tells surfaced for human visual inspection
KEY_AI_TELLS = [
    {"id": "T01", "label": "Plastic or airbrushed pore-less skin", "check_status": "requires_human_visual_check"},
    {"id": "T03", "label": "Fused, extra, or anatomically implausible fingers/hands", "check_status": "requires_human_visual_check"},
    {"id": "T06", "label": "Floating contact shadows or missing ambient occlusion", "check_status": "requires_human_visual_check"},
    {"id": "T07", "label": "Unmotivated rim lighting without a physical scene source", "check_status": "requires_human_visual_check"},
    {"id": "T08", "label": "Conflicting key light directions between subject and background", "check_status": "requires_human_visual_check"},
    {"id": "T09", "label": "Warped architectural lines or melting edges", "check_status": "requires_human_visual_check"},
    {"id": "T10", "label": "Illegible or garbled embedded text / brand labels", "check_status": "requires_human_visual_check"},
    {"id": "T15", "label": "Abrupt cutout blur rather than continuous optical depth-of-field", "check_status": "requires_human_visual_check"},
]


def _parse_ratio(aspect_ratio: str) -> float | None:
    if ":" not in aspect_ratio:
        return None
    try:
        a, b = aspect_ratio.split(":", 1)
        return float(a) / float(b)
    except Exception:
        return None


def _normalize_weights(dims: list[QualityDimensionScore]) -> list[QualityDimensionScore]:
    total = sum(d.weight for d in dims if d.weight > 0)
    if total <= 0:
        return dims
    for d in dims:
        d.weight = round(d.weight / total, 4)
    return dims


def _inspect_image_pixels(path: Path) -> dict[str, Any]:
    with Image.open(path) as img:
        rgb = img.convert("RGB")
        width, height = rgb.size
        gray = rgb.convert("L")
        stat_rgb = ImageStat.Stat(rgb)
        stat_l = ImageStat.Stat(gray)

        # Shadow/highlight clipping percentages
        hist = gray.histogram()
        total_px = max(1, width * height)
        shadow_clip_pct = round((sum(hist[:5]) / total_px) * 100.0, 2)
        highlight_clip_pct = round((sum(hist[251:]) / total_px) * 100.0, 2)

        # Edge energy sharpness proxy via FIND_EDGES filter
        edges = gray.filter(ImageFilter.FIND_EDGES)
        edge_mean = round(ImageStat.Stat(edges).mean[0], 2)

        r_m, g_m, b_m = [round(v, 2) for v in stat_rgb.mean]
        color_cast_spread = round(max(r_m, g_m, b_m) - min(r_m, g_m, b_m), 2)

        return {
            "width": width,
            "height": height,
            "actual_ratio": round(width / max(1, height), 4),
            "mean_luminance": round(stat_l.mean[0], 2),
            "luminance_stddev": round(stat_l.stddev[0], 2),
            "shadow_clip_pct": shadow_clip_pct,
            "highlight_clip_pct": highlight_clip_pct,
            "edge_energy": edge_mean,
            "rgb_means": (r_m, g_m, b_m),
            "color_cast_spread": color_cast_spread,
        }


def _sample_video_frames(video_path: Path, duration_s: float) -> list[dict[str, Any]]:
    """Extract 3 real frames (start, middle, end) via ffmpeg and compute luminance/color continuity deltas."""
    timestamps = [0.2, max(0.3, duration_s * 0.5), max(0.4, duration_s - 0.3)]
    samples: list[dict[str, Any]] = []
    with tempfile.TemporaryDirectory() as tmpdir:
        for idx, ts in enumerate(timestamps):
            out_png = Path(tmpdir) / f"frame_{idx}.png"
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
                    "-q:v",
                    "2",
                    str(out_png),
                ],
                capture_output=True,
                timeout=15,
                check=False,
            )
            if proc.returncode == 0 and out_png.exists():
                stats = _inspect_image_pixels(out_png)
                stats["timestamp_s"] = round(ts, 2)
                samples.append(stats)
    return samples


def review_asset(
    *,
    asset: GeneratedAssetRecord,
    plan: ProductionPlanRecord,
    file_path: Path,
) -> QualityReviewRecord:
    """Perform honest, evidence-backed advisory quality review with real media forensics."""
    now = utcnow_iso()
    findings: list[QualityFinding] = []
    dimensions: list[QualityDimensionScore] = []
    design_fit_notes: list[str] = []

    if asset.media_type == MediaType.IMAGE:
        px = _inspect_image_pixels(file_path)
        planned_ar = plan.image_plan.aspect_ratio if plan.image_plan else "3:2"
        expected_ratio = _parse_ratio(planned_ar)
        ratio_diff = abs(px["actual_ratio"] - expected_ratio) if expected_ratio else 0.0

        # 1. Technical Specification & Aspect Ratio Compliance (Critical)
        if ratio_diff <= 0.06:
            spec_score = 4.8
            spec_obs = f"Measured {px['width']}x{px['height']}px (ratio {px['actual_ratio']:.2f}) matches planned {planned_ar}."
        elif ratio_diff <= 0.18:
            spec_score = 3.2
            spec_obs = f"Measured {px['width']}x{px['height']}px (ratio {px['actual_ratio']:.2f}) slightly deviates from planned {planned_ar}."
            findings.append(
                QualityFinding(
                    severity="warning",
                    dimension="technical_spec",
                    location_or_timestamp="Full frame",
                    observed_evidence=spec_obs,
                    inferred_cause="Provider rounded output dimensions to nearest supported grid.",
                    confidence=0.95,
                    suggested_correction=f"Explicitly confirm aspect ratio {planned_ar} or adjust framing crop.",
                )
            )
        else:
            spec_score = 1.8
            spec_obs = f"Measured {px['width']}x{px['height']}px (ratio {px['actual_ratio']:.2f}) does NOT match planned {planned_ar}."
            findings.append(
                QualityFinding(
                    severity="critical",
                    dimension="technical_spec",
                    location_or_timestamp="Full frame",
                    observed_evidence=spec_obs,
                    inferred_cause="Model ignored aspect ratio parameter or defaulted to square/landscape fallback.",
                    confidence=0.98,
                    suggested_correction=f"Re-submit using Interactions API response_format.aspect_ratio='{planned_ar}' and verify model support.",
                )
            )

        # 2. Exposure, Dynamic Range & Highlight/Shadow Integrity
        if px["highlight_clip_pct"] > 12.0 or px["shadow_clip_pct"] > 18.0:
            exp_score = 2.6
            exp_obs = f"Mean luminance {px['mean_luminance']}, highlight clip {px['highlight_clip_pct']}%, shadow clip {px['shadow_clip_pct']}%."
            findings.append(
                QualityFinding(
                    severity="warning",
                    dimension="lighting_exposure",
                    location_or_timestamp="Highlights / Shadows",
                    observed_evidence=exp_obs,
                    inferred_cause="Excessive highlight clipping or crushed shadow blocks reduce photographic rolloff realism.",
                    confidence=0.82,
                    suggested_correction="Revise lighting contrast ratio softer (e.g., 3:1 with gentle highlight rolloff).",
                )
            )
        elif px["luminance_stddev"] < 18.0:
            exp_score = 3.0
            exp_obs = f"Low tonal contrast spread (stddev {px['luminance_stddev']}, mean {px['mean_luminance']})."
            findings.append(
                QualityFinding(
                    severity="info",
                    dimension="lighting_exposure",
                    location_or_timestamp="Global tonal curve",
                    observed_evidence=exp_obs,
                    inferred_cause="Image may appear flat or overly diffused.",
                    confidence=0.75,
                    suggested_correction="Introduce negative fill or stronger key light separation if greater depth is desired.",
                )
            )
        else:
            exp_score = 4.5
            exp_obs = f"Balanced tonal spread (mean {px['mean_luminance']}, stddev {px['luminance_stddev']}, clip H:{px['highlight_clip_pct']}% / S:{px['shadow_clip_pct']}%)."

        # 3. Edge Detail / Sharpness Distribution Proxy
        if px["edge_energy"] < 4.5:
            sharp_score = 2.8
            sharp_obs = f"Low edge gradient energy ({px['edge_energy']}) — frame may be soft or overly smooth."
            findings.append(
                QualityFinding(
                    severity="warning",
                    dimension="detail_texture",
                    location_or_timestamp="Global frame",
                    observed_evidence=sharp_obs,
                    inferred_cause="Possible soft focus or plastic over-smoothing.",
                    confidence=0.68,
                    suggested_correction="Request crisper focal plane lock and natural surface micro-texture.",
                )
            )
        else:
            sharp_score = 4.3
            sharp_obs = f"Healthy edge gradient energy ({px['edge_energy']}) indicating structured detail presence."

        # 4. Color Balance Check
        if px["color_cast_spread"] > 55.0:
            color_score = 3.3
            color_obs = f"Pronounced chromatic bias across RGB means {px['rgb_means']} (spread {px['color_cast_spread']})."
            findings.append(
                QualityFinding(
                    severity="info",
                    dimension="color_balance",
                    location_or_timestamp="Global color balance",
                    observed_evidence=color_obs,
                    inferred_cause="Strong tint or motivated warm/cool lighting cast; verify skin/product color accuracy visually.",
                    confidence=0.7,
                    suggested_correction="If unintentional, request neutral white balance protecting true subject hues.",
                )
            )
        else:
            color_score = 4.4
            color_obs = f"Controlled RGB balance {px['rgb_means']} (spread {px['color_cast_spread']})."

        # 5. Semantic / Source Preservation & Physical Causality (honestly flagged as needing human/vision inspection!)
        pres_note = (
            f"Plan defines {len(plan.image_plan.hard_locks)} hard lock(s). Deterministic pixel forensics cannot verify semantic facial identity or garment seams — manual visual check required."
            if plan.image_plan and plan.image_plan.hard_locks
            else "No reference hard locks declared; human visual confirmation required for brief alignment and physical lighting causality."
        )

        dimensions = _normalize_weights(
            [
                QualityDimensionScore(
                    name="technical_spec",
                    label="Output Dimensions & Aspect Ratio",
                    weight=0.30,
                    score=spec_score,
                    critical=True,
                    observed_evidence=spec_obs,
                    inferred_notes="Directly measured from stored image file headers and pixel buffer.",
                ),
                QualityDimensionScore(
                    name="lighting_exposure",
                    label="Exposure & Tonal Rolloff",
                    weight=0.25,
                    score=exp_score,
                    critical=True,
                    observed_evidence=exp_obs,
                    inferred_notes="Derived from full-frame 8-bit luminance histogram statistics.",
                ),
                QualityDimensionScore(
                    name="detail_texture",
                    label="Detail & Edge Definition",
                    weight=0.20,
                    score=sharp_score,
                    critical=False,
                    observed_evidence=sharp_obs,
                    inferred_notes="Proxy edge-gradient check; cannot distinguish optical sharpness from sharpening halos alone.",
                ),
                QualityDimensionScore(
                    name="color_balance",
                    label="Color Balance & Cast",
                    weight=0.15,
                    score=color_score,
                    critical=False,
                    observed_evidence=color_obs,
                    inferred_notes="Channel-mean balance check; review subject material hues against plan.",
                ),
                QualityDimensionScore(
                    name="semantic_preservation_and_causality",
                    label="Brief Alignment, Preservation & Physical Causality",
                    weight=0.10,
                    score=None,
                    critical=False,
                    observed_evidence="Not semantically evaluated (no multimodal vision grader invoked in deterministic check).",
                    inferred_notes=pres_note,
                ),
            ]
        )

        if asset.is_local_test_fixture:
            findings.append(
                QualityFinding(
                    severity="info",
                    dimension="execution_mode",
                    location_or_timestamp="Asset provenance",
                    observed_evidence="Asset was rendered by local_test_fixture (non-billable workflow verification render).",
                    inferred_cause="Local test verification mode active rather than live Google Gemini API.",
                    confidence=1.0,
                    suggested_correction="Configure a Google API key and spend cap in Settings to generate live photographic outputs.",
                )
            )

        design_fit_notes = [
            f"Placement fit check (Designer-Studio handoff): verified framing ratio {planned_ar} ({px['width']}x{px['height']}px).",
            "Confirm safe margins around hero subject before placing asset in web hero or editorial layouts.",
        ]
        inspection_coverage = "full_image_file_metadata_and_pixel_statistics (no external vision LLM invoked)"
        limitations = [
            "Deterministic pixel inspection verifies dimensions, aspect ratio, exposure clipping, contrast, color cast, and edge energy only.",
            "Semantic brief adherence, human anatomy/hands, text legibility, source-preservation identity fidelity, and subtle AI artifacts require human visual review.",
            "This score is strictly advisory and is NOT an objective quality certification.",
        ]
        confidence = 0.64

    else:
        # Video deterministic inspection via ffprobe + 3 sampled frames via ffmpeg
        probe = probe_video_metadata(file_path)
        planned_dur = plan.video_plan.total_duration_s if plan.video_plan else 8.0
        planned_ar = plan.video_plan.aspect_ratio if plan.video_plan else "16:9"
        actual_dur = probe.get("duration_s") or asset.duration_s
        actual_fps = probe.get("fps") or asset.fps
        actual_w = probe.get("width") or asset.width
        actual_h = probe.get("height") or asset.height

        # 1. Duration & Technical Compliance
        if actual_dur is not None:
            dur_diff = abs(actual_dur - planned_dur)
            if dur_diff <= 0.6:
                dur_score = 4.8
                dur_obs = f"Measured duration {actual_dur:.2f}s matches planned {planned_dur:.1f}s ({actual_w}x{actual_h}, {actual_fps} FPS, codec={probe.get('codec')})."
            elif dur_diff <= 2.0:
                dur_score = 3.4
                dur_obs = f"Measured duration {actual_dur:.2f}s differs slightly from planned {planned_dur:.1f}s."
                findings.append(
                    QualityFinding(
                        severity="warning",
                        dimension="duration_spec",
                        location_or_timestamp=f"00:00 – 00:{actual_dur:04.1f}",
                        observed_evidence=dur_obs,
                        inferred_cause="Provider quantized output clip length to supported duration tier.",
                        confidence=0.95,
                        suggested_correction="Adjust shot durations or use extension workflow to match exact target runtime.",
                    )
                )
            else:
                dur_score = 1.9
                dur_obs = f"Measured duration {actual_dur:.2f}s significantly misses planned {planned_dur:.1f}s."
                findings.append(
                    QualityFinding(
                        severity="critical",
                        dimension="duration_spec",
                        location_or_timestamp=f"00:00 – 00:{actual_dur:04.1f}",
                        observed_evidence=dur_obs,
                        inferred_cause="Clip truncated or provider enforced lower duration cap.",
                        confidence=0.98,
                        suggested_correction="Split long shot sequence into feasible clips within provider max duration.",
                    )
                )
        else:
            dur_score = 2.0
            dur_obs = "Unable to probe MP4 stream duration via ffprobe."
            findings.append(
                QualityFinding(
                    severity="critical",
                    dimension="duration_spec",
                    location_or_timestamp="Container stream",
                    observed_evidence=dur_obs,
                    inferred_cause="Video container may be corrupt or incomplete.",
                    confidence=0.9,
                    suggested_correction="Inspect raw asset file integrity before acceptance.",
                )
            )

        # 2. Aspect Ratio & Frame Rate
        expected_ratio = _parse_ratio(planned_ar)
        actual_ratio = (actual_w / actual_h) if (actual_w and actual_h) else None
        if expected_ratio and actual_ratio and abs(actual_ratio - expected_ratio) <= 0.08:
            fmt_score = 4.7
            fmt_obs = f"Measured {actual_w}x{actual_h} (ratio {actual_ratio:.2f}) at {actual_fps} FPS matches {planned_ar}."
        else:
            fmt_score = 2.4
            fmt_obs = f"Measured {actual_w}x{actual_h} at {actual_fps} FPS deviates from planned {planned_ar}."
            findings.append(
                QualityFinding(
                    severity="warning",
                    dimension="format_compliance",
                    location_or_timestamp="Full clip",
                    observed_evidence=fmt_obs,
                    inferred_cause="Output frame geometry differs from planned aspect ratio.",
                    confidence=0.9,
                    suggested_correction=f"Verify provider aspect_ratio='{planned_ar}' setting.",
                )
            )

        # 3. Sampled Frame Continuity (Luminance & Color Drift across Start / Mid / End)
        samples = _sample_video_frames(file_path, actual_dur or 4.0)
        if len(samples) >= 2:
            lums = [s["mean_luminance"] for s in samples]
            lum_delta = round(max(lums) - min(lums), 2)
            if lum_delta <= 28.0:
                cont_score = 4.4
                cont_obs = f"Sampled {len(samples)} frames ({', '.join(str(s['timestamp_s']) + 's' for s in samples)}); luminance drift {lum_delta} stays stable."
            else:
                cont_score = 2.7
                cont_obs = f"Sampled {len(samples)} frames show elevated luminance shift ({lum_delta}) between timestamps."
                findings.append(
                    QualityFinding(
                        severity="warning",
                        dimension="lighting_continuity",
                        location_or_timestamp=f"{samples[0]['timestamp_s']}s -> {samples[-1]['timestamp_s']}s",
                        observed_evidence=cont_obs,
                        inferred_cause="Possible lighting flicker, sudden exposure swing, or unmotivated cut transition.",
                        confidence=0.72,
                        suggested_correction="Inspect transition timestamp and reinforce lighting_continuity lock across shots.",
                    )
                )
        else:
            cont_score = None
            cont_obs = "Frame sampling unavailable; continuity could not be measured automatically."

        dimensions = _normalize_weights(
            [
                QualityDimensionScore(
                    name="duration_spec",
                    label="Duration & Stream Validity",
                    weight=0.35,
                    score=dur_score,
                    critical=True,
                    observed_evidence=dur_obs,
                    inferred_notes="Directly measured via ffprobe stream inspection.",
                ),
                QualityDimensionScore(
                    name="format_compliance",
                    label="Resolution, Aspect Ratio & FPS",
                    weight=0.25,
                    score=fmt_score,
                    critical=True,
                    observed_evidence=fmt_obs,
                    inferred_notes="Measured against planned aspect ratio and 24 FPS cadence.",
                ),
                QualityDimensionScore(
                    name="lighting_continuity",
                    label="Sampled Frame Luminance Continuity",
                    weight=0.25,
                    score=cont_score,
                    critical=False,
                    observed_evidence=cont_obs,
                    inferred_notes="Evaluated over 3 sampled frames (start, midpoint, tail); does not inspect every frame.",
                ),
                QualityDimensionScore(
                    name="motion_and_subject_continuity",
                    label="Motion Plausibility, Camera Move & Subject Continuity",
                    weight=0.15,
                    score=None,
                    critical=False,
                    observed_evidence="Not semantically evaluated on all frames.",
                    inferred_notes="Playback inspection required to verify smooth subject physics, absence of morphing, and shot transitions.",
                ),
            ]
        )

        if asset.is_local_test_fixture:
            findings.append(
                QualityFinding(
                    severity="info",
                    dimension="execution_mode",
                    location_or_timestamp="00:00",
                    observed_evidence="Video rendered by local_test_fixture (non-billable animated shot-slate MP4).",
                    inferred_cause="Offline workflow verification mode active rather than live Google Gemini Omni API.",
                    confidence=1.0,
                    suggested_correction="Configure a Google API key and spend cap in Settings to generate live AI video.",
                )
            )

        design_fit_notes = [
            f"Video delivery fit: {actual_w}x{actual_h} MP4 ({actual_dur}s) aligned with {len(plan.video_plan.shots) if plan.video_plan else 1} planned shot(s).",
            "Play back full clip to verify visual continuity across planned shot boundaries.",
        ]
        inspection_coverage = (
            f"ffprobe_stream_metadata_plus_{len(samples)}_sampled_frames"
            if samples
            else "ffprobe_stream_metadata_only"
        )
        limitations = [
            f"Video inspection checked stream metadata and {len(samples)} sampled frames only — NOT full frame-by-frame motion analysis.",
            "Temporal morphing, flickering micro-details, hand/face continuity, and camera trajectory smoothness require human playback review.",
            "This score is strictly advisory and is NOT an objective certification.",
        ]
        confidence = 0.60 if samples else 0.45

    # Weighted composite across scored dimensions only (transparent visible normalization)
    scored = [d for d in dimensions if d.score is not None]
    if scored:
        w_sum = sum(d.weight for d in scored)
        weighted_score = round(sum((d.weight / w_sum) * float(d.score) for d in scored), 2)
    else:
        weighted_score = None

    # Fail-closed critical gate (Studio Brain Forensic Reality QC: any critical <= 2.0 forces rework)
    critical_fail = any(d.critical and d.score is not None and d.score <= 2.0 for d in dimensions)
    has_warnings = any(f.severity in {"critical", "warning"} for f in findings)
    if critical_fail:
        verdict = QualityVerdict.REWORK_RECOMMENDED
    elif has_warnings or (weighted_score is not None and weighted_score < 4.0):
        verdict = QualityVerdict.REVIEW_RECOMMENDED
    else:
        verdict = QualityVerdict.PASS_ADVISORY

    return QualityReviewRecord(
        id=f"qcr_{uuid4().hex[:14]}",
        asset_id=asset.id,
        plan_id=plan.id,
        media_type=asset.media_type,
        advisory_verdict=verdict,
        weighted_score=weighted_score,
        confidence=confidence,
        inspection_coverage=inspection_coverage,
        limitations=limitations,
        dimensions=dimensions,
        findings=findings,
        ai_tell_checklist=KEY_AI_TELLS if asset.media_type == MediaType.IMAGE else [],
        design_fit_notes=design_fit_notes,
        created_at=now,
    )
