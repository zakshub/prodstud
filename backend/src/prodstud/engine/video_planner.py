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


def revalidate_plan_against_capability(
    plan: "ProductionPlanRecord",
    capability: ProviderModelCapability,
    ref_count: int = 0,
    has_start_and_end_refs: bool = False,
) -> tuple[bool, list[str]]:
    """Re-verify edited or revised Image/Video plan constraints against target provider capability."""
    from prodstud.domain.enums import CapabilitySupport, MediaType

    warnings: list[str] = []
    ok = True

    if capability.support_status in {CapabilitySupport.UNSUPPORTED, CapabilitySupport.PROVIDER_CONDITIONAL}:
        ok = False
        warnings.append(
            f"Target model '{capability.model_id}' status is '{capability.support_status.value}' and cannot execute directly."
        )

    if plan.media_type == MediaType.IMAGE and plan.image_plan is not None:
        ip = plan.image_plan
        if ip.aspect_ratio not in capability.supported_aspect_ratios:
            ok = False
            warnings.append(
                f"Aspect ratio '{ip.aspect_ratio}' is not supported by {capability.model_id} "
                f"(supported: {', '.join(capability.supported_aspect_ratios)})."
            )
        if ip.resolution not in capability.supported_resolutions:
            ok = False
            warnings.append(
                f"Resolution '{ip.resolution}' is not supported by {capability.model_id} "
                f"(supported: {', '.join(capability.supported_resolutions)})."
            )
        if ref_count > capability.max_reference_images:
            ok = False
            warnings.append(
                f"{ref_count} reference images attached, exceeding {capability.model_id} cap of {capability.max_reference_images}."
            )
        return ok, warnings

    if plan.media_type == MediaType.VIDEO and plan.video_plan is not None:
        vp = plan.video_plan
        is_extension = vp.extended_from_asset_id is not None or vp.extension_duration_s is not None
        if vp.aspect_ratio not in capability.supported_aspect_ratios:
            ok = False
            warnings.append(
                f"Aspect ratio '{vp.aspect_ratio}' is not supported by {capability.model_id} "
                f"(supported: {', '.join(capability.supported_aspect_ratios)})."
            )
        if vp.resolution not in capability.supported_resolutions:
            ok = False
            warnings.append(
                f"Resolution '{vp.resolution}' is not supported by {capability.model_id} "
                f"(supported: {', '.join(capability.supported_resolutions)})."
            )
        if is_extension:
            ext_dur = float(vp.extension_duration_s or 0.0)
            if not capability.supports_video_extension:
                ok = False
                warnings.append(f"Model '{capability.model_id}' does not support multi-turn video extension.")
            if not (3.0 <= ext_dur <= 10.0):
                ok = False
                warnings.append(
                    f"Extension segment duration ({ext_dur:.1f}s) must be between 3.0s and 10.0s per turn."
                )
            if vp.total_duration_s > 30.0:
                ok = False
                warnings.append(
                    f"Cumulative extended sequence duration ({vp.total_duration_s:.1f}s) exceeds verified 30.0s multi-turn ceiling."
                )
        else:
            if capability.max_duration_s is not None and vp.total_duration_s > capability.max_duration_s:
                ok = False
                warnings.append(
                    f"Planned sequence duration ({vp.total_duration_s}s) exceeds {capability.model_id} single-clip limit of {capability.max_duration_s}s."
                )
            if capability.min_duration_s is not None and vp.total_duration_s < capability.min_duration_s:
                ok = False
                warnings.append(
                    f"Planned duration ({vp.total_duration_s}s) is below {capability.model_id} minimum duration ({capability.min_duration_s}s)."
                )
        if capability.supported_durations_s and not is_extension and int(round(vp.total_duration_s)) not in capability.supported_durations_s:
            warnings.append(
                f"{capability.model_id} supports discrete durations {capability.supported_durations_s}s."
            )
        if ref_count > capability.max_reference_images:
            ok = False
            warnings.append(
                f"{ref_count} reference images attached, exceeding {capability.model_id} cap of {capability.max_reference_images}."
            )
        if has_start_and_end_refs and vp.total_duration_s > 10.0 and capability.model_id == "gemini-omni-1.2-flash":
            ok = False
            warnings.append(
                "Gemini Omni 1.2 Flash first-and-last frame interpolation supports 3–10s maximum."
            )
        vp.feasibility_status = "feasible" if ok else "requires_alternative"
        vp.feasibility_notes = warnings or [
            f"Verified against {capability.model_id} duration, aspect ratio, resolution, and reference limits."
        ]
        return ok, warnings

    return ok, warnings


