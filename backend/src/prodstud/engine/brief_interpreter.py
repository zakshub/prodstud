"""Brief interpreter: intent classification, missing-info detection, contradiction detection, and anti-AI screening."""

from __future__ import annotations

import re
from dataclasses import dataclass, field

from prodstud.domain.enums import MediaType, ReferenceRole, TaskMode
from prodstud.domain.models import (
    BriefInput,
    ContradictionWarning,
    MissingInfoQuestion,
    ReferenceAssetRecord,
)

# Studio Brain anti-AI & anti-copy guardlists
BANNED_AI_BUZZWORDS = (
    "hyperrealistic",
    "photorealistic",
    "ultra realistic",
    "8k",
    "16k",
    "masterpiece",
    "trending on artstation",
    "unreal engine",
    "award winning photo",
)

LIVING_CREATOR_COPY_PATTERN = re.compile(r"\bin the style of\s+([A-Z][a-z]+(?:\s+[A-Z][a-z]+)+)")

HUMAN_KEYWORDS = ("person", "woman", "man", "model", "portrait", "face", "chef", "athlete", "artist", "hand", "hands", "founder", "actor", "dancer", "craftsman")
PRODUCT_KEYWORDS = ("bottle", "watch", "shoe", "sneaker", "perfume", "camera", "headphones", "packaging", "product", "mug", "cup", "espresso", "ceramic", "vase", "carafe", "coffee", "lamp", "chair", "armchair", "bag", "cosmetic", "serum", "can", "box", "laptop", "device", "jewelry")
FASHION_KEYWORDS = ("fashion", "editorial", "garment", "coat", "dress", "jacket", "tailored", "silk", "linen", "wool", "runway", "lookbook", "outfit", "wardrobe")
INTERIOR_NIGHT_KEYWORDS = ("night", "midnight", "neon", "indoor", "interior", "studio", "atelier", "cafe", "loft", "gallery", "dark", "moody", "candle", "lamp", "tungsten", "dusk")
OUTDOOR_DAY_KEYWORDS = ("midday", "noon", "bright sunlight", "sunny", "beach", "desert", "daylight", "morning sun", "courtyard", "golden hour", "overcast")


@dataclass
class InterpretedBrief:
    media_type: MediaType
    task_mode: TaskMode
    complexity_tier: str
    interpreted_intent: str
    subject: str
    environment: str
    style_direction: str
    reality_class: str
    has_human_subject: bool
    is_product: bool
    is_interior_or_night: bool
    requested_focal_mm: int | None
    requested_aspect_ratio: str | None
    requested_resolution: str | None
    requested_duration_s: float | None
    hard_locks: list[str] = field(default_factory=list)
    soft_locks: list[str] = field(default_factory=list)
    allowed_changes: list[str] = field(default_factory=list)
    missing_info: list[MissingInfoQuestion] = field(default_factory=list)
    contradictions: list[ContradictionWarning] = field(default_factory=list)
    clean_prompt_notes: list[str] = field(default_factory=list)


def _extract_focal_mm(text: str) -> int | None:
    match = re.search(r"\b(14|18|24|28|35|40|50|65|85|100|105|135|200)\s*mm\b", text, re.IGNORECASE)
    return int(match.group(1)) if match else None


def _extract_duration_s(text: str) -> float | None:
    match = re.search(r"\b(\d+(?:\.\d+)?)\s*(?:sec|secs|second|seconds|s)\b", text, re.IGNORECASE)
    return float(match.group(1)) if match else None


def _infer_subject(brief: BriefInput) -> str:
    if brief.subject and brief.subject.strip():
        return brief.subject.strip()
    # Extract concise primary phrase from first sentence/clause
    text = brief.prompt_text.strip()
    first_clause = re.split(r"[.;\n]", text)[0].strip()
    words = first_clause.split()
    return " ".join(words[:14]) if len(words) > 14 else first_clause


