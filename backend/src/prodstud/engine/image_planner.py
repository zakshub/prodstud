"""Physically causal Image Production Planner (provider-independent)."""

from __future__ import annotations

from prodstud.domain.enums import TaskMode
from prodstud.domain.models import (
    BriefInput,
    DecisionExplanation,
    ImagePlanDetails,
    ReferenceAssetRecord,
)
from prodstud.engine.brief_interpreter import InterpretedBrief

STANDARD_ANTI_AI_CONSTRAINTS = [
    "No plastic airbrushed skin or uniform synthetic pore overlays",
    "No unmotivated rim lighting or highlights without a scene light source",
    "No floating contact shadows; anchor subject and props with ambient occlusion",
    "No anatomical hand distortion, fused fingers, or warped straight architecture lines",
    "No uniform Gaussian background cutout blur; keep continuous optical depth-of-field falloff",
    "Differentiate material specular response (matte diffuse, satin directional sheen, metallic reflection)",
]


def build_image_plan(
    brief: BriefInput,
    interpreted: InterpretedBrief,
    references: list[ReferenceAssetRecord],
) -> tuple[ImagePlanDetails, list[DecisionExplanation], str]:
    """Build a structured, physically causal image plan with plain-language explanations."""
    lower = brief.prompt_text.lower()

    # Camera & Lens physics
    if interpreted.requested_focal_mm:
        focal_mm = interpreted.requested_focal_mm
        focal_origin = "user_specified"
    elif interpreted.task_mode == TaskMode.PORTRAIT:
        focal_mm = 85
        focal_origin = "inferred"
    elif interpreted.task_mode == TaskMode.PRODUCT_IMAGE:
        focal_mm = 100
        focal_origin = "inferred"
    elif interpreted.task_mode == TaskMode.FASHION_EDITORIAL:
        focal_mm = 50
        focal_origin = "inferred"
    elif interpreted.task_mode == TaskMode.CINEMATIC_STILL:
        focal_mm = 35
        focal_origin = "inferred"
    else:
        focal_mm = 50
        focal_origin = "inferred"

    aperture = (
        "f/8 (deep front-to-back product sharpness)"
        if interpreted.task_mode == TaskMode.PRODUCT_IMAGE
        else "f/2.2 (natural eye focus with gradual background falloff)"
        if interpreted.task_mode == TaskMode.PORTRAIT
        else "f/4 (balanced subject separation with legible environment geometry)"
    )
    camera_height = (
        "Eye level, slightly below horizon for balanced stature"
        if interpreted.has_human_subject
        else "15-degree elevated hero tabletop angle"
        if interpreted.is_product
        else "Natural human eye-level vantage (1.5m)"
    )
    camera_position = (
        "Three-quarter front perspective at ~2.2m subject distance"
        if interpreted.has_human_subject
        else "Controlled studio hero angle at ~1.2m working distance"
        if interpreted.is_product
        else "Balanced medium distance establishing spatial depth"
    )
    focus_plane = (
        "Critical sharpness locked on subject's near eye"
        if interpreted.has_human_subject
        else "Critical sharpness locked on primary product face and label edges"
        if interpreted.is_product
        else "Critical sharpness on primary hero subject plane"
    )

    # Lighting intelligence (Physical Causality Rule)
    if "golden hour" in lower or "sunset" in lower:
        key_light = "Low-angle 20-degree warm late-afternoon sunlight from camera left"
        fill_light = "Cool open sky ambient fill from camera right with subtle shadow retention"
        contrast_ratio = "4:1 warm directional editorial contrast"
        kelvin = 3800
    elif interpreted.is_interior_or_night:
        key_light = "Motivated practical lamp / diffused overhead tungsten source 45 degrees camera left, feathered across subject"
        fill_light = "Restrained ambient wall bounce with negative fill on shadow side for sculptural depth"
        contrast_ratio = "5:1 controlled low-key studio contrast"
        kelvin = 3200
    elif interpreted.is_product:
        key_light = "Large diffused softbox overhead-left at 45 degrees creating smooth graduated specular rolloff"
        fill_light = "White matte bounce card camera right plus black negative-fill edge flag for crisp product edge definition"
        contrast_ratio = "3:1 clean commercial product contrast"
        kelvin = 5400
    else:
        key_light = "Large diffused directional daylight window 45 degrees camera left with soft penumbra shadow edges"
        fill_light = "Neutral architectural wall bounce preserving natural shadow density"
        contrast_ratio = "3:1 natural editorial contrast"
        kelvin = 5600

    # Framing & Aspect Ratio
    if brief.aspect_ratio:
        aspect_ratio = brief.aspect_ratio.strip()
        ar_origin = "user_specified"
    elif interpreted.task_mode in {TaskMode.FASHION_EDITORIAL, TaskMode.PORTRAIT}:
        aspect_ratio = "4:5"
        ar_origin = "inferred"
    elif interpreted.task_mode == TaskMode.CINEMATIC_STILL:
        aspect_ratio = "16:9"
        ar_origin = "inferred"
    else:
        aspect_ratio = "3:2"
        ar_origin = "inferred"

    if brief.resolution:
        resolution = brief.resolution.strip()
        res_origin = "user_specified"
    else:
        resolution = "2K" if interpreted.is_product else "1K"
        res_origin = "inferred"

    shot_framing = (
        "Close-up / head-and-shoulders framing with generous top breathing room"
        if interpreted.task_mode == TaskMode.PORTRAIT
        else "Tight hero commercial framing with clean negative space margins"
        if interpreted.is_product
        else "Medium three-quarter framing grounding subject in architectural space"
    )
    composition_rule = (
        "Centered architectural symmetry with crisp vertical lines"
        if interpreted.is_product
        else "Asymmetric rule-of-thirds placement with clear foreground/midground/background depth"
    )

    color_palette = (
        "Calibrated neutral architectural midtones anchored around authentic subject material hues; protected natural highlights"
    )
    material_texture = (
        "Physically distinct material reflectance: natural micro-grain, woven fiber texture, realistic matte vs specular separation"
        if not interpreted.has_human_subject
        else "Authentic non-uniform skin pores, natural hair flyaways, gravity-driven fabric folds, and true surface reflectance"
    )
    atmosphere = (
        "Clean optical clarity with subtle natural aerial falloff in deep background planes; zero decorative haze"
    )

    subject_details = (
        f"{interpreted.subject}. Maintain natural asymmetry, weight distribution, and realistic hand/prop contact."
        if interpreted.has_human_subject
        else f"{interpreted.subject}. Preserve crisp geometry, structural seams, authentic surface wear, and physical ground contact."
    )

    negatives = list(STANDARD_ANTI_AI_CONSTRAINTS)
    for c in brief.constraints:
        if c.strip():
            negatives.append(f"User constraint: {c.strip()}")

    plan_details = ImagePlanDetails(
        reality_class=interpreted.reality_class,
        subject=interpreted.subject,
        subject_details=subject_details,
        environment=interpreted.environment,
        camera_position=camera_position,
        camera_height=camera_height,
        focal_length_mm=focal_mm,
        aperture=aperture,
        focus_plane=focus_plane,
        lighting_key=key_light,
        lighting_fill=fill_light,
        lighting_contrast_ratio=contrast_ratio,
        color_temperature_k=kelvin,
        composition_rule=composition_rule,
        shot_framing=shot_framing,
        color_palette=color_palette,
        material_and_texture=material_texture,
        atmosphere=atmosphere,
        aspect_ratio=aspect_ratio,
        resolution=resolution,
        hard_locks=interpreted.hard_locks,
        soft_locks=interpreted.soft_locks,
        allowed_changes=interpreted.allowed_changes,
        negative_constraints=negatives,
    )

    decisions = [
        DecisionExplanation(
            field="reality_class",
            label="Photographic Reality Class",
            value=interpreted.reality_class,
            origin="inferred",
            plain_explanation="Sets the benchmark for allowable polish, natural texture, and optical imperfections so the image feels captured rather than synthetic.",
            protocol_codes=["P009", "P018"],
        ),
        DecisionExplanation(
            field="focal_length_mm",
            label="Lens Focal Length & Optics",
            value=f"{focal_mm}mm · {aperture}",
            origin=focal_origin,
            plain_explanation=(
                f"A {focal_mm}mm lens prevents unnatural perspective distortion while keeping depth-of-field transitions physically continuous."
            ),
            protocol_codes=["P072", "P074", "P080"],
        ),
        DecisionExplanation(
            field="lighting_key",
            label="Motivated Lighting Architecture",
            value=f"{key_light} ({contrast_ratio}, ~{kelvin}K)",
            origin="inferred",
            plain_explanation="Every highlight and shadow is traced to a single motivated light field so subject and background integrate realistically.",
            protocol_codes=["P081", "P082", "P094", "P098"],
        ),
        DecisionExplanation(
            field="aspect_ratio",
            label="Output Framing & Resolution",
            value=f"{aspect_ratio} @ {resolution}",
            origin=ar_origin if ar_origin == "user_specified" else res_origin,
            plain_explanation="Validated against supported provider ratios and resolution tiers before generation approval.",
            protocol_codes=["P067", "P108"],
        ),
    ]
    if references:
        decisions.append(
            DecisionExplanation(
                field="hard_locks",
                label="Source Preservation Locks",
                value=interpreted.hard_locks or ["Preserve uploaded reference cues"],
                origin="user_specified" if brief.hard_locks else "inferred",
                plain_explanation=f"Protects locked identity, product, or framing traits across {len(references)} uploaded reference asset(s).",
                protocol_codes=["P021", "P030", "P050", "P128"],
            )
        )

    summary = (
        f"{interpreted.reality_class} plan for {interpreted.subject} in {interpreted.environment}. "
        f"Shot at {focal_mm}mm ({aspect_ratio}, {resolution}) with {contrast_ratio} (~{kelvin}K) motivated lighting."
    )
    return plan_details, decisions, summary
