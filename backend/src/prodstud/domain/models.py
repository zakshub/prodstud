"""Provider-neutral typed Pydantic v2 contracts for Production Studio."""

from __future__ import annotations

from typing import Any
from pydantic import BaseModel, Field

from .enums import (
    CapabilitySupport,
    ErrorCategory,
    JobStatus,
    MediaType,
    ProtocolDisposition,
    QualityVerdict,
    ReferenceRole,
    TaskMode,
)


class UserProfile(BaseModel):
    id: str
    email: str
    display_name: str
    daily_spend_cap_usd: float = 0.0
    spent_today_usd: float = 0.0
    preferred_theme: str = "dark"
    created_at: str


class CredentialSummary(BaseModel):
    provider: str
    masked_key: str
    status: str  # active | revoked
    validated_at: str | None = None
    validation_note: str | None = None
    updated_at: str


class ProjectRecord(BaseModel):
    id: str
    user_id: str
    name: str
    description: str = ""
    archived: bool = False
    created_at: str
    updated_at: str
    asset_count: int = 0
    latest_asset_id: str | None = None


class ReferenceAssetRecord(BaseModel):
    id: str
    project_id: str
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    width: int | None = None
    height: int | None = None
    role: ReferenceRole = ReferenceRole.STYLE
    rights_confirmed: bool = True
    notes: str = ""
    created_at: str


class ProtocolEntry(BaseModel):
    protocol_id: int
    protocol_code: str
    canonical_title: str
    source_layer: str
    source_reference: str
    original_description: str
    disposition: ProtocolDisposition
    activation_conditions: list[str]
    image_behavior: str
    video_behavior: str
    decision_fields: list[str]
    provider_translation_notes: str
    qc_checks: list[str]
    source_confidence: str
    implementation_notes: str


class ProtocolActivationRecord(BaseModel):
    protocol_id: int
    protocol_code: str
    canonical_title: str
    source_layer: str
    disposition: ProtocolDisposition
    reason: str
    affected_fields: list[str]


class DecisionExplanation(BaseModel):
    field: str
    label: str
    value: Any
    origin: str  # "user_specified" | "inferred"
    plain_explanation: str
    protocol_codes: list[str] = Field(default_factory=list)


class MissingInfoQuestion(BaseModel):
    field: str
    question: str
    why_it_matters: str
    suggested_default: str


class ContradictionWarning(BaseModel):
    code: str
    severity: str  # "blocking" | "warning"
    message: str
    conflicting_fields: list[str]
    suggested_resolution: str


class VideoShotSpec(BaseModel):
    shot_id: str
    order: int
    start_s: float
    end_s: float
    duration_s: float
    visual_purpose: str
    subject_action: str
    framing: str
    camera_movement: str
    lens_focal_mm: int
    lighting_continuity: str
    environment_continuity: str
    transition_out: str
    reference_continuity: list[str] = Field(default_factory=list)
    feasibility_notes: str = ""


class VideoSequencePlan(BaseModel):
    sequence_intent: str
    total_duration_s: float
    fps: int = 24
    aspect_ratio: str = "16:9"
    resolution: str = "720p"
    shots: list[VideoShotSpec]
    continuity_invariants: list[str]
    feasibility_status: str  # "feasible" | "requires_alternative"
    feasibility_notes: list[str] = Field(default_factory=list)
    alternative_proposals: list[str] = Field(default_factory=list)


class ImagePlanDetails(BaseModel):
    reality_class: str
    subject: str
    subject_details: str
    environment: str
    camera_position: str
    camera_height: str
    focal_length_mm: int
    aperture: str
    focus_plane: str
    lighting_key: str
    lighting_fill: str
    lighting_contrast_ratio: str
    color_temperature_k: int
    composition_rule: str
    shot_framing: str
    color_palette: str
    material_and_texture: str
    atmosphere: str
    aspect_ratio: str
    resolution: str
    hard_locks: list[str] = Field(default_factory=list)
    soft_locks: list[str] = Field(default_factory=list)
    allowed_changes: list[str] = Field(default_factory=list)
    negative_constraints: list[str] = Field(default_factory=list)


class BriefInput(BaseModel):
    project_id: str
    media_type: MediaType
    prompt_text: str = Field(..., min_length=4, max_length=4000)
    subject: str | None = None
    style_direction: str | None = None
    environment: str | None = None
    aspect_ratio: str | None = None
    resolution: str | None = None
    duration_s: float | None = None
    reference_ids: list[str] = Field(default_factory=list)
    hard_locks: list[str] = Field(default_factory=list)
    constraints: list[str] = Field(default_factory=list)
    preservation_mode: str = "new_generation"  # new_generation | strict_preservation | selective_edit
    provider_id: str | None = None
    model_id: str | None = None


class ProductionPlanRecord(BaseModel):
    id: str
    project_id: str
    brief_id: str
    parent_plan_id: str | None = None
    version: int = 1
    media_type: MediaType
    task_mode: TaskMode
    complexity_tier: str  # low | moderate | high
    summary: str
    interpreted_intent: str
    image_plan: ImagePlanDetails | None = None
    video_plan: VideoSequencePlan | None = None
    activated_protocols: list[ProtocolActivationRecord]
    decisions: list[DecisionExplanation]
    missing_info: list[MissingInfoQuestion] = Field(default_factory=list)
    contradictions: list[ContradictionWarning] = Field(default_factory=list)
    feasibility_ok: bool = True
    feasibility_warnings: list[str] = Field(default_factory=list)
    recommended_provider: str
    recommended_model: str
    approved_for_generation: bool = False
    created_at: str
    updated_at: str


