"""Controlled Revision Mapper: isolates requested changes while preserving all unaffected approved decisions."""

from __future__ import annotations

import copy
import re
from uuid import uuid4

from prodstud.domain.enums import MediaType
from prodstud.domain.models import (
    ProductionPlanRecord,
    ProviderModelCapability,
    RevisionRecord,
    RevisionRequest,
)
from prodstud.storage.database import utcnow_iso


def apply_targeted_revision(
    *,
    source_plan: ProductionPlanRecord,
    revision_request: RevisionRequest,
    source_asset_id: str | None,
    capability: ProviderModelCapability,
) -> tuple[ProductionPlanRecord, RevisionRecord]:
    """Translate a targeted revision request into the smallest plan delta while preserving unaffected decisions."""
    new_plan = copy.deepcopy(source_plan)
    new_plan.id = f"pln_{uuid4().hex[:14]}"
    new_plan.parent_plan_id = source_plan.id
    new_plan.version = source_plan.version + 1
    new_plan.approved_for_generation = False  # Always require explicit re-approval before billable execution
    now = utcnow_iso()
    new_plan.created_at = now
    new_plan.updated_at = now

    text = revision_request.change_request.strip()
    lower = text.lower()
    changed_fields: list[str] = []
    preserved_fields: list[str] = []

    if new_plan.media_type == MediaType.IMAGE and new_plan.image_plan is not None:
        img = new_plan.image_plan
        all_fields = [
            "subject",
            "environment",
            "focal_length_mm",
            "aperture",
            "lighting_key",
            "lighting_fill",
            "lighting_contrast_ratio",
            "color_temperature_k",
            "composition_rule",
            "shot_framing",
            "color_palette",
            "aspect_ratio",
            "resolution",
            "hard_locks",
        ]

        # Apply explicit structured overrides first
        for field_name, val in revision_request.override_fields.items():
            if hasattr(img, field_name) and val is not None:
                setattr(img, field_name, val)
                changed_fields.append(field_name)

        # Heuristic targeted mapping from natural language revision note
        focal_match = re.search(r"\b(24|28|35|50|85|100|135)\s*mm\b", lower)
        if focal_match and "focal_length_mm" not in changed_fields:
            img.focal_length_mm = int(focal_match.group(1))
            changed_fields.append("focal_length_mm")

        ar_match = re.search(r"\b(1:1|3:4|4:3|4:5|3:2|2:3|9:16|16:9|21:9)\b", lower)
        if ar_match and "aspect_ratio" not in changed_fields:
            img.aspect_ratio = ar_match.group(1)
            changed_fields.append("aspect_ratio")

        if any(k in lower for k in ("warmer", "golden", "tungsten", "warm light")) and "color_temperature_k" not in changed_fields:
            img.color_temperature_k = 3400
            img.lighting_key = f"{img.lighting_key}; shifted warmer (~3400K) per targeted revision"
            changed_fields.extend(["color_temperature_k", "lighting_key"])
        elif any(k in lower for k in ("cooler", "crisp daylight", "cool light", "blue hour")) and "color_temperature_k" not in changed_fields:
            img.color_temperature_k = 6200
            img.lighting_key = f"{img.lighting_key}; shifted cooler (~6200K) per targeted revision"
            changed_fields.extend(["color_temperature_k", "lighting_key"])

        if any(k in lower for k in ("dramatic", "higher contrast", "moodier", "darker shadow")) and "lighting_contrast_ratio" not in changed_fields:
            img.lighting_contrast_ratio = "6:1 dramatic sculpted contrast with deeper negative fill"
            changed_fields.append("lighting_contrast_ratio")
        elif any(k in lower for k in ("softer", "brighter", "even light", "high key")) and "lighting_contrast_ratio" not in changed_fields:
            img.lighting_contrast_ratio = "2:1 soft open commercial fill"
            changed_fields.append("lighting_contrast_ratio")

        if any(k in lower for k in ("close-up", "tighter", "zoom in", "closer")) and "shot_framing" not in changed_fields:
            img.shot_framing = "Tighter close-up framing focusing closely on hero subject detail"
            changed_fields.append("shot_framing")
        elif any(k in lower for k in ("wider", "pull back", "more room", "negative space")) and "shot_framing" not in changed_fields:
            img.shot_framing = "Wider environmental framing with increased negative space around subject"
            changed_fields.append("shot_framing")

        if any(k in lower for k in ("background", "environment", "setting", "location")) and "environment" not in changed_fields:
            img.environment = f"{img.environment} (revised per instruction: {text})"
            changed_fields.append("environment")

        if not changed_fields:
            img.subject_details = f"{img.subject_details} Targeted adjustment: {text}."
            changed_fields.append("subject_details")

        img.allowed_changes = [f"Targeted revision v{new_plan.version}: {text}"]
        preserved_fields = [f for f in all_fields if f not in changed_fields]
        new_plan.summary = f"Revised Image Plan v{new_plan.version} — updated {', '.join(changed_fields)} while preserving {len(preserved_fields)} approved decisions."

    elif new_plan.media_type == MediaType.VIDEO and new_plan.video_plan is not None:
        vp = new_plan.video_plan
        all_fields = ["aspect_ratio", "resolution", "total_duration_s", "continuity_invariants", "shots"]

        for field_name, val in revision_request.override_fields.items():
            if hasattr(vp, field_name) and val is not None and field_name != "shots":
                setattr(vp, field_name, val)
                changed_fields.append(field_name)

        target_order = revision_request.target_shot_order
        if target_order is None:
            shot_match = re.search(r"\bshot\s*#?\s*(\d+)\b", lower)
            if shot_match:
                target_order = int(shot_match.group(1))

        if target_order is not None:
            for shot in vp.shots:
                if shot.order == target_order:
                    if any(k in lower for k in ("slower", "static", "locked", "pan", "dolly", "track", "handheld", "camera")):
                        shot.camera_movement = f"{shot.camera_movement} -> Revised: {text}"
                        changed_fields.append(f"shot_{shot.order}.camera_movement")
                    elif any(k in lower for k in ("close", "wide", "frame", "framing")):
                        shot.framing = f"{shot.framing} -> Revised: {text}"
                        changed_fields.append(f"shot_{shot.order}.framing")
                    else:
                        shot.subject_action = f"{shot.subject_action} (Revised: {text})"
                        changed_fields.append(f"shot_{shot.order}.subject_action")
        else:
            ar_match = re.search(r"\b(16:9|9:16|1:1)\b", lower)
            if ar_match and "aspect_ratio" not in changed_fields:
                vp.aspect_ratio = ar_match.group(1)
                changed_fields.append("aspect_ratio")
            if not changed_fields and vp.shots:
                vp.shots[0].subject_action = f"{vp.shots[0].subject_action} (Revised: {text})"
                changed_fields.append("shot_1.subject_action")

        preserved_fields = [f for f in all_fields if f not in changed_fields and not any(c.startswith("shot_") for c in changed_fields if f == "shots")]
        for shot in vp.shots:
            if target_order is not None and shot.order != target_order:
                preserved_fields.append(f"shot_{shot.order} (preserved untouched)")
        new_plan.summary = f"Revised Video Plan v{new_plan.version} — updated {', '.join(changed_fields)} while preserving continuity invariants."

    regen_note = (
        f"{capability.display_name} supports multi-turn contextual revision, but local pixel-only guarantees are not absolute — review unaffected locked regions after regeneration."
        if capability.supports_multi_turn_edit
        else f"{capability.display_name} regenerates the full asset from updated directives and cannot guarantee pixel-locked local edits; preserved plan parameters are carried forward verbatim."
    )

    rev = RevisionRecord(
        id=f"rev_{uuid4().hex[:14]}",
        project_id=source_plan.project_id,
        source_plan_id=source_plan.id,
        new_plan_id=new_plan.id,
        source_asset_id=source_asset_id,
        change_request=text,
        changed_fields=sorted(set(changed_fields)),
        preserved_fields=preserved_fields,
        provider_regeneration_note=regen_note,
        created_at=now,
    )
    return new_plan, rev
