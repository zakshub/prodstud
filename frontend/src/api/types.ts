export type MediaType = "image" | "video";

export interface UserProfile {
  id: string;
  email: string;
  display_name: string;
  daily_spend_cap_usd: number;
  spent_today_usd: number;
  preferred_theme: "dark" | "light";
  created_at: string;
}

export interface CredentialSummary {
  provider: string;
  masked_key: string;
  status: string;
  validated_at: string | null;
  validation_note: string | null;
  updated_at: string;
}

export interface ProjectRecord {
  id: string;
  user_id: string;
  name: string;
  description: string;
  archived: boolean;
  created_at: string;
  updated_at: string;
  asset_count: number;
  latest_asset_id: string | null;
}

export interface ReferenceAssetRecord {
  id: string;
  project_id: string;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  width: number | null;
  height: number | null;
  role: string;
  rights_confirmed: boolean;
  notes: string;
  created_at: string;
}

export interface ProtocolActivation {
  protocol_id: number;
  protocol_code: string;
  canonical_title: string;
  source_layer: string;
  disposition: string;
  reason: string;
  affected_fields: string[];
}

export interface DecisionExplanation {
  field: string;
  label: string;
  value: unknown;
  origin: "user_specified" | "inferred";
  plain_explanation: string;
  protocol_codes: string[];
}

export interface MissingInfoQuestion {
  field: string;
  question: string;
  why_it_matters: string;
  suggested_default: string;
}

export interface ContradictionWarning {
  code: string;
  severity: "blocking" | "warning";
  message: string;
  conflicting_fields: string[];
  suggested_resolution: string;
}

export interface ImagePlanDetails {
  reality_class: string;
  subject: string;
  subject_details: string;
  environment: string;
  camera_position: string;
  camera_height: string;
  focal_length_mm: number;
  aperture: string;
  focus_plane: string;
  lighting_key: string;
  lighting_fill: string;
  lighting_contrast_ratio: string;
  color_temperature_k: number;
  composition_rule: string;
  shot_framing: string;
  color_palette: string;
  material_and_texture: string;
  atmosphere: string;
  aspect_ratio: string;
  resolution: string;
  hard_locks: string[];
  soft_locks: string[];
  allowed_changes: string[];
  negative_constraints: string[];
}

export interface VideoShotSpec {
  shot_id: string;
  order: number;
  start_s: number;
  end_s: number;
  duration_s: number;
  visual_purpose: string;
  subject_action: string;
  framing: string;
  camera_movement: string;
  lens_focal_mm: number;
  lighting_continuity: string;
  environment_continuity: string;
  transition_out: string;
  reference_continuity: string[];
  feasibility_notes: string;
}

export interface VideoSequencePlan {
  sequence_intent: string;
  total_duration_s: number;
  fps: number;
  aspect_ratio: string;
  resolution: string;
  shots: VideoShotSpec[];
  continuity_invariants: string[];
  feasibility_status: string;
  feasibility_notes: string[];
  alternative_proposals: string[];
}

export interface ProductionPlanRecord {
  id: string;
  project_id: string;
  brief_id: string;
  parent_plan_id: string | null;
  version: number;
  media_type: MediaType;
  task_mode: string;
  complexity_tier: string;
  summary: string;
  interpreted_intent: string;
  image_plan: ImagePlanDetails | null;
  video_plan: VideoSequencePlan | null;
  activated_protocols: ProtocolActivation[];
  decisions: DecisionExplanation[];
  missing_info: MissingInfoQuestion[];
  contradictions: ContradictionWarning[];
  feasibility_ok: boolean;
  feasibility_warnings: string[];
  recommended_provider: string;
  recommended_model: string;
  approved_for_generation: boolean;
  created_at: string;
  updated_at: string;
}

export interface ProviderModelCapability {
  provider_id: string;
  provider_name: string;
  model_id: string;
  display_name: string;
  media_type: MediaType;
  support_status: "supported" | "unsupported" | "unverified" | "deprecated" | "provider_conditional";
  is_billable: boolean;
  is_local_test_fixture: boolean;
  requires_credential: boolean;
  supported_aspect_ratios: string[];
  supported_resolutions: string[];
  supported_durations_s: number[];
  min_duration_s: number | null;
  max_duration_s: number | null;
  max_reference_images: number;
  supports_multi_turn_edit: boolean;
  supports_first_last_frame: boolean;
  supports_video_extension: boolean;
  supports_cancellation: boolean;
  pricing_note: string;
  estimated_unit_cost_usd: number | null;
  official_doc_url: string;
  verified_date: string;
  limitations: string[];
}

