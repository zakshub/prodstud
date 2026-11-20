"""Production Intelligence Engine facade orchestrating interpretation, 170-protocol activation, and planning."""

from __future__ import annotations

from uuid import uuid4

from prodstud.domain.enums import MediaType
from prodstud.domain.models import (
    BriefInput,
    ProductionPlanRecord,
    ProviderModelCapability,
    ReferenceAssetRecord,
)
from prodstud.engine.brief_interpreter import interpret_brief
from prodstud.engine.image_planner import build_image_plan
from prodstud.engine.protocol_registry import ProtocolRegistry
from prodstud.engine.video_planner import build_video_plan
from prodstud.storage.database import utcnow_iso


class ProductionIntelligenceEngine:
    """Provider-independent Production Intelligence Engine."""

    def __init__(self, registry: ProtocolRegistry):
        self.registry = registry

    def create_plan(
        self,
        *,
        brief_id: str,
        brief: BriefInput,
        references: list[ReferenceAssetRecord],
        capability: ProviderModelCapability,
    ) -> ProductionPlanRecord:
        interpreted = interpret_brief(brief, references)
        now = utcnow_iso()

        image_plan = None
        video_plan = None
        feasibility_ok = True
        feasibility_warnings: list[str] = []

        if brief.media_type == MediaType.IMAGE:
            image_plan, decisions, summary = build_image_plan(brief, interpreted, references)
            # Validate image plan against verified capability registry
            if image_plan.aspect_ratio not in capability.supported_aspect_ratios:
                feasibility_ok = False
                feasibility_warnings.append(
                    f"Aspect ratio '{image_plan.aspect_ratio}' is unsupported by {capability.model_id} "
                    f"(supported: {', '.join(capability.supported_aspect_ratios)})."
                )
            if image_plan.resolution not in capability.supported_resolutions:
                feasibility_ok = False
                feasibility_warnings.append(
                    f"Resolution '{image_plan.resolution}' is unsupported by {capability.model_id} "
                    f"(supported: {', '.join(capability.supported_resolutions)})."
                )
            if len(references) > capability.max_reference_images:
                feasibility_ok = False
                feasibility_warnings.append(
                    f"{len(references)} reference image(s) exceed {capability.model_id} cap of {capability.max_reference_images}."
                )
            is_multi_shot = False
            high_res = image_plan.resolution in {"2K", "4K"}
        else:
            video_plan, decisions, summary, feasibility_ok, feasibility_warnings = build_video_plan(
                brief, interpreted, references, capability
            )
            is_multi_shot = len(video_plan.shots) > 1
            high_res = video_plan.resolution in {"1080p", "4K"}

        # Blocking contradictions also prevent immediate approval until resolved
        if any(c.severity == "blocking" for c in interpreted.contradictions):
            feasibility_ok = False
            for c in interpreted.contradictions:
                if c.severity == "blocking":
                    feasibility_warnings.append(f"Blocking contradiction ({c.code}): {c.message}")

        activations = self.registry.activate_contextually(
            media_type=brief.media_type,
            task_mode=interpreted.task_mode,
            has_references=bool(references),
            multi_reference=len(references) > 1,
            is_revision=False,
            has_human_subject=interpreted.has_human_subject,
            is_product=interpreted.is_product,
            is_interior_or_night=interpreted.is_interior_or_night,
            is_multi_shot=is_multi_shot,
            has_feasibility_warning=not feasibility_ok,
            high_resolution=high_res,
            prompt_lower=brief.prompt_text.lower(),
        )

        return ProductionPlanRecord(
            id=f"pln_{uuid4().hex[:14]}",
            project_id=brief.project_id,
            brief_id=brief_id,
            parent_plan_id=None,
            version=1,
            media_type=brief.media_type,
            task_mode=interpreted.task_mode,
            complexity_tier=interpreted.complexity_tier,
            summary=summary,
            interpreted_intent=interpreted.interpreted_intent,
            image_plan=image_plan,
            video_plan=video_plan,
            activated_protocols=activations,
            decisions=decisions,
            missing_info=interpreted.missing_info,
            contradictions=interpreted.contradictions,
            feasibility_ok=feasibility_ok,
            feasibility_warnings=feasibility_warnings,
            recommended_provider=capability.provider_id,
            recommended_model=capability.model_id,
            approved_for_generation=False,
            created_at=now,
            updated_at=now,
        )