def build_video_extension_plan(
    *,
    source_plan: "ProductionPlanRecord",
    source_asset: "GeneratedAssetRecord",
    continuation_prompt: str,
    extension_duration_s: float,
    capability: ProviderModelCapability,
    source_provider_job_id: str | None = None,
) -> "ProductionPlanRecord":
    """Build a multi-turn Video Extension Plan preserving continuity invariants and previous interaction lineage.

    Verified against Google Gemini Omni 1.2 Flash docs (2026-11-19):
    - Per-turn tail extension window: 3–10s (using final 10s visual/audio lookback via previous_interaction_id)
    - Maximum cumulative multi-turn sequence ceiling: 30s
    """
    import copy
    from uuid import uuid4

    from prodstud.domain.enums import MediaType, TaskMode
    from prodstud.domain.models import GeneratedAssetRecord, ProductionPlanRecord
    from prodstud.storage.database import utcnow_iso

    if source_plan.media_type != MediaType.VIDEO or not source_plan.video_plan:
        raise ValueError("Video extension requires a source timed Video production plan.")

    ext_dur = round(float(extension_duration_s), 1)
    base_vp = copy.deepcopy(source_plan.video_plan)
    source_duration = round(float(source_asset.duration_s or base_vp.total_duration_s), 1)
    new_total = round(source_duration + ext_dur, 1)

    last_shot = base_vp.shots[-1] if base_vp.shots else None
    lighting_anchor = (
        last_shot.lighting_continuity
        if last_shot
        else "Carry forward source clip lighting direction and color temperature without flicker."
    )
    env_anchor = (
        last_shot.environment_continuity
        if last_shot
        else "Preserve spatial geography, props, and horizon line from final 10s tail."
    )
    ref_ids = list(last_shot.reference_continuity) if last_shot else []

    next_order = len(base_vp.shots) + 1
    new_shots: list[VideoShotSpec] = list(base_vp.shots)
    if ext_dur <= 6.0:
        new_shots.append(
            VideoShotSpec(
                shot_id=f"SHOT-{next_order:02d}",
                order=next_order,
                start_s=source_duration,
                end_s=new_total,
                duration_s=ext_dur,
                visual_purpose="Seamless multi-turn tail continuation extending the ending frame trajectory",
                subject_action=continuation_prompt.strip(),
                framing="Matched medium-to-close continuity framing inheriting previous ending lens perspective",
                camera_movement="Smooth continuous follow-through inheriting velocity from prior closing beat",
                lens_focal_mm=last_shot.lens_focal_mm if last_shot else 50,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Hold extended closing frame cleanly for delivery or next extension turn",
                reference_continuity=ref_ids,
                feasibility_notes="Single continuation shot anchored to final 10s lookback context via previous_interaction_id.",
            )
        )
    else:
        part1 = round(ext_dur * 0.5, 1)
        part2 = round(ext_dur - part1, 1)
        mid_t = round(source_duration + part1, 1)
        new_shots.append(
            VideoShotSpec(
                shot_id=f"SHOT-{next_order:02d}",
                order=next_order,
                start_s=source_duration,
                end_s=mid_t,
                duration_s=part1,
                visual_purpose="Bridge continuation seamlessly from prior closing frame into new beat",
                subject_action=f"Continue naturally from previous ending action: {continuation_prompt.strip()}",
                framing="Matched continuity frame preserving subject scale and horizon line",
                camera_movement="Steady motivated push or tracking glide matching prior camera momentum",
                lens_focal_mm=last_shot.lens_focal_mm if last_shot else 50,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Clean motion-matched beat into resolving payoff",
                reference_continuity=ref_ids,
                feasibility_notes="First half of extended segment locks spatial and light-field continuity.",
            )
        )
        new_shots.append(
            VideoShotSpec(
                shot_id=f"SHOT-{next_order + 1:02d}",
                order=next_order + 1,
                start_s=mid_t,
                end_s=new_total,
                duration_s=part2,
                visual_purpose="Extended closing resolution beat",
                subject_action=f"Complete extended action cleanly: {continuation_prompt.strip()}",
                framing="Controlled hero close framing settling cleanly on subject",
                camera_movement="Gentle deceleration into calm locked-off final second",
                lens_focal_mm=85 if (last_shot and last_shot.lens_focal_mm >= 50) else 50,
                lighting_continuity=lighting_anchor,
                environment_continuity=env_anchor,
                transition_out="Clean static tail hold",
                reference_continuity=ref_ids,
                feasibility_notes="Stable closing frame preserves option for subsequent turns up to 30s total.",
            )
        )

    invariants = list(base_vp.continuity_invariants)
    ext_lock = (
        f"Extension seam lock (at {source_duration:.1f}s): inherit subject identity, lighting direction, "
        f"and motion momentum seamlessly from asset {source_asset.id} (v{source_asset.version_number})."
    )
    if ext_lock not in invariants:
        invariants.append(ext_lock)

    resolved_pjid = source_provider_job_id or (source_asset.metadata.get("provider_job_id") if isinstance(source_asset.metadata, dict) else None)

    extended_vp = VideoSequencePlan(
        sequence_intent=f"{base_vp.sequence_intent} | Extended +{ext_dur:.1f}s: {continuation_prompt.strip()}",
        total_duration_s=new_total,
        fps=base_vp.fps,
        aspect_ratio=base_vp.aspect_ratio,
        resolution=base_vp.resolution,
        shots=new_shots,
        continuity_invariants=invariants,
        feasibility_status="feasible",
        feasibility_notes=[],
        alternative_proposals=[],
        extended_from_asset_id=source_asset.id,
        extension_duration_s=ext_dur,
        source_provider_job_id=str(resolved_pjid) if resolved_pjid else None,
    )

    now = utcnow_iso()
    new_plan = copy.deepcopy(source_plan)
    new_plan.id = f"pln_{uuid4().hex[:14]}"
    new_plan.parent_plan_id = source_plan.id
    new_plan.version = source_plan.version + 1
    new_plan.task_mode = TaskMode.VIDEO_EXTENSION
    new_plan.video_plan = extended_vp
    new_plan.recommended_provider = capability.provider_id
    new_plan.recommended_model = capability.model_id
    new_plan.approved_for_generation = False
    new_plan.created_at = now
    new_plan.updated_at = now

    ok, warnings = revalidate_plan_against_capability(new_plan, capability)
    if not ok:
        if new_total > 30.0:
            extended_vp.alternative_proposals.append(
                f"Reduce extension segment to at most {max(3.0, round(30.0 - source_duration, 1)):.1f}s to stay within the 30.0s multi-turn ceiling."
            )
        if not (3.0 <= ext_dur <= 10.0):
            extended_vp.alternative_proposals.append("Choose an extension segment between 3s and 10s.")

    new_plan.feasibility_ok = ok
    new_plan.feasibility_warnings = warnings
    new_plan.decisions.append(
        DecisionExplanation(
            field="video_extension",
            label="Multi-Turn Video Extension",
            value=f"+{ext_dur:.1f}s appended after {source_duration:.1f}s (total {new_total:.1f}s / 30.0s cap)",
            origin="user_specified",
            plain_explanation=(
                "Extends the existing clip from its closing frame using verified multi-turn continuation lineage "
                "(previous_interaction_id on Google Omni 1.2 Flash, final 10s lookback) while locking subject and light-field invariants."
            ),
            protocol_codes=["P050", "P104", "P126", "P139"],
        )
    )
    new_plan.summary = (
        f"Video Extension Plan v{new_plan.version} (+{ext_dur:.1f}s -> {new_total:.1f}s total, {len(new_shots)} shots) "
        f"continuing from {source_asset.filename}."
    )
    return new_plan

