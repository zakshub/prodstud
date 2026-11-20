# 170-Protocol Registry Coverage Report

- **Registry Version:** `1.0.0`
- **Total Protocols Mapped:** `170 / 170`
- **Registry SHA-256:** `1d116194b1a72feb6c0da9db01066403b4c50714ea125ee79f2c2d24ac2590ac`
- **Source Reference:** `zakshub/studio:knowledge/production-intelligence/170-protocol-summary.md`
- **Source Confidence:** `summary_verified_pending_full_manual_page_audit`

## Disposition Summary

| Disposition | Count | Meaning |
|---|---:|---|
| `core` | 64 | Directly applied in core image/video production planning & QC |
| `conditional` | 69 | Activated contextually only when brief, references, or media mode require it |
| `adapted` | 29 | Source manual production procedure explicitly adapted for synthetic image/video generation |
| `deferred` | 8 | Intentionally outside MVP/V1 synthetic production scope (e.g., physical shoot crew/call sheets) |

## Complete 170-Protocol Inventory

| ID | Code | Layer | Canonical Title | Disposition | Triggers | Decision Fields |
|---:|---|---|---|---|---|---|
| 1 | `P001` | A. Concept and Intent | Input Interpretation | `core` | `always` | `interpreted_objective, media_type` |
| 2 | `P002` | A. Concept and Intent | User Intent Classification | `core` | `always` | `task_mode, deliverable_class` |
| 3 | `P003` | A. Concept and Intent | Problem Definition | `conditional` | `commercial, brief_complex` | `problem_statement` |
| 4 | `P004` | A. Concept and Intent | Output Purpose | `core` | `always` | `output_purpose, delivery_context` |
| 5 | `P005` | A. Concept and Intent | Success Criteria | `core` | `always` | `success_criteria` |
| 6 | `P006` | A. Concept and Intent | Target Audience | `conditional` | `commercial, campaign, brand` | `target_audience` |
| 7 | `P007` | A. Concept and Intent | Emotional Objective | `conditional` | `narrative, editorial, portrait, video` | `emotional_objective` |
| 8 | `P008` | A. Concept and Intent | Visual Intent | `core` | `always` | `visual_intent` |
| 9 | `P009` | A. Concept and Intent | Reality Level | `core` | `always` | `reality_class` |
| 10 | `P010` | A. Concept and Intent | Concept Strength | `conditional` | `brief_complex, narrative` | `concept_clarity_check` |
| 11 | `P011` | B. Strategy and Creative Direction | Creative Brief Structuring | `core` | `always` | `structured_brief` |
| 12 | `P012` | B. Strategy and Creative Direction | Core Message | `conditional` | `commercial, product, campaign` | `core_message` |
| 13 | `P013` | B. Strategy and Creative Direction | Narrative Moment | `conditional` | `narrative, video, editorial` | `narrative_beat` |
| 14 | `P014` | B. Strategy and Creative Direction | Genre and World | `conditional` | `cinematic, narrative, video` | `world_rules` |
| 15 | `P015` | B. Strategy and Creative Direction | Mood Direction | `conditional` | `editorial, cinematic, portrait, video` | `mood` |
| 16 | `P016` | B. Strategy and Creative Direction | Tone Control | `conditional` | `commercial, editorial, brand` | `tone` |
| 17 | `P017` | B. Strategy and Creative Direction | Art Direction | `core` | `always` | `art_direction_summary` |
| 18 | `P018` | B. Strategy and Creative Direction | Aesthetic Discipline | `core` | `always` | `anti_cliche_constraints` |
| 19 | `P019` | B. Strategy and Creative Direction | Style Boundary | `conditional` | `brand, preservation, reference` | `style_boundaries` |
| 20 | `P020` | B. Strategy and Creative Direction | Originality Verification | `adapted` | `always` | `originality_guard` |
| 21 | `P021` | C. Research and Reference | Reference Collection | `conditional` | `has_references` | `reference_manifest` |
| 22 | `P022` | C. Research and Reference | Reference Deconstruction | `conditional` | `has_references` | `reference_attributes` |
| 23 | `P023` | C. Research and Reference | Reference Fusion | `conditional` | `multi_reference` | `reference_fusion_rules` |
| 24 | `P024` | C. Research and Reference | Category Scan | `deferred` | `research_mode` | `category_conventions` |
| 25 | `P025` | C. Research and Reference | Visual Benchmark | `conditional` | `editorial, commercial, product` | `quality_benchmark` |
| 26 | `P026` | C. Research and Reference | Camera Reference Alignment | `conditional` | `has_references, camera_specified` | `camera_reference_notes` |
| 27 | `P027` | C. Research and Reference | Lighting Reference Alignment | `conditional` | `has_references, lighting_specified` | `lighting_reference_notes` |
| 28 | `P028` | C. Research and Reference | Color Reference Alignment | `conditional` | `has_references, color_specified` | `color_reference_notes` |
| 29 | `P029` | C. Research and Reference | Composition Reference Alignment | `conditional` | `has_references, composition_specified` | `composition_reference_notes` |
| 30 | `P030` | C. Research and Reference | Reference Risk and Rights Check | `core` | `has_references` | `reference_rights_status, reference_conflicts` |
| 31 | `P031` | D. Production Feasibility | Technical Feasibility Validation | `core` | `always` | `feasibility_status, feasibility_warnings` |
| 32 | `P032` | D. Production Feasibility | Budget Reality and Spend Guard | `adapted` | `always` | `estimated_cost_usd, spend_guard_status` |
| 33 | `P033` | D. Production Feasibility | Time and Async Duration Planning | `adapted` | `video, async_job` | `expected_latency_class, clip_duration_s` |
| 34 | `P034` | D. Production Feasibility | Resource Allocation | `conditional` | `multi_shot, batch` | `execution_units` |
| 35 | `P035` | D. Production Feasibility | Technical Risk Assessment | `core` | `always` | `technical_risks` |
| 36 | `P036` | D. Production Feasibility | Visual Risk Assessment | `core` | `always` | `visual_risks` |
| 37 | `P037` | D. Production Feasibility | Complexity Classification | `core` | `always` | `complexity_tier` |
| 38 | `P038` | D. Production Feasibility | Production Priority Ranking | `core` | `always` | `hard_locks, soft_locks` |
| 39 | `P039` | D. Production Feasibility | Backup and Alternative Plan | `conditional` | `feasibility_warning, video_long_duration` | `fallback_alternatives` |
| 40 | `P040` | D. Production Feasibility | Scope Control | `core` | `always` | `scope_boundaries` |
| 41 | `P041` | E. Subject / Character / Object | Subject Selection | `core` | `always` | `primary_subject` |
| 42 | `P042` | E. Subject / Character / Object | Subject Priority Hierarchy | `conditional` | `multi_subject, product, portrait` | `subject_hierarchy` |
| 43 | `P043` | E. Subject / Character / Object | Subject Psychology | `conditional` | `human_subject, portrait, narrative` | `subject_psychology` |
| 44 | `P044` | E. Subject / Character / Object | Facial Expression Logic | `conditional` | `human_subject, portrait` | `facial_expression` |
| 45 | `P045` | E. Subject / Character / Object | Eye Direction and Gaze | `conditional` | `human_subject, portrait` | `eye_direction` |
| 46 | `P046` | E. Subject / Character / Object | Body Language | `conditional` | `human_subject, video` | `body_language` |
| 47 | `P047` | E. Subject / Character / Object | Pose Architecture | `conditional` | `human_subject, fashion, portrait` | `pose_spec` |
| 48 | `P048` | E. Subject / Character / Object | Pose Realism Check | `conditional` | `human_subject, fashion, video` | `pose_realism_checks` |
| 49 | `P049` | E. Subject / Character / Object | Hand and Contact Logic | `conditional` | `human_subject, product_held` | `hand_contact_spec` |
| 50 | `P050` | E. Subject / Character / Object | Subject Consistency | `core` | `has_references, video, revision, product` | `subject_invariants` |
| 51 | `P051` | F. Environment and Set | Location Logic | `core` | `always` | `location_setting` |
| 52 | `P052` | F. Environment and Set | Environment Design | `conditional` | `environment_rich, cinematic, video` | `environment_architecture` |
| 53 | `P053` | F. Environment and Set | Set Dressing | `conditional` | `environment_rich, commercial, product` | `set_props` |
| 54 | `P054` | F. Environment and Set | Background Depth | `core` | `always` | `background_separation` |
| 55 | `P055` | F. Environment and Set | Foreground Layer | `conditional` | `cinematic, editorial, video` | `foreground_elements` |
| 56 | `P056` | F. Environment and Set | Surface Materials | `core` | `always` | `material_physics` |
| 57 | `P057` | F. Environment and Set | Practical Environment Light | `conditional` | `interior, night, cinematic` | `practical_lights` |
| 58 | `P058` | F. Environment and Set | Environmental Story | `conditional` | `narrative, editorial, video` | `environment_story_cues` |
| 59 | `P059` | F. Environment and Set | Spatial Realism | `core` | `always` | `contact_shadows_and_scale` |
| 60 | `P060` | F. Environment and Set | Environment Consistency | `core` | `video, revision, multi_shot` | `environment_invariants` |
| 61 | `P061` | G. Camera System | Camera Selection | `adapted` | `always` | `capture_format_class` |
| 62 | `P062` | G. Camera System | Camera Character | `adapted` | `editorial, cinematic, documentary` | `sensor_rendering_character` |
| 63 | `P063` | G. Camera System | Sensor Format | `adapted` | `camera_advanced, cinematic, portrait` | `sensor_format` |
| 64 | `P064` | G. Camera System | Recording Format | `deferred` | `real_shoot` | `recording_format` |
| 65 | `P065` | G. Camera System | Codec Specification | `adapted` | `video` | `output_codec` |
| 66 | `P066` | G. Camera System | Bit Depth | `deferred` | `real_shoot, post_pro` | `bit_depth` |
| 67 | `P067` | G. Camera System | Resolution Target | `core` | `always` | `output_resolution` |
| 68 | `P068` | G. Camera System | Color Profile | `adapted` | `editorial, cinematic, commercial` | `color_profile` |
| 69 | `P069` | G. Camera System | Monitoring LUT Reference | `deferred` | `real_shoot, color_pro` | `monitoring_lut` |
| 70 | `P070` | G. Camera System | Camera Position and Settings | `core` | `always` | `camera_height, camera_angle, camera_distance` |
| 71 | `P071` | H. Lens and Optical | Lens Psychology | `conditional` | `portrait, cinematic, editorial, video` | `lens_perspective_feel` |
| 72 | `P072` | H. Lens and Optical | Focal Length | `core` | `always` | `focal_length_mm` |
| 73 | `P073` | H. Lens and Optical | Lens Type | `conditional` | `product, cinematic, macro` | `lens_type` |
| 74 | `P074` | H. Lens and Optical | Depth of Field | `core` | `always` | `aperture_fstop, dof_falloff` |
| 75 | `P075` | H. Lens and Optical | Focus Strategy | `core` | `always` | `focus_plane` |
| 76 | `P076` | H. Lens and Optical | Perspective Control | `conditional` | `architecture, product, interior` | `vertical_convergence_control` |
| 77 | `P077` | H. Lens and Optical | Bokeh Behavior | `conditional` | `shallow_dof, portrait, night` | `bokeh_character` |
| 78 | `P078` | H. Lens and Optical | Optical Texture | `conditional` | `cinematic, editorial, vintage` | `optical_microcontrast` |
| 79 | `P079` | H. Lens and Optical | Optical Filters | `conditional` | `cinematic, glare_control` | `optical_filter` |
| 80 | `P080` | H. Lens and Optical | Lens Realism Check | `core` | `always` | `optical_coherence_check` |
| 81 | `P081` | I. Lighting Intelligence | Lighting Architecture | `core` | `always` | `lighting_setup_summary` |
| 82 | `P082` | I. Lighting Intelligence | Key Light Design | `core` | `always` | `key_light_source, key_light_direction, key_light_angle` |
| 83 | `P083` | I. Lighting Intelligence | Key Light Feathering | `conditional` | `portrait, studio, fashion` | `key_feathering` |
| 84 | `P084` | I. Lighting Intelligence | Light Modifier Selection | `conditional` | `studio, product, portrait` | `light_modifier` |
| 85 | `P085` | I. Lighting Intelligence | Diffusion Control | `conditional` | `studio, portrait, daylight` | `diffusion_quality` |
| 86 | `P086` | I. Lighting Intelligence | Spill Control | `conditional` | `studio, low_key, cinematic` | `spill_control` |
| 87 | `P087` | I. Lighting Intelligence | Fill Light Logic | `core` | `always` | `fill_strategy` |
| 88 | `P088` | I. Lighting Intelligence | Negative Fill | `conditional` | `editorial, low_key, product, portrait` | `negative_fill` |
| 89 | `P089` | I. Lighting Intelligence | Rim and Back Light | `conditional` | `separation_needed, cinematic, studio` | `rim_light_motivation` |
| 90 | `P090` | I. Lighting Intelligence | Hair and Shoulder Separation Light | `conditional` | `portrait, studio, fashion` | `hair_light_spec` |
| 91 | `P091` | I. Lighting Intelligence | Background Light | `conditional` | `studio, interior, portrait` | `background_lighting` |
| 92 | `P092` | I. Lighting Intelligence | Snoot, Gobo and Pattern Projection | `conditional` | `dramatic, editorial, cinematic` | `shadow_pattern` |
| 93 | `P093` | I. Lighting Intelligence | Practical Light Integration | `conditional` | `interior, night, video` | `practical_integration` |
| 94 | `P094` | I. Lighting Intelligence | Lighting Contrast Ratio | `core` | `always` | `contrast_ratio` |
| 95 | `P095` | I. Lighting Intelligence | Color Temperature and Mixed Light | `core` | `always` | `color_temperature_k` |
| 96 | `P096` | I. Lighting Intelligence | Shadow Design | `core` | `always` | `shadow_behavior` |
| 97 | `P097` | I. Lighting Intelligence | Highlight Control | `core` | `always` | `highlight_rolloff` |
| 98 | `P098` | I. Lighting Intelligence | Light Motivation Check | `core` | `always` | `light_causality_check` |
| 99 | `P099` | I. Lighting Intelligence | Lighting Realism Verification | `core` | `always` | `lighting_field_consistency` |
| 100 | `P100` | I. Lighting Intelligence | Lighting Failure Diagnosis | `core` | `qc_phase` | `lighting_qc_diagnostics` |
| 101 | `P101` | J. Composition and Motion | Composition Geometry | `core` | `always` | `composition_rule` |
| 102 | `P102` | J. Composition and Motion | Visual Hierarchy | `core` | `always` | `focal_hierarchy` |
| 103 | `P103` | J. Composition and Motion | Shot Type and Framing | `core` | `always` | `shot_framing` |
| 104 | `P104` | J. Composition and Motion | Subject Blocking and Staging | `core` | `video, multi_subject` | `subject_blocking` |
| 105 | `P105` | J. Composition and Motion | Camera Movement Choreography | `core` | `video` | `camera_movement` |
| 106 | `P106` | J. Composition and Motion | Frame Rate Specification | `adapted` | `video` | `fps` |
| 107 | `P107` | J. Composition and Motion | Shutter Behavior and Motion Blur | `adapted` | `video, action` | `motion_blur_logic` |
| 108 | `P108` | J. Composition and Motion | Aspect Ratio Selection | `core` | `always` | `aspect_ratio` |
| 109 | `P109` | J. Composition and Motion | Crop and Safe Margins | `conditional` | `commercial, delivery, text_overlay` | `safe_margins` |
| 110 | `P110` | J. Composition and Motion | Platform Framing Adaptation | `conditional` | `multi_platform, delivery` | `platform_framing_notes` |
| 111 | `P111` | K. Color, Texture and Atmosphere | Exposure Balance | `core` | `always` | `exposure_bias` |
| 112 | `P112` | K. Color, Texture and Atmosphere | Contrast Curve | `core` | `always` | `tonal_contrast` |
| 113 | `P113` | K. Color, Texture and Atmosphere | Color Palette Architecture | `core` | `always` | `color_palette` |
| 114 | `P114` | K. Color, Texture and Atmosphere | Color Science and Skin Protection | `core` | `always` | `color_science_notes` |
| 115 | `P115` | K. Color, Texture and Atmosphere | Look and LUT Discipline | `conditional` | `editorial, cinematic` | `grade_restraint` |
| 116 | `P116` | K. Color, Texture and Atmosphere | Film Emulation Restraint | `conditional` | `film_look, editorial` | `film_character` |
| 117 | `P117` | K. Color, Texture and Atmosphere | Shadow Color Integrity | `conditional` | `editorial, cinematic, night` | `shadow_tint` |
| 118 | `P118` | K. Color, Texture and Atmosphere | Highlight Color Integrity | `conditional` | `editorial, product, studio` | `highlight_tint` |
| 119 | `P119` | K. Color, Texture and Atmosphere | Surface Texture Hierarchy | `core` | `always` | `texture_detail_hierarchy` |
| 120 | `P120` | K. Color, Texture and Atmosphere | Atmospheric Depth | `conditional` | `exterior, cinematic, video` | `atmosphere_spec` |
| 121 | `P121` | L. AI Image Production | Provider Prompt Translation | `adapted` | `always` | `provider_translation_contract` |
| 122 | `P122` | L. AI Image Production | Structured Prompt Architecture | `adapted` | `always` | `prompt_structure_sections` |
| 123 | `P123` | L. AI Image Production | Negative Constraints and Anti-AI Directives | `adapted` | `always` | `negative_constraints` |
| 124 | `P124` | L. AI Image Production | Artifact Control | `adapted` | `always` | `artifact_controls` |
| 125 | `P125` | L. AI Image Production | Model and Subject Consistency | `adapted` | `has_references, video, revision` | `consistency_strategy` |
| 126 | `P126` | L. AI Image Production | Scene Continuity Control | `adapted` | `video, multi_shot, revision` | `scene_continuity_rules` |
| 127 | `P127` | L. AI Image Production | Controlled Variation Strategy | `adapted` | `variation, revision` | `variation_scope` |
| 128 | `P128` | L. AI Image Production | Selective Edit and Preservation Mode | `adapted` | `edit_mode, preservation` | `preservation_mode, allowed_changes` |
| 129 | `P129` | L. AI Image Production | Resolution and Upscale Strategy | `adapted` | `high_res` | `target_resolution_tier` |
| 130 | `P130` | L. AI Image Production | AI Realism Pre-Flight Check | `adapted` | `always` | `anti_ai_preflight` |
| 131 | `P131` | M. Real Shoot Execution | Shot List Structuring | `adapted` | `video, multi_shot` | `video_shot_list` |
| 132 | `P132` | M. Real Shoot Execution | Lighting Diagram Logic | `adapted` | `studio, lighting_advanced` | `lighting_geometry_notes` |
| 133 | `P133` | M. Real Shoot Execution | Physical Gear List | `deferred` | `real_shoot` | `gear_list` |
| 134 | `P134` | M. Real Shoot Execution | Physical Location Scout | `deferred` | `real_shoot` | `location_scout` |
| 135 | `P135` | M. Real Shoot Execution | Production Call Sheet | `deferred` | `real_shoot` | `call_sheet` |
| 136 | `P136` | M. Real Shoot Execution | Crew Assignment | `deferred` | `real_shoot` | `crew_roles` |
| 137 | `P137` | M. Real Shoot Execution | On-Set QC Discipline | `adapted` | `always` | `generation_inspection_gate` |
| 138 | `P138` | M. Real Shoot Execution | Media Backup and Checksumming | `adapted` | `always` | `asset_sha256, storage_integrity` |
| 139 | `P139` | M. Real Shoot Execution | Continuity Supervision | `adapted` | `video, multi_shot, revision` | `continuity_checklist` |
| 140 | `P140` | M. Real Shoot Execution | Production Safety and Rights Compliance | `adapted` | `always` | `safety_and_rights_check` |
| 141 | `P141` | N. Post Production | Asset Selection and Culling | `adapted` | `multi_version, revision` | `selected_version_id` |
| 142 | `P142` | N. Post Production | Restrained Retouching Logic | `conditional` | `edit_mode, portrait, product` | `retouch_boundaries` |
| 143 | `P143` | N. Post Production | Compositing Coherence | `conditional` | `has_references, background_replace` | `compositing_edge_checks` |
| 144 | `P144` | N. Post Production | VFX and Physical Simulation Plausibility | `conditional` | `video, fx_elements` | `vfx_physics_checks` |
| 145 | `P145` | N. Post Production | Base Tonal Correction | `conditional` | `finishing, edit_mode` | `base_exposure_correction` |
| 146 | `P146` | N. Post Production | Creative Color Grade | `conditional` | `editorial, cinematic, video` | `creative_grade_intent` |
| 147 | `P147` | N. Post Production | Cross-Shot Grade Matching | `adapted` | `video, multi_shot` | `grade_continuity_notes` |
| 148 | `P148` | N. Post Production | Sharpening and Noise Consistency | `conditional` | `finishing, qc_phase` | `sharpness_noise_check` |
| 149 | `P149` | N. Post Production | Final Retouch QC | `adapted` | `qc_phase` | `finishing_qc_status` |
| 150 | `P150` | N. Post Production | Master Export Packaging | `core` | `export` | `export_format, metadata_sidecar` |
| 151 | `P151` | O. Product Ready Delivery | Platform Delivery Specification | `core` | `always` | `delivery_format, mime_type` |
| 152 | `P152` | O. Product Ready Delivery | Responsive Crop Readiness | `conditional` | `commercial, web_hero` | `crop_safe_notes` |
| 153 | `P153` | O. Product Ready Delivery | Typography Integration Space | `conditional` | `commercial, poster, text_overlay` | `typography_safe_zone` |
| 154 | `P154` | O. Product Ready Delivery | Layout Placement Fit | `conditional` | `commercial, ui_slot` | `layout_fit_notes` |
| 155 | `P155` | O. Product Ready Delivery | Brand Consistency Alignment | `conditional` | `brand, commercial` | `brand_constraints` |
| 156 | `P156` | O. Product Ready Delivery | Delivery Accessibility Check | `conditional` | `commercial, text_overlay` | `accessibility_notes` |
| 157 | `P157` | O. Product Ready Delivery | Review and Approval Handoff | `core` | `always` | `approval_status` |
| 158 | `P158` | O. Product Ready Delivery | Asset Versioning | `core` | `always` | `version_number, parent_asset_id` |
| 159 | `P159` | O. Product Ready Delivery | Controlled Revision Loop | `core` | `revision` | `revision_delta, preserved_decisions` |
| 160 | `P160` | O. Product Ready Delivery | Sanitized Provenance Handoff | `core` | `export` | `provenance_manifest` |
| 161 | `P161` | P. Quality Control and Learning | Advisory Quality Scoring | `core` | `qc_phase` | `weighted_advisory_score, confidence, inspection_coverage` |
| 162 | `P162` | P. Quality Control and Learning | Structured Failure Diagnosis | `core` | `qc_phase` | `qc_findings` |
| 163 | `P163` | P. Quality Control and Learning | Production Realism Assessment | `core` | `qc_phase` | `physical_causality_check` |
| 164 | `P164` | P. Quality Control and Learning | Visual and Temporal Coherence | `core` | `qc_phase` | `coherence_check` |
| 165 | `P165` | P. Quality Control and Learning | Emotional and Brief Alignment | `core` | `qc_phase` | `brief_alignment_check` |
| 166 | `P166` | P. Quality Control and Learning | Technical Specification Accuracy | `core` | `qc_phase` | `technical_compliance_check` |
| 167 | `P167` | P. Quality Control and Learning | Commercial Delivery Readiness | `conditional` | `qc_phase, commercial` | `delivery_readiness_notes` |
| 168 | `P168` | P. Quality Control and Learning | Rework vs Accept Decision | `core` | `qc_phase` | `recommended_next_action` |
| 169 | `P169` | P. Quality Control and Learning | Project Archive and Audit Trail | `core` | `always` | `audit_event_log` |
| 170 | `P170` | P. Quality Control and Learning | Governed Learning Feedback | `conditional` | `feedback_phase` | `human_feedback_records` |
