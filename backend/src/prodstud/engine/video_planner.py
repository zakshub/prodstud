"""Dedicated Timed Video Shot Planner (D005 — never treats video as a still prompt with duration)."""

from __future__ import annotations

from prodstud.domain.models import (
    BriefInput,
    DecisionExplanation,
    ProviderModelCapability,
    ReferenceAssetRecord,
    VideoSequencePlan,
    VideoShotSpec,
)
from prodstud.engine.brief_interpreter import InterpretedBrief


def build_video_plan(
    brief: BriefInput,
    interpreted: InterpretedBrief,
    references: list[ReferenceAssetRecord],
    capability: ProviderModelCapability,
) -> tuple[VideoSequencePlan, list[DecisionExplanation], str, bool, list[str]]:
    """Build a structured timed shot plan with action, framing, camera motion, continuity, transitions, and feasibility."""
    lower = brief.prompt_text.lower()

    # Determine target duration and aspect ratio
    raw_duration = interpreted.requested_duration_s if interpreted.requested_duration_s is not None else 8.0
    total_duration = round(max(3.0, min(60.0, float(raw_duration))), 1)
    dur_origin = "user_specified" if interpreted.requested_duration_s is not None else "inferred"

    if brief.aspect_ratio:
        aspect_ratio = brief.aspect_ratio.strip()
        ar_origin = "user_specified"
    elif any(k in lower for k in ("vertical", "portrait", "9:16", "reel", "mobile")):
        aspect_ratio = "9:16"
        ar_origin = "inferred"
    else:
        aspect_ratio = "16:9"
        ar_origin = "inferred"

    resolution = brief.resolution.strip() if brief.resolution else "720p"

    # Lighting & environment continuity baseline
    lighting_anchor = (
        "3200K warm interior practical key with controlled shadow falloff — constant across all cuts"
        if interpreted.is_interior_or_night
        else "5600K diffused directional natural daylight from camera left — constant across all cuts"
    )
    env_anchor = f"{interpreted.environment}; consistent horizon line, architectural props, and ambient depth"
    ref_ids = [r.id for r in references]

    # Build purposeful timed shot structure (2-4 shots depending on total duration)
    shots: list[VideoShotSpec] = []
    if total_duration <= 5.0:
        shots.append(
            VideoShotSpec(
                shot_id="SHOT-01",
                order=1,
                start_s=0.0,
                end_s=total_duration,
                duration_s=total_duration,
                visual_purpose="Single uninterrupted establishing and hero action beat",
                subject_action=f"{interpreted.subject} executes primary motion naturally within frame with grounded physics",
                framing="Medium hero shot with clear headroom and spatial depth",
                camera_movement="Smooth slow push-in (dolly forward) maintaining steady horizon",
                lens_focal_mm=interpreted.requested_focal_mm or 35,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Hold final beat 0.5s cleanly to end frame",
                reference_continuity=ref_ids,
                feasibility_notes="Single continuous camera move minimizes temporal warping and morphing artifacts.",
            )
        )
    elif total_duration <= 10.0:
        s1 = round(total_duration * 0.45, 1)
        s2 = round(total_duration - s1, 1)
        shots = [
            VideoShotSpec(
                shot_id="SHOT-01",
                order=1,
                start_s=0.0,
                end_s=s1,
                duration_s=s1,
                visual_purpose="Establish spatial geography, lighting mood, and subject placement",
                subject_action=f"{interpreted.subject} enters or settles into primary action in {interpreted.environment}",
                framing="Wide-to-medium establishing shot (rule of thirds)",
                camera_movement="Controlled lateral tracking glide matching subject pace",
                lens_focal_mm=interpreted.requested_focal_mm or 35,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Motivated motion-matched straight cut to tighter hero framing",
                reference_continuity=ref_ids,
                feasibility_notes="Avoids rapid whip pans that cause motion smearing.",
            ),
            VideoShotSpec(
                shot_id="SHOT-02",
                order=2,
                start_s=s1,
                end_s=round(s1 + s2, 1),
                duration_s=s2,
                visual_purpose="Deliver intimate tactile detail and clear closing emotional/product payoff",
                subject_action=f"Hero detail motion on {interpreted.subject} revealing texture, specular response, and deliberate finish",
                framing="Medium close-up centered on hero feature with shallow continuous DOF",
                camera_movement="Subtle slow dolly-in settling to a calm locked-off final second",
                lens_focal_mm=85 if (interpreted.is_product or interpreted.has_human_subject) else 50,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Clean final hold for graceful delivery end",
                reference_continuity=ref_ids,
                feasibility_notes="Tighter focal length locks visual focus and reduces background flicker risk.",
            ),
        ]
    else:
        s1 = round(total_duration * 0.3, 1)
        s2 = round(total_duration * 0.4, 1)
        s3 = round(total_duration - s1 - s2, 1)
        shots = [
            VideoShotSpec(
                shot_id="SHOT-01",
                order=1,
                start_s=0.0,
                end_s=s1,
                duration_s=s1,
                visual_purpose="Opening establishing shot anchoring setting, scale, and light direction",
                subject_action=f"Introduce {interpreted.subject} positioned naturally inside {interpreted.environment}",
                framing="Wide architectural establishing frame",
                camera_movement="Slow forward push-in along central axis",
                lens_focal_mm=28,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Clean straight cut on movement peak",
                reference_continuity=ref_ids,
                feasibility_notes="Grounded wide framing establishes spatial continuity before moving closer.",
            ),
            VideoShotSpec(
                shot_id="SHOT-02",
                order=2,
                start_s=s1,
                end_s=round(s1 + s2, 1),
                duration_s=s2,
                visual_purpose="Primary narrative or functional action progression",
                subject_action=f"{interpreted.subject} performs core dynamic action with realistic weight and momentum",
                framing="Medium eye-level tracking frame",
                camera_movement="Steady lateral dolly tracking subject motion at constant distance",
                lens_focal_mm=50,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Match-action cut to detail payoff shot",
                reference_continuity=ref_ids,
                feasibility_notes="Single directional axis preserves screen direction and continuity.",
            ),
            VideoShotSpec(
                shot_id="SHOT-03",
                order=3,
                start_s=round(s1 + s2, 1),
                end_s=round(s1 + s2 + s3, 1),
                duration_s=s3,
                visual_purpose="Closing hero detail and resolution beat",
                subject_action=f"Controlled finishing motion highlighting authentic texture and posture of {interpreted.subject}",
                framing="Close-up hero framing with soft optical background falloff",
                camera_movement="Gentle micro-dolly settling into brief static hold",
                lens_focal_mm=85,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Hold final frame cleanly",
                reference_continuity=ref_ids,
                feasibility_notes="Stable closing frame enables seamless future video extension if needed.",
            ),
        ]

    # Continuity Invariants Ledger (cps-brief-to-shot-lineage-tracker)
    continuity_invariants = [
        f"Subject lock: preserve identity, geometry, and wardrobe/surface finish of '{interpreted.subject}' across all {len(shots)} shot(s).",
        f"Light field lock: {lighting_anchor}.",
        f"Spatial lock: {env_anchor}.",
        "Temporal lock: 24 FPS cadence with consistent 180-degree natural shutter motion blur; avoid teleporting props or hue shifts across cuts.",
    ]
    for hl in interpreted.hard_locks:
        continuity_invariants.append(f"Hard lock: {hl}")

    # Provider Feasibility Validation (D005 + WORKFLOWS.md)
    feasibility_warnings: list[str] = []
    alternatives: list[str] = []
    feasibility_ok = True

    if aspect_ratio not in capability.supported_aspect_ratios:
        feasibility_ok = False
        feasibility_warnings.append(
            f"Aspect ratio '{aspect_ratio}' is not supported by {capability.model_id} (supported: {', '.join(capability.supported_aspect_ratios)})."
        )
        alternatives.append(f"Switch aspect ratio to '{capability.supported_aspect_ratios[0]}' for native provider support.")

    if resolution not in capability.supported_resolutions:
        feasibility_ok = False
        feasibility_warnings.append(
            f"Resolution '{resolution}' is not supported by {capability.model_id} (supported: {', '.join(capability.supported_resolutions)})."
        )
        alternatives.append(f"Use '{capability.supported_resolutions[0]}' supported natively by {capability.model_id}.")

    if capability.max_duration_s is not None and total_duration > capability.max_duration_s:
        feasibility_ok = False
        feasibility_warnings.append(
            f"Planned sequence duration ({total_duration}s) exceeds {capability.model_id} single-clip limit of {capability.max_duration_s}s."
        )
        if capability.supports_video_extension:
            alternatives.append(
                f"Generate the first {capability.max_duration_s}s segment now and use multi-turn extension (up to 30s total) for remaining shots."
            )
        alternatives.append(
            f"Condense shot pacing to fit within {capability.max_duration_s}s so the full sequence renders cleanly in one pass."
        )

    if capability.min_duration_s is not None and total_duration < capability.min_duration_s:
        feasibility_ok = False
        feasibility_warnings.append(
            f"Planned duration ({total_duration}s) is below {capability.model_id} minimum duration ({capability.min_duration_s}s)."
        )
        alternatives.append(f"Increase total duration to at least {capability.min_duration_s}s.")

    if capability.supported_durations_s and int(round(total_duration)) not in capability.supported_durations_s:
        nearest = min(capability.supported_durations_s, key=lambda d: abs(d - total_duration))
        feasibility_warnings.append(
            f"{capability.model_id} supports discrete durations {capability.supported_durations_s}s; planned {total_duration}s will need snapping to {nearest}s."
        )
        alternatives.append(f"Snap planned total duration to {nearest}s and rebalance shot durations proportionally.")

    if len(references) > capability.max_reference_images:
        feasibility_ok = False
        feasibility_warnings.append(
            f"{len(references)} reference images attached, exceeding {capability.model_id} cap of {capability.max_reference_images}."
        )
        alternatives.append(f"Select the {capability.max_reference_images} highest-priority reference assets.")

    has_start_and_end = any(r.role.value == "start_frame" for r in references) and any(r.role.value == "end_frame" for r in references)
    if has_start_and_end and total_duration > 10.0 and capability.model_id == "gemini-omni-1.2-flash":
        feasibility_ok = False
        feasibility_warnings.append(
            "Gemini Omni 1.2 Flash first-and-last frame interpolation supports 3–10s maximum; durations >10s are rejected by the API."
        )
        alternatives.append("Reduce duration to 8–10s for first/last frame interpolation, or remove the end-frame lock.")

    video_plan = VideoSequencePlan(
        sequence_intent=interpreted.interpreted_intent,
        total_duration_s=total_duration,
        fps=24,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        shots=shots,
        continuity_invariants=continuity_invariants,
        feasibility_status="feasible" if feasibility_ok else "requires_alternative",
        feasibility_notes=feasibility_warnings or [f"Verified against {capability.model_id} duration, aspect ratio, resolution, and reference limits."],
        alternative_proposals=alternatives,
    )

    decisions = [
        DecisionExplanation(
            field="shots",
            label="Timed Shot Structure",
            value=f"{len(shots)} shot(s) totaling {total_duration}s at 24 FPS",
            origin=dur_origin,
            plain_explanation="Breaks the brief into paced shots with explicit subject action, camera movement, and clean cuts instead of one vague motion prompt.",
            protocol_codes=["P033", "P104", "P105", "P131"],
        ),
        DecisionExplanation(
            field="continuity_invariants",
            label="Cross-Shot Continuity Locks",
            value=f"{len(continuity_invariants)} active invariants (subject, light field, environment, cadence)",
            origin="inferred",
            plain_explanation="Carries locked subject, lighting color temperature, and spatial rules across every shot to minimize flicker and drift.",
            protocol_codes=["P050", "P060", "P126", "P139"],
        ),
        DecisionExplanation(
            field="aspect_ratio",
            label="Video Delivery Format",
            value=f"{aspect_ratio} · {resolution} · 24 FPS (MP4)",
            origin=ar_origin,
            plain_explanation="Matched directly to verified video provider output parameters prior to confirmation.",
            protocol_codes=["P065", "P067", "P106", "P108"],
        ),
    ]

    summary = (
        f"{len(shots)}-shot timed video sequence ({total_duration}s, {aspect_ratio}, {resolution}, 24 FPS) for {interpreted.subject}. "
        f"Feasibility: {'Ready' if feasibility_ok else 'Alternative proposed before billing'}."
    )
    return video_plan, decisions, summary, feasibility_ok, feasibility_warnings
