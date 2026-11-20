"""Tests for 170-Protocol Registry, contextual activation, contradiction detection, Image Planner, Video Shot Planner, and Revision Engine."""

from __future__ import annotations

from prodstud.domain.enums import MediaType, ReferenceRole, TaskMode
from prodstud.domain.models import BriefInput, ReferenceAssetRecord, RevisionRequest
from prodstud.engine.revision_engine import apply_targeted_revision
from prodstud.runtime import AppRuntime


def test_170_protocol_registry_integrity(runtime: AppRuntime) -> None:
    assert len(runtime.protocols.entries) == 170
    ids = [p.protocol_id for p in runtime.protocols.entries]
    assert ids == list(range(1, 171))
    summary = runtime.protocols.summary()
    assert summary["total_protocols"] == 170
    assert sum(summary["dispositions"].values()) == 170


def test_contextual_protocol_activation_is_not_170_questions(runtime: AppRuntime) -> None:
    cap = runtime.providers.resolve_capability(MediaType.IMAGE, "google_gemini_image", "gemini-nano-banana-2.1")
    brief = BriefInput(
        project_id="prj_test",
        media_type=MediaType.IMAGE,
        prompt_text="Matte ceramic espresso cup on brushed limestone counter with warm morning window light",
        aspect_ratio="4:5",
    )
    plan = runtime.engine.create_plan(brief_id="brf_1", brief=brief, references=[], capability=cap)
    # Must activate a focused contextual subset, NEVER dump 170 questions
    assert 8 <= len(plan.activated_protocols) <= 30
    assert len(plan.missing_info) <= 3
    assert plan.task_mode == TaskMode.PRODUCT_IMAGE
    assert plan.image_plan is not None
    assert plan.image_plan.aspect_ratio == "4:5"
    assert plan.image_plan.focal_length_mm == 100
    assert plan.feasibility_ok is True


def test_contradiction_detection_hard_lock_and_rights(runtime: AppRuntime) -> None:
    cap = runtime.providers.resolve_capability(MediaType.IMAGE, "google_gemini_image", "gemini-nano-banana-2.1")
    unconfirmed_ref = ReferenceAssetRecord(
        id="ref_1",
        project_id="prj_test",
        filename="source.png",
        mime_type="image/png",
        size_bytes=1200,
        sha256="abc123",
        width=640,
        height=480,
        role=ReferenceRole.PRODUCT,
        rights_confirmed=False,
        created_at="2026-11-19T00:00:00Z",
    )
    brief = BriefInput(
        project_id="prj_test",
        media_type=MediaType.IMAGE,
        prompt_text="Replace background with bright desert beach in the style of Annie Leibovitz",
        preservation_mode="strict_preservation",
        reference_ids=["ref_1"],
    )
    plan = runtime.engine.create_plan(brief_id="brf_2", brief=brief, references=[unconfirmed_ref], capability=cap)
    codes = {c.code for c in plan.contradictions}
    assert "HARD_LOCK_VS_EDIT_CONFLICT" in codes
    assert "REFERENCE_RIGHTS_UNCONFIRMED" in codes
    assert "ANTI_COPY_STYLE_GUARD" in codes
    assert plan.feasibility_ok is False


def test_video_planner_creates_timed_shots_and_checks_provider_duration(runtime: AppRuntime) -> None:
    cap = runtime.providers.resolve_capability(MediaType.VIDEO, "google_gemini_video", "gemini-omni-1.2-flash")
    # Valid 8-second multi-shot sequence
    brief_ok = BriefInput(
        project_id="prj_v1",
        media_type=MediaType.VIDEO,
        prompt_text="Artisan barista pouring espresso into glass cup in dimly lit cafe, then close-up steam rising",
        duration_s=8.0,
        aspect_ratio="16:9",
        resolution="720p",
    )
    plan_ok = runtime.engine.create_plan(brief_id="brf_v1", brief=brief_ok, references=[], capability=cap)
    assert plan_ok.video_plan is not None
    assert len(plan_ok.video_plan.shots) == 2
    assert sum(s.duration_s for s in plan_ok.video_plan.shots) == 8.0
    assert plan_ok.video_plan.continuity_invariants
    assert plan_ok.feasibility_ok is True

    # Over-limit 24-second sequence -> must detect infeasibility and propose alternatives BEFORE billing
    brief_long = BriefInput(
        project_id="prj_v1",
        media_type=MediaType.VIDEO,
        prompt_text="Three-shot luxury watch launch sequence across studio and rooftop",
        duration_s=24.0,
        aspect_ratio="16:9",
    )
    plan_long = runtime.engine.create_plan(brief_id="brf_v2", brief=brief_long, references=[], capability=cap)
    assert plan_long.video_plan is not None
    assert plan_long.feasibility_ok is False
    assert plan_long.video_plan.feasibility_status == "requires_alternative"
    assert len(plan_long.video_plan.alternative_proposals) >= 1


def test_targeted_revision_preserves_unaffected_decisions(runtime: AppRuntime) -> None:
    cap = runtime.providers.resolve_capability(MediaType.IMAGE, "google_gemini_image", "gemini-nano-banana-2.1")
    brief = BriefInput(
        project_id="prj_r1",
        media_type=MediaType.IMAGE,
        prompt_text="Minimalist leather Weekender bag on oak bench in north-facing gallery",
        aspect_ratio="3:2",
        resolution="2K",
    )
    plan = runtime.engine.create_plan(brief_id="brf_r1", brief=brief, references=[], capability=cap)
    assert plan.image_plan is not None
    orig_focal = plan.image_plan.focal_length_mm
    orig_ar = plan.image_plan.aspect_ratio

    new_plan, rev = apply_targeted_revision(
        source_plan=plan,
        revision_request=RevisionRequest(change_request="Make lighting warmer and slightly more dramatic"),
        source_asset_id="ast_orig",
        capability=cap,
    )
    assert new_plan.version == 2
    assert new_plan.parent_plan_id == plan.id
    assert new_plan.approved_for_generation is False
    assert new_plan.image_plan is not None
    assert new_plan.image_plan.color_temperature_k == 3400
    assert new_plan.image_plan.focal_length_mm == orig_focal
    assert new_plan.image_plan.aspect_ratio == orig_ar
    assert "focal_length_mm" in rev.preserved_fields
    assert "aspect_ratio" in rev.preserved_fields
    assert "color_temperature_k" in rev.changed_fields