def _infer_environment(brief: BriefInput, lower: str) -> tuple[str, bool]:
    if brief.environment and brief.environment.strip():
        return brief.environment.strip(), False
    env_patterns = [
        (r"\bin\s+(?:a|an|the)\s+([^,.;]+)", True),
        (r"\bon\s+(?:a|an|the)\s+([^,.;]+)", True),
        (r"\bat\s+(?:a|an|the)\s+([^,.;]+)", True),
    ]
    for pattern, _ in env_patterns:
        m = re.search(pattern, brief.prompt_text, re.IGNORECASE)
        if m and len(m.group(1).strip()) >= 4:
            return m.group(1).strip()[:120], False

    if any(k in lower for k in PRODUCT_KEYWORDS):
        return "Neutral textured architectural tabletop with controlled studio backdrop", True
    if any(k in lower for k in HUMAN_KEYWORDS):
        return "Natural-light minimalist architectural studio interior with subtle wall texture", True
    return "Coherent natural architectural setting matched to subject scale", True


def interpret_brief(brief: BriefInput, references: list[ReferenceAssetRecord]) -> InterpretedBrief:
    """Interpret plain-language brief into structured production context, missing questions, and contradictions."""
    text = brief.prompt_text.strip()
    lower = text.lower()

    has_human = any(k in lower for k in HUMAN_KEYWORDS)
    is_product = any(k in lower for k in PRODUCT_KEYWORDS)
    is_fashion = any(k in lower for k in FASHION_KEYWORDS)
    is_interior_night = any(k in lower for k in INTERIOR_NIGHT_KEYWORDS)
    is_outdoor_day = any(k in lower for k in OUTDOOR_DAY_KEYWORDS)

    # Task mode classification (reconciled with Studio Brain 19-mode matrix + Video modes)
    if brief.media_type == MediaType.VIDEO:
        duration_hint = brief.duration_s or _extract_duration_s(text) or 8.0
        if any(k in lower for k in ("extend", "continuation", "continue the clip")):
            task_mode = TaskMode.VIDEO_EXTENSION
        elif duration_hint > 10.0 or any(k in lower for k in ("sequence", "shots", "cut to", "scene", "storyboard", "commercial", "montage", "then")):
            task_mode = TaskMode.VIDEO_MULTI_SHOT_SEQUENCE
        else:
            task_mode = TaskMode.VIDEO_SINGLE_SHOT
    else:
        if brief.preservation_mode == "strict_preservation":
            task_mode = TaskMode.STRICT_PRESERVATION_EDIT
        elif brief.preservation_mode == "selective_edit":
            task_mode = TaskMode.SELECTIVE_EDIT
        elif is_fashion:
            task_mode = TaskMode.FASHION_EDITORIAL
        elif is_product and not has_human:
            task_mode = TaskMode.PRODUCT_IMAGE
        elif has_human and ("portrait" in lower or "headshot" in lower or "close-up" in lower):
            task_mode = TaskMode.PORTRAIT
        elif any(k in lower for k in ("documentary", "candid", "street", "lifestyle")):
            task_mode = TaskMode.LIFESTYLE_DOCUMENTARY
        elif any(k in lower for k in ("cinematic", "film still", "anamorphic", "movie")):
            task_mode = TaskMode.CINEMATIC_STILL
        else:
            task_mode = TaskMode.NEW_GENERATION

    subject = _infer_subject(brief)
    environment, env_was_inferred = _infer_environment(brief, lower)
    style_direction = (
        brief.style_direction.strip()
        if brief.style_direction and brief.style_direction.strip()
        else (
            "Restrained commercial studio photography with authentic material texture"
            if is_product
            else "Physically grounded natural editorial cinematography"
            if brief.media_type == MediaType.VIDEO
            else "Authentic editorial photography with physically causal lighting"
        )
    )
    reality_class = (
        "Commercial Studio Product Photography"
        if task_mode == TaskMode.PRODUCT_IMAGE
        else "Documentary / Editorial Realism"
        if task_mode in {TaskMode.LIFESTYLE_DOCUMENTARY, TaskMode.FASHION_EDITORIAL}
        else "Cinematic Motion Capture (24 FPS)"
        if brief.media_type == MediaType.VIDEO
        else "Natural Photographic Realism"
    )

    requested_focal = _extract_focal_mm(text)
    requested_duration = brief.duration_s if brief.duration_s is not None else _extract_duration_s(text)

    # Hard locks & Soft locks (Source Preservation Doctrine)
    hard_locks = [h.strip() for h in brief.hard_locks if h.strip()]
    soft_locks: list[str] = ["lighting color temperature coherence", "optical depth-of-field continuity"]
    allowed_changes: list[str] = []

    for ref in references:
        if ref.role == ReferenceRole.IDENTITY and "subject facial identity and proportions" not in hard_locks:
            hard_locks.append("subject facial identity and proportions")
        elif ref.role == ReferenceRole.PRODUCT and "product silhouette, geometry, and label typography" not in hard_locks:
            hard_locks.append("product silhouette, geometry, and label typography")
        elif ref.role == ReferenceRole.COMPOSITION and "camera framing and compositional geometry" not in hard_locks:
            hard_locks.append("camera framing and compositional geometry")
        elif ref.role == ReferenceRole.ENVIRONMENT and "architectural background geometry" not in hard_locks:
            hard_locks.append("architectural background geometry")

    if task_mode == TaskMode.STRICT_PRESERVATION_EDIT:
        for default_lock in ("original subject identity", "garment or product structure", "scene geometry and framing"):
            if default_lock not in hard_locks:
                hard_locks.append(default_lock)
        allowed_changes = ["exposure and white balance cleanup", "local contrast and micro-detail recovery", "restrained color correction"]
    elif task_mode == TaskMode.SELECTIVE_EDIT:
        allowed_changes = ["user-specified target modification only while preserving locked regions"]
    else:
        allowed_changes = ["original scene composition and lighting design within brief constraints"]

    # Missing information detection (only material unknowns — NEVER 170 questions!)
    missing_info: list[MissingInfoQuestion] = []
    if env_was_inferred and brief.preservation_mode == "new_generation":
        missing_info.append(
            MissingInfoQuestion(
                field="environment",
                question="Where is the subject placed?",
                why_it_matters="Setting determines light motivation, background depth, and color bounce on the subject.",
                suggested_default=environment,
            )
        )
    if not brief.aspect_ratio:
        default_ar = "16:9" if brief.media_type == MediaType.VIDEO else ("4:5" if is_fashion else "3:2")
        missing_info.append(
            MissingInfoQuestion(
                field="aspect_ratio",
                question="What target framing aspect ratio is required for delivery?",
                why_it_matters="Aspect ratio governs subject blocking, headroom, and provider capability compliance.",
                suggested_default=default_ar,
            )
        )
    if brief.media_type == MediaType.VIDEO and requested_duration is None:
        missing_info.append(
            MissingInfoQuestion(
                field="duration_s",
                question="What total clip duration (in seconds) are you targeting?",
                why_it_matters="Video models enforce strict duration windows (e.g., 3–15s on Gemini Omni 1.2 Flash) and pacing changes shot count.",
                suggested_default="8 seconds (2–3 cohesive shots)",
            )
        )

    # Contradiction & Policy Detection (Structured Rule Conflict Resolution)
    contradictions: list[ContradictionWarning] = []
    clean_notes: list[str] = []

    # 1. Conflicting lighting/time-of-day
    if is_interior_night and is_outdoor_day and any(k in lower for k in ("midnight", "night", "dark room")) and any(k in lower for k in ("midday", "noon", "bright sunlight")):
        contradictions.append(
            ContradictionWarning(
                code="LIGHTING_TIME_CONFLICT",
                severity="warning",
                message="Brief combines contradictory time-of-day lighting cues (night/dark interior vs bright midday sunlight).",
                conflicting_fields=["environment", "lighting_key"],
                suggested_resolution="Choose one dominant motivated light field (either daylight exterior/window or night practical lighting).",
            )
        )

    # 2. Hard lock vs requested change conflict (Studio Brain rule conflict pattern)
    if brief.preservation_mode == "strict_preservation" and any(k in lower for k in ("change background", "replace background", "new outfit", "redesign", "change pose")):
        contradictions.append(
            ContradictionWarning(
                code="HARD_LOCK_VS_EDIT_CONFLICT",
                severity="blocking",
                message="Strict preservation mode forbids replacing locked background, pose, or wardrobe elements.",
                conflicting_fields=["preservation_mode", "hard_locks", "prompt_text"],
                suggested_resolution="Switch preservation_mode to 'selective_edit' or remove structural redesign instructions.",
            )
        )

    # 3. Preservation edit without any reference image
    if brief.preservation_mode in {"strict_preservation", "selective_edit"} and not references:
        contradictions.append(
            ContradictionWarning(
                code="PRESERVATION_REFERENCE_MISSING",
                severity="blocking",
                message="Preservation or selective edit mode requires at least one uploaded source reference image.",
                conflicting_fields=["preservation_mode", "reference_ids"],
                suggested_resolution="Upload a source reference image or switch to 'new_generation'.",
            )
        )

    # 4. Reference rights check (Studio Brain rights > aesthetics)
    unconfirmed_refs = [r.filename for r in references if not r.rights_confirmed]
    if unconfirmed_refs:
        contradictions.append(
            ContradictionWarning(
                code="REFERENCE_RIGHTS_UNCONFIRMED",
                severity="blocking",
                message=f"Reference asset(s) lack confirmed usage rights: {', '.join(unconfirmed_refs)}.",
                conflicting_fields=["reference_ids"],
                suggested_resolution="Confirm usage rights for uploaded reference assets or remove them before generation.",
            )
        )

    # 5. Optical contradiction (ultra-wide lens + compressed telephoto bokeh)
    if requested_focal is not None and requested_focal <= 24 and any(k in lower for k in ("telephoto compression", "compressed background", "extreme bokeh")):
        contradictions.append(
            ContradictionWarning(
                code="OPTICAL_FOCAL_CONFLICT",
                severity="warning",
                message=f"Requested {requested_focal}mm wide-angle lens optically contradicts telephoto compression / shallow bokeh.",
                conflicting_fields=["focal_length_mm", "dof_falloff"],
                suggested_resolution="Use 85mm–135mm for background compression, or keep 24mm with deeper environmental context.",
            )
        )

    # 6. Anti-AI buzzword & Anti-copy living creator checks
    found_buzzwords = [bw for bw in BANNED_AI_BUZZWORDS if bw in lower]
    if found_buzzwords:
        clean_notes.append(
            f"Replaced generic AI buzzwords ({', '.join(found_buzzwords)}) with concrete camera, lens, lighting, and material specifications."
        )
    creator_match = LIVING_CREATOR_COPY_PATTERN.search(text)
    if creator_match:
        contradictions.append(
            ContradictionWarning(
                code="ANTI_COPY_STYLE_GUARD",
                severity="warning",
                message=f"Detected direct living-creator style mimicry ('in the style of {creator_match.group(1)}'). Production Studio applies transferable lighting/optical principles instead.",
                conflicting_fields=["style_direction", "prompt_text"],
                suggested_resolution="Describe concrete lighting quality, lens framing, and tonal palette instead of mimicking a named creator.",
            )
        )

    # Complexity classification
    complexity_score = 0
    if brief.media_type == MediaType.VIDEO:
        complexity_score += 2
    if len(references) >= 2:
        complexity_score += 1
    if hard_locks:
        complexity_score += 1
    if contradictions:
        complexity_score += 1
    if any(k in lower for k in ("text", "logo", "hands", "reflection", "crowd", "water", "glass")):
        complexity_score += 1

    complexity_tier = "high" if complexity_score >= 4 else "moderate" if complexity_score >= 2 else "low"

    interpreted_intent = (
        f"Produce a {brief.media_type.value} ({task_mode.value.replace('_', ' ').lower()}) featuring {subject} "
        f"in {environment}, guided by {reality_class.lower()}."
    )

    return InterpretedBrief(
        media_type=brief.media_type,
        task_mode=task_mode,
        complexity_tier=complexity_tier,
        interpreted_intent=interpreted_intent,
        subject=subject,
        environment=environment,
        style_direction=style_direction,
        reality_class=reality_class,
        has_human_subject=has_human,
        is_product=is_product,
        is_interior_or_night=is_interior_night,
        requested_focal_mm=requested_focal,
        requested_aspect_ratio=brief.aspect_ratio,
        requested_resolution=brief.resolution,
        requested_duration_s=requested_duration,
        hard_locks=hard_locks,
        soft_locks=soft_locks,
        allowed_changes=allowed_changes,
        missing_info=missing_info[:3],
        contradictions=contradictions,
        clean_prompt_notes=clean_notes,
    )