export interface ApprovalQuote {
  quote_id: string;
  plan_id: string;
  provider_id: string;
  model_id: string;
  media_type: MediaType;
  is_billable: boolean;
  is_local_test_fixture: boolean;
  estimated_cost_usd: number | null;
  pricing_disclosure: string;
  user_daily_spend_cap_usd: number;
  user_spent_today_usd: number;
  spend_guard_allows: boolean;
  spend_guard_reason: string;
  credential_ready: boolean;
  credential_reason: string;
  settings_summary: Record<string, unknown>;
  feasibility_warnings: string[];
  confirmation_token: string;
  expires_at: string;
}

export interface GenerationJobRecord {
  id: string;
  project_id: string;
  plan_id: string;
  provider_id: string;
  model_id: string;
  media_type: MediaType;
  status: string;
  idempotency_key: string;
  is_billable: boolean;
  is_local_test_fixture: boolean;
  estimated_cost_usd: number | null;
  provider_job_id: string | null;
  asset_id: string | null;
  error_category: string | null;
  error_message: string | null;
  provider_may_have_accepted: boolean;
  diagnostics: Record<string, unknown>;
  created_at: string;
  updated_at: string;
}

export interface GeneratedAssetRecord {
  id: string;
  project_id: string;
  plan_id: string;
  job_id: string;
  parent_asset_id: string | null;
  version_number: number;
  media_type: MediaType;
  provider_id: string;
  model_id: string;
  is_local_test_fixture: boolean;
  filename: string;
  mime_type: string;
  size_bytes: number;
  sha256: string;
  width: number | null;
  height: number | null;
  duration_s: number | null;
  fps: number | null;
  tags: string[];
  collection_name: string | null;
  is_favorite: boolean;
  accepted: boolean;
  metadata: Record<string, unknown>;
  created_at: string;
}

export interface QualityDimensionScore {
  name: string;
  label: string;
  weight: number;
  score: number | null;
  critical: boolean;
  observed_evidence: string;
  inferred_notes: string;
}

export interface QualityFinding {
  severity: "critical" | "warning" | "info";
  dimension: string;
  location_or_timestamp: string;
  observed_evidence: string;
  inferred_cause: string;
  confidence: number;
  suggested_correction: string;
}

export interface QualityReviewRecord {
  id: string;
  asset_id: string;
  plan_id: string;
  media_type: MediaType;
  advisory_verdict: "pass_advisory" | "review_recommended" | "rework_recommended";
  weighted_score: number | null;
  confidence: number;
  inspection_coverage: string;
  limitations: string[];
  dimensions: QualityDimensionScore[];
  findings: QualityFinding[];
  ai_tell_checklist: Array<{ id: string; label: string; check_status: string }>;
  design_fit_notes: string[];
  human_feedback_status: string | null;
  human_feedback_note: string | null;
  created_at: string;
}

export interface RevisionRecord {
  id: string;
  project_id: string;
  source_plan_id: string;
  new_plan_id: string;
  source_asset_id: string | null;
  change_request: string;
  changed_fields: string[];
  preserved_fields: string[];
  provider_regeneration_note: string;
  created_at: string;
}

export interface ProjectWorkspaceData {
  project: ProjectRecord;
  references: ReferenceAssetRecord[];
  plans: ProductionPlanRecord[];
  jobs: GenerationJobRecord[];
  assets: GeneratedAssetRecord[];
  revisions: RevisionRecord[];
}

export interface ProductionTemplateRecord {
  id: string;
  user_id: string;
  name: string;
  media_type: MediaType;
  description: string;
  default_brief: Record<string, unknown>;
  created_at: string;
}

export interface AuditEventRecord {
  id: string;
  user_id: string | null;
  project_id: string | null;
  event_type: string;
  entity_type: string;
  entity_id: string;
  payload: Record<string, unknown>;
  created_at: string;
}