class ProviderModelCapability(BaseModel):
    provider_id: str
    provider_name: str
    model_id: str
    display_name: str
    media_type: MediaType
    support_status: CapabilitySupport
    is_billable: bool
    is_local_test_fixture: bool = False
    requires_credential: bool
    supported_aspect_ratios: list[str]
    supported_resolutions: list[str]
    supported_durations_s: list[int] = Field(default_factory=list)
    min_duration_s: int | None = None
    max_duration_s: int | None = None
    max_reference_images: int = 0
    supports_multi_turn_edit: bool = False
    supports_first_last_frame: bool = False
    supports_video_extension: bool = False
    supports_cancellation: bool = False
    pricing_note: str
    estimated_unit_cost_usd: float | None = None
    official_doc_url: str
    verified_date: str
    limitations: list[str] = Field(default_factory=list)


class ApprovalQuote(BaseModel):
    quote_id: str
    plan_id: str
    provider_id: str
    model_id: str
    media_type: MediaType
    is_billable: bool
    is_local_test_fixture: bool
    estimated_cost_usd: float | None
    pricing_disclosure: str
    user_daily_spend_cap_usd: float
    user_spent_today_usd: float
    spend_guard_allows: bool
    spend_guard_reason: str
    credential_ready: bool
    credential_reason: str
    settings_summary: dict[str, Any]
    feasibility_warnings: list[str]
    confirmation_token: str
    expires_at: str


class GenerationJobRecord(BaseModel):
    id: str
    project_id: str
    plan_id: str
    provider_id: str
    model_id: str
    media_type: MediaType
    status: JobStatus
    idempotency_key: str
    is_billable: bool
    is_local_test_fixture: bool
    estimated_cost_usd: float | None = None
    provider_job_id: str | None = None
    asset_id: str | None = None
    error_category: ErrorCategory | None = None
    error_message: str | None = None
    provider_may_have_accepted: bool = False
    diagnostics: dict[str, Any] = Field(default_factory=dict)
    created_at: str
    updated_at: str


class GeneratedAssetRecord(BaseModel):
    id: str
    project_id: str
    plan_id: str
    job_id: str
    parent_asset_id: str | None = None
    version_number: int = 1
    media_type: MediaType
    provider_id: str
    model_id: str
    is_local_test_fixture: bool = False
    filename: str
    mime_type: str
    size_bytes: int
    sha256: str
    width: int | None = None
    height: int | None = None
    duration_s: float | None = None
    fps: float | None = None
    tags: list[str] = Field(default_factory=list)
    collection_name: str | None = None
    is_favorite: bool = False
    accepted: bool = False
    metadata: dict[str, Any] = Field(default_factory=dict)
    created_at: str


class QualityDimensionScore(BaseModel):
    name: str
    label: str
    weight: float
    score: float | None  # 1.0 - 5.0, or None when uninspectable
    critical: bool = False
    observed_evidence: str
    inferred_notes: str = ""


class QualityFinding(BaseModel):
    severity: str  # "critical" | "warning" | "info"
    dimension: str
    location_or_timestamp: str
    observed_evidence: str
    inferred_cause: str
    confidence: float  # 0.0 - 1.0
    suggested_correction: str


class QualityReviewRecord(BaseModel):
    id: str
    asset_id: str
    plan_id: str
    media_type: MediaType
    advisory_verdict: QualityVerdict
    weighted_score: float | None  # Visible weighted composite, strictly advisory
    confidence: float
    inspection_coverage: str  # Explicit honest disclosure of what was actually inspected
    limitations: list[str]
    dimensions: list[QualityDimensionScore]
    findings: list[QualityFinding]
    ai_tell_checklist: list[dict[str, Any]] = Field(default_factory=list)
    design_fit_notes: list[str] = Field(default_factory=list)
    human_feedback_status: str | None = None  # "accepted" | "rejected" | "needs_rework"
    human_feedback_note: str | None = None
    created_at: str


class RevisionRequest(BaseModel):
    change_request: str = Field(..., min_length=3, max_length=2000)
    target_shot_order: int | None = None
    override_fields: dict[str, Any] = Field(default_factory=dict)


class RevisionRecord(BaseModel):
    id: str
    project_id: str
    source_plan_id: str
    new_plan_id: str
    source_asset_id: str | None = None
    change_request: str
    changed_fields: list[str]
    preserved_fields: list[str]
    provider_regeneration_note: str
    created_at: str


class ProductionTemplateRecord(BaseModel):
    id: str
    user_id: str
    name: str
    media_type: MediaType
    description: str
    default_brief: dict[str, Any]
    created_at: str


class AuditEventRecord(BaseModel):
    id: str
    user_id: str | None
    project_id: str | None
    event_type: str
    entity_type: str
    entity_id: str
    payload: dict[str, Any]
    created_at: str
