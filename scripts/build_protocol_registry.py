#!/usr/bin/env python3
"""Deterministic builder and validator for the Production Studio 170-Protocol Registry.

Preserves canonical layer ranges and titles reconciled from:
- docs/PROTOCOL_MAPPING.md
- zakshub/studio:knowledge/production-intelligence/170-protocol-summary.md

All engineering adaptations for synthetic image/video production are explicitly tagged.
"""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
DATA_OUT = ROOT / "data" / "protocols_170.json"
COVERAGE_OUT = ROOT / "docs" / "PROTOCOL_COVERAGE.md"

SOURCE_REF = "zakshub/studio:knowledge/production-intelligence/170-protocol-summary.md"
SOURCE_CONFIDENCE = "summary_verified_pending_full_manual_page_audit"

# Exact 170 canonical titles mapped 1..170 across Layers A..P
# (pid, layer_code, layer_name, canonical_title, disposition, trigger_tags, decision_fields, original_desc, adaptation_note, image_behavior, video_behavior, qc_checks)
LAYERS: dict[str, tuple[str, tuple[int, int]]] = {
    "A": ("A. Concept and Intent", (1, 10)),
    "B": ("B. Strategy and Creative Direction", (11, 20)),
    "C": ("C. Research and Reference", (21, 30)),
    "D": ("D. Production Feasibility", (31, 40)),
    "E": ("E. Subject / Character / Object", (41, 50)),
    "F": ("F. Environment and Set", (51, 60)),
    "G": ("G. Camera System", (61, 70)),
    "H": ("H. Lens and Optical", (71, 80)),
    "I": ("I. Lighting Intelligence", (81, 100)),
    "J": ("J. Composition and Motion", (101, 110)),
    "K": ("K. Color, Texture and Atmosphere", (111, 120)),
    "L": ("L. AI Image Production", (121, 130)),
    "M": ("M. Real Shoot Execution", (131, 140)),
    "N": ("N. Post Production", (141, 150)),
    "O": ("O. Product Ready Delivery", (151, 160)),
    "P": ("P. Quality Control and Learning", (161, 170)),
}

RAW_PROTOCOLS: list[tuple[int, str, str, str, list[str], list[str], str]] = [
    # Layer A: Concept and Intent (1-10)
    (1, "A", "Input Interpretation", "core", ["always"], ["interpreted_objective", "media_type"], "Parse user brief and extract unambiguous production intent."),
    (2, "A", "User Intent Classification", "core", ["always"], ["task_mode", "deliverable_class"], "Classify whether request is new generation, preservation edit, product, portrait, editorial, or motion sequence."),
    (3, "A", "Problem Definition", "conditional", ["commercial", "brief_complex"], ["problem_statement"], "Clarify the visual communication problem the asset must solve."),
    (4, "A", "Output Purpose", "core", ["always"], ["output_purpose", "delivery_context"], "Define final usage context such as hero visual, product showcase, editorial still, or motion clip."),
    (5, "A", "Success Criteria", "core", ["always"], ["success_criteria"], "Establish measurable visual acceptance checks before execution."),
    (6, "A", "Target Audience", "conditional", ["commercial", "campaign", "brand"], ["target_audience"], "Align visual register and legibility to intended viewer expectations."),
    (7, "A", "Emotional Objective", "conditional", ["narrative", "editorial", "portrait", "video"], ["emotional_objective"], "Specify intended viewer emotional response without vague aesthetic buzzwords."),
    (8, "A", "Visual Intent", "core", ["always"], ["visual_intent"], "Translate abstract goals into concrete visible cues."),
    (9, "A", "Reality Level", "core", ["always"], ["reality_class"], "Select photographic reality class (documentary, commercial studio, editorial, cinematic, stylized)."),
    (10, "A", "Concept Strength", "conditional", ["brief_complex", "narrative"], ["concept_clarity_check"], "Verify the core visual idea is coherent and depictable in one frame or planned shot sequence."),

    # Layer B: Strategy and Creative Direction (11-20)
    (11, "B", "Creative Brief Structuring", "core", ["always"], ["structured_brief"], "Normalize raw prompt text into structured subject, action, setting, and constraints."),
    (12, "B", "Core Message", "conditional", ["commercial", "product", "campaign"], ["core_message"], "Ensure focal hierarchy reinforces the primary subject or product claim."),
    (13, "B", "Narrative Moment", "conditional", ["narrative", "video", "editorial"], ["narrative_beat"], "Identify the decisive moment or temporal story progression."),
    (14, "B", "Genre and World", "conditional", ["cinematic", "narrative", "video"], ["world_rules"], "Define consistent world rules so props, wardrobe, and architecture agree."),
    (15, "B", "Mood Direction", "conditional", ["editorial", "cinematic", "portrait", "video"], ["mood"], "Anchor emotional atmosphere in lighting contrast, color temperature, and pacing."),
    (16, "B", "Tone Control", "conditional", ["commercial", "editorial", "brand"], ["tone"], "Keep visual register calibrated (restrained, documentary, luxury, playful, utilitarian)."),
    (17, "B", "Art Direction", "core", ["always"], ["art_direction_summary"], "Coordinate subject styling, set geometry, color harmony, and prop discipline."),
    (18, "B", "Aesthetic Discipline", "core", ["always"], ["anti_cliche_constraints"], "Reject decorative filler and generic AI visual clichés that weaken authenticity."),
    (19, "B", "Style Boundary", "conditional", ["brand", "preservation", "reference"], ["style_boundaries"], "Define explicit boundaries on what visual treatments are disallowed."),
    (20, "B", "Originality Verification", "adapted", ["always"], ["originality_guard"], "Ensure transferable visual principles are applied without imitating living artists or protected trademarks."),

    # Layer C: Research and Reference (21-30)
    (21, "C", "Reference Collection", "conditional", ["has_references"], ["reference_manifest"], "Inventory uploaded references with checksums, dimensions, and declared roles."),
    (22, "C", "Reference Deconstruction", "conditional", ["has_references"], ["reference_attributes"], "Separate observable reference traits (lighting, material, geometry) from intent."),
    (23, "C", "Reference Fusion", "conditional", ["multi_reference"], ["reference_fusion_rules"], "Define how multiple references combine without conflicting identity, style, or lighting."),
    (24, "C", "Category Scan", "deferred", ["research_mode"], ["category_conventions"], "Benchmark visual conventions in target category; deferred to Phase 2+ research workflows."),
    (25, "C", "Visual Benchmark", "conditional", ["editorial", "commercial", "product"], ["quality_benchmark"], "Set realistic photographic quality bar matched to output purpose."),
    (26, "C", "Camera Reference Alignment", "conditional", ["has_references", "camera_specified"], ["camera_reference_notes"], "Match perspective height and framing geometry to camera reference."),
    (27, "C", "Lighting Reference Alignment", "conditional", ["has_references", "lighting_specified"], ["lighting_reference_notes"], "Extract key direction, softness, and contrast ratio from lighting reference."),
    (28, "C", "Color Reference Alignment", "conditional", ["has_references", "color_specified"], ["color_reference_notes"], "Match palette hue relationships and tonal curve without clipping skin or product truth."),
    (29, "C", "Composition Reference Alignment", "conditional", ["has_references", "composition_specified"], ["composition_reference_notes"], "Extract framing geometry and negative space structure from composition reference."),
    (30, "C", "Reference Risk and Rights Check", "core", ["has_references"], ["reference_rights_status", "reference_conflicts"], "Flag rights constraints, reference-to-brief contradictions, and provider reference caps."),

    # Layer D: Production Feasibility (31-40)
    (31, "D", "Technical Feasibility Validation", "core", ["always"], ["feasibility_status", "feasibility_warnings"], "Verify planned parameters against verified provider capability registry before billing."),
    (32, "D", "Budget Reality and Spend Guard", "adapted", ["always"], ["estimated_cost_usd", "spend_guard_status"], "Disclose verified cost estimates and enforce user daily spend cap and explicit approval."),
    (33, "D", "Time and Async Duration Planning", "adapted", ["video", "async_job"], ["expected_latency_class", "clip_duration_s"], "Validate video clip durations against provider limits (e.g., 3-15s Omni, 4/6/8s Veo)."),
    (34, "D", "Resource Allocation", "conditional", ["multi_shot", "batch"], ["execution_units"], "Account for multi-shot clip counts and reference asset limits."),
    (35, "D", "Technical Risk Assessment", "core", ["always"], ["technical_risks"], "Identify provider limitations (e.g., small text legibility, multi-subject motion drift, 65K token cap)."),
    (36, "D", "Visual Risk Assessment", "core", ["always"], ["visual_risks"], "Detect anatomy, hands, reflections, text, or complex physics hazards in brief."),
    (37, "D", "Complexity Classification", "core", ["always"], ["complexity_tier"], "Classify production complexity (low, moderate, high) to trigger appropriate review gates."),
    (38, "D", "Production Priority Ranking", "core", ["always"], ["hard_locks", "soft_locks"], "Rank non-negotiable hard locks above soft stylistic preferences."),
    (39, "D", "Backup and Alternative Plan", "conditional", ["feasibility_warning", "video_long_duration"], ["fallback_alternatives"], "Propose feasible alternatives and explicit tradeoffs when provider cannot fulfill brief verbatim."),
    (40, "D", "Scope Control", "core", ["always"], ["scope_boundaries"], "Keep plan within verified image/video capabilities and disallow unsupported scope inflation."),

    # Layer E: Subject / Character / Object (41-50)
    (41, "E", "Subject Selection", "core", ["always"], ["primary_subject"], "Define the hero subject (person, product, object, or environment) unmistakably."),
    (42, "E", "Subject Priority Hierarchy", "conditional", ["multi_subject", "product", "portrait"], ["subject_hierarchy"], "Order primary, secondary, and background subjects so focus and lighting prioritize the hero."),
    (43, "E", "Subject Psychology", "conditional", ["human_subject", "portrait", "narrative"], ["subject_psychology"], "Ground expression and posture in plausible internal state rather than stiff posing."),
    (44, "E", "Facial Expression Logic", "conditional", ["human_subject", "portrait"], ["facial_expression"], "Specify restrained, natural micro-expressions avoiding synthetic uncanny symmetry."),
    (45, "E", "Eye Direction and Gaze", "conditional", ["human_subject", "portrait"], ["eye_direction"], "Align gaze direction with camera lens or off-camera focal anchor."),
    (46, "E", "Body Language", "conditional", ["human_subject", "video"], ["body_language"], "Ensure weight distribution, shoulder slope, and kinetic momentum follow biomechanics."),
    (47, "E", "Pose Architecture", "conditional", ["human_subject", "fashion", "portrait"], ["pose_spec"], "Define stance, balance, and contact points with floor or props."),
    (48, "E", "Pose Realism Check", "conditional", ["human_subject", "fashion", "video"], ["pose_realism_checks"], "Prevent floating limbs, impossible spinal twists, and zero-gravity garment drape."),
    (49, "E", "Hand and Contact Logic", "conditional", ["human_subject", "product_held"], ["hand_contact_spec"], "Explicitly define hand placement, grip physics, and anatomical finger plausibility."),
    (50, "E", "Subject Consistency", "core", ["has_references", "video", "revision", "product"], ["subject_invariants"], "Lock immutable identity, product geometry, label text, and wardrobe invariants across revisions/shots."),

    # Layer F: Environment and Set (51-60)
    (51, "F", "Location Logic", "core", ["always"], ["location_setting"], "Place subject in a geographically and architecturally coherent location."),
    (52, "F", "Environment Design", "conditional", ["environment_rich", "cinematic", "video"], ["environment_architecture"], "Specify architectural materials, scale, and spatial layout."),
    (53, "F", "Set Dressing", "conditional", ["environment_rich", "commercial", "product"], ["set_props"], "Include purposeful props with believable wear rather than sterile showroom emptiness."),
    (54, "F", "Background Depth", "core", ["always"], ["background_separation"], "Establish clear spatial separation between subject plane and background planes."),
    (55, "F", "Foreground Layer", "conditional", ["cinematic", "editorial", "video"], ["foreground_elements"], "Use motivated foreground framing or occlusion layers for optical depth where helpful."),
    (56, "F", "Surface Materials", "core", ["always"], ["material_physics"], "Differentiate diffuse, specular, rough, translucent, metallic, and woven surface responses."),
    (57, "F", "Practical Environment Light", "conditional", ["interior", "night", "cinematic"], ["practical_lights"], "Anchor visible lamps, windows, or signage as physically causal light emitters."),
    (58, "F", "Environmental Story", "conditional", ["narrative", "editorial", "video"], ["environment_story_cues"], "Ensure environmental wear, weather, and props support the narrative moment."),
    (59, "F", "Spatial Realism", "core", ["always"], ["contact_shadows_and_scale"], "Require grounded contact shadows, ambient occlusion, and consistent perspective horizon."),
    (60, "F", "Environment Consistency", "core", ["video", "revision", "multi_shot"], ["environment_invariants"], "Preserve architecture, weather, time of day, and prop positions across shots/revisions."),

    # Layer G: Camera System (61-70)
    (61, "G", "Camera Selection", "adapted", ["always"], ["capture_format_class"], "Select photographic capture class (full-frame digital, medium format, cinema camera, documentary) for optical behavior."),
    (62, "G", "Camera Character", "adapted", ["editorial", "cinematic", "documentary"], ["sensor_rendering_character"], "Define highlight rolloff, dynamic range, and organic noise profile matched to capture class."),
    (63, "G", "Sensor Format", "adapted", ["camera_advanced", "cinematic", "portrait"], ["sensor_format"], "Model sensor size influence on field of view and depth-of-field transition."),
    (64, "G", "Recording Format", "deferred", ["real_shoot"], ["recording_format"], "Physical camera RAW/Log container specification; deferred for synthetic generation except color-pipeline reference."),
    (65, "G", "Codec Specification", "adapted", ["video"], ["output_codec"], "Map to verified video delivery container/codec (MP4 H.264/provider native MP4)."),
    (66, "G", "Bit Depth", "deferred", ["real_shoot", "post_pro"], ["bit_depth"], "10-bit/12-bit capture parameter; deferred until Phase 3 professional delivery."),
    (67, "G", "Resolution Target", "core", ["always"], ["output_resolution"], "Map to verified provider output tiers (Image: 1K/2K/4K; Video: 720p/1080p/4K where supported)."),
    (68, "G", "Color Profile", "adapted", ["editorial", "cinematic", "commercial"], ["color_profile"], "Define natural vs editorial tonal curve and highlight retention target."),
    (69, "G", "Monitoring LUT Reference", "deferred", ["real_shoot", "color_pro"], ["monitoring_lut"], "On-set monitoring LUT; deferred to Phase 3 color/look profiles."),
    (70, "G", "Camera Position and Settings", "core", ["always"], ["camera_height", "camera_angle", "camera_distance"], "Specify camera height, tilt/pitch, and physical distance to subject to govern perspective."),

    # Layer H: Lens and Optical (71-80)
    (71, "H", "Lens Psychology", "conditional", ["portrait", "cinematic", "editorial", "video"], ["lens_perspective_feel"], "Choose intimate compression vs environmental immersion based on viewer psychology."),
    (72, "H", "Focal Length", "core", ["always"], ["focal_length_mm"], "Select physically appropriate focal length (e.g., 24-35mm wide, 50mm natural, 85-135mm portrait/product compression)."),
    (73, "H", "Lens Type", "conditional", ["product", "cinematic", "macro"], ["lens_type"], "Specify prime, macro, anamorphic, or tilt-shift optical geometry when relevant."),
    (74, "H", "Depth of Field", "core", ["always"], ["aperture_fstop", "dof_falloff"], "Define realistic aperture and continuous optical depth-of-field falloff."),
    (75, "H", "Focus Strategy", "core", ["always"], ["focus_plane"], "Anchor plane of critical focus (e.g., near eye, product label, or rack-focus transition in video)."),
    (76, "H", "Perspective Control", "conditional", ["architecture", "product", "interior"], ["vertical_convergence_control"], "Prevent unintended vertical warping in architectural lines and product edges."),
    (77, "H", "Bokeh Behavior", "conditional", ["shallow_dof", "portrait", "night"], ["bokeh_character"], "Keep out-of-focus highlights optically natural and proportional to distance, never pasted Gaussian blur."),
    (78, "H", "Optical Texture", "conditional", ["cinematic", "editorial", "vintage"], ["optical_microcontrast"], "Apply restrained lens character (subtle microcontrast or halation) only when motivated."),
    (79, "H", "Optical Filters", "conditional", ["cinematic", "glare_control"], ["optical_filter"], "Model polarizer glare control or subtle diffusion filtration only when brief justifies it."),
    (80, "H", "Lens Realism Check", "core", ["always"], ["optical_coherence_check"], "Verify focal length, perspective convergence, and focus falloff do not contradict each other."),

    # Layer I: Lighting Intelligence (81-100)
    (81, "I", "Lighting Architecture", "core", ["always"], ["lighting_setup_summary"], "Establish complete coherent light field shared by subject and environment."),
    (82, "I", "Key Light Design", "core", ["always"], ["key_light_source", "key_light_direction", "key_light_angle"], "Define primary light source placement, height, direction, and motivation."),
    (83, "I", "Key Light Feathering", "conditional", ["portrait", "studio", "fashion"], ["key_feathering"], "Control falloff gradient across face or product planes via light feathering."),
    (84, "I", "Light Modifier Selection", "conditional", ["studio", "product", "portrait"], ["light_modifier"], "Specify physical modifier (softbox, octabox, scrim, bare sun, window) governing shadow edge quality."),
    (85, "I", "Diffusion Control", "conditional", ["studio", "portrait", "daylight"], ["diffusion_quality"], "Set apparent light source size to control soft vs crisp shadow transitions."),
    (86, "I", "Spill Control", "conditional", ["studio", "low_key", "cinematic"], ["spill_control"], "Use flags/grids logic to prevent unwanted light washing onto backgrounds."),
    (87, "I", "Fill Light Logic", "core", ["always"], ["fill_strategy"], "Define shadow recovery via bounce or secondary fill aligned to key motivation."),
    (88, "I", "Negative Fill", "conditional", ["editorial", "low_key", "product", "portrait"], ["negative_fill"], "Preserve sculptural shadow depth on shadow side rather than flat over-illumination."),
    (89, "I", "Rim and Back Light", "conditional", ["separation_needed", "cinematic", "studio"], ["rim_light_motivation"], "Use rim separation ONLY when a physically plausible rear source exists; forbid unmotivated AI rim glow."),
    (90, "I", "Hair and Shoulder Separation Light", "conditional", ["portrait", "studio", "fashion"], ["hair_light_spec"], "Subtle top/back edge separation matched to studio/environment light geometry."),
    (91, "I", "Background Light", "conditional", ["studio", "interior", "portrait"], ["background_lighting"], "Control background luminance separation relative to subject key exposure."),
    (92, "I", "Snoot, Gobo and Pattern Projection", "conditional", ["dramatic", "editorial", "cinematic"], ["shadow_pattern"], "Motivate projected shadow shapes (window blinds, foliage dappled light) from real geometry."),
    (93, "I", "Practical Light Integration", "conditional", ["interior", "night", "video"], ["practical_integration"], "Ensure practical lamps cast believable local pools and inverse-square falloff."),
    (94, "I", "Lighting Contrast Ratio", "core", ["always"], ["contrast_ratio"], "Specify key-to-fill ratio (e.g., 2:1 clean commercial, 4:1 editorial, 8:1 dramatic low-key)."),
    (95, "I", "Color Temperature and Mixed Light", "core", ["always"], ["color_temperature_k"], "Harmonize Kelvin values (e.g., 5600K daylight vs 3200K tungsten practicals) and motivated bounce color."),
    (96, "I", "Shadow Design", "core", ["always"], ["shadow_behavior"], "Verify shadow direction, penumbra softness, density, and grounded contact occlusion."),
    (97, "I", "Highlight Control", "core", ["always"], ["highlight_rolloff"], "Protect specular rolloff on skin, glass, metal, and white fabric without clipped plastic glare."),
    (98, "I", "Light Motivation Check", "core", ["always"], ["light_causality_check"], "Enforce Physical Causality Rule: every visible highlight and shadow must trace to a scene light source."),
    (99, "I", "Lighting Realism Verification", "core", ["always"], ["lighting_field_consistency"], "Confirm subject and background obey one unified directional light field."),
    (100, "I", "Lighting Failure Diagnosis", "core", ["qc_phase"], ["lighting_qc_diagnostics"], "Diagnose conflicting shadows, floating contact shadows, or synthetic rim glows during review."),

    # Layer J: Composition and Motion (101-110)
    (101, "J", "Composition Geometry", "core", ["always"], ["composition_rule"], "Establish intentional spatial balance (rule of thirds, centered symmetry, leading lines, negative space)."),
    (102, "J", "Visual Hierarchy", "core", ["always"], ["focal_hierarchy"], "Direct viewer eye path cleanly to primary subject first, supporting context second."),
    (103, "J", "Shot Type and Framing", "core", ["always"], ["shot_framing"], "Define exact framing (extreme close-up, close-up, medium, full-body, wide establishing)."),
    (104, "J", "Subject Blocking and Staging", "core", ["video", "multi_subject"], ["subject_blocking"], "Plan physical positions and movement paths of subjects through 3D space over time."),
    (105, "J", "Camera Movement Choreography", "core", ["video"], ["camera_movement"], "Specify motivated camera motion (locked-off, slow dolly-in, lateral track, pan, tilt, handheld) per shot."),
    (106, "J", "Frame Rate Specification", "adapted", ["video"], ["fps"], "Bind to verified video provider cadence (24 FPS cinematic standard on Omni 1.2 Flash / Veo 3.1)."),
    (107, "J", "Shutter Behavior and Motion Blur", "adapted", ["video", "action"], ["motion_blur_logic"], "Ensure motion blur agrees with subject speed and natural 180-degree shutter feel."),
    (108, "J", "Aspect Ratio Selection", "core", ["always"], ["aspect_ratio"], "Validate aspect ratio against verified model capabilities (Image: 1:1..21:9; Video: 16:9, 9:16, 1:1)."),
    (109, "J", "Crop and Safe Margins", "conditional", ["commercial", "delivery", "text_overlay"], ["safe_margins"], "Preserve breathing room around subject extremities and typography safe zones."),
    (110, "J", "Platform Framing Adaptation", "conditional", ["multi_platform", "delivery"], ["platform_framing_notes"], "Adapt framing intentionally for portrait vs widescreen without awkward head/product clipping."),

    # Layer K: Color, Texture and Atmosphere (111-120)
    (111, "K", "Exposure Balance", "core", ["always"], ["exposure_bias"], "Set overall luminance target (high-key, neutral balanced, low-key) preserving midtone fidelity."),
    (112, "K", "Contrast Curve", "core", ["always"], ["tonal_contrast"], "Define toe/shoulder tonal rolloff without crushed black blocks or washed midtones."),
    (113, "K", "Color Palette Architecture", "core", ["always"], ["color_palette"], "Define harmonious dominant, supporting, and accent hues anchored in real materials."),
    (114, "K", "Color Science and Skin Protection", "core", ["always"], ["color_science_notes"], "Protect natural skin tone reflectance and accurate product hues against heavy tinting."),
    (115, "K", "Look and LUT Discipline", "conditional", ["editorial", "cinematic"], ["grade_restraint"], "Apply subtle color grading without overdone teal-and-orange or artificial saturation."),
    (116, "K", "Film Emulation Restraint", "conditional", ["film_look", "editorial"], ["film_character"], "Keep analog grain and tonal character proportional to lighting and sensor reality class."),
    (117, "K", "Shadow Color Integrity", "conditional", ["editorial", "cinematic", "night"], ["shadow_tint"], "Keep shadow color casts physically motivated by ambient fill/sky bounce."),
    (118, "K", "Highlight Color Integrity", "conditional", ["editorial", "product", "studio"], ["highlight_tint"], "Preserve clean spectral rolloff in bright areas without neon color clipping."),
    (119, "K", "Surface Texture Hierarchy", "core", ["always"], ["texture_detail_hierarchy"], "Ensure micro-texture is sharpest at the focal plane and naturally softens with distance/DOF."),
    (120, "K", "Atmospheric Depth", "conditional", ["exterior", "cinematic", "video"], ["atmosphere_spec"], "Use motivated atmospheric cues (aerial perspective, mist, dust, rain) rather than decorative haze."),

    # Layer L: AI Image Production (121-130)
    (121, "L", "Provider Prompt Translation", "adapted", ["always"], ["provider_translation_contract"], "Translate provider-neutral Production Plan into clean target-adapter payload inside adapter boundary."),
    (122, "L", "Structured Prompt Architecture", "adapted", ["always"], ["prompt_structure_sections"], "Organize execution directives into Subject, Environment, Camera, Lens, Lighting, Color, Texture, Composition, Constraints."),
    (123, "L", "Negative Constraints and Anti-AI Directives", "adapted", ["always"], ["negative_constraints"], "Encode positive physical instructions and explicit avoidance of the 22 AI generation tells."),
    (124, "L", "Artifact Control", "adapted", ["always"], ["artifact_controls"], "Target anatomical hands, text/logo legibility, straight edges, and edge-blending coherence."),
    (125, "L", "Model and Subject Consistency", "adapted", ["has_references", "video", "revision"], ["consistency_strategy"], "Carry locked subject descriptors and reference image bindings across generations and revisions."),
    (126, "L", "Scene Continuity Control", "adapted", ["video", "multi_shot", "revision"], ["scene_continuity_rules"], "Enforce shot-to-shot spatial, lighting, wardrobe, and transition continuity."),
    (127, "L", "Controlled Variation Strategy", "adapted", ["variation", "revision"], ["variation_scope"], "Isolate requested change dimensions while keeping approved parameters fixed."),
    (128, "L", "Selective Edit and Preservation Mode", "adapted", ["edit_mode", "preservation"], ["preservation_mode", "allowed_changes"], "Distinguish strict preservation edit, selective edit, and full regeneration with explicit provider caveats."),
    (129, "L", "Resolution and Upscale Strategy", "adapted", ["high_res"], ["target_resolution_tier"], "Select native verified high-resolution tier (2K/4K) rather than destructive post-hoc sharpening."),
    (130, "L", "AI Realism Pre-Flight Check", "adapted", ["always"], ["anti_ai_preflight"], "Verify plan does not rely on banned buzzwords ('hyperrealistic, 8k, masterpiece') in place of optical physics."),

    # Layer M: Real Shoot Execution (131-140)
    (131, "M", "Shot List Structuring", "adapted", ["video", "multi_shot"], ["video_shot_list"], "Adapted for video production: produce ordered, timed shots with action, camera, lighting, and transition specs."),
    (132, "M", "Lighting Diagram Logic", "adapted", ["studio", "lighting_advanced"], ["lighting_geometry_notes"], "Adapted into structured spatial key/fill/rim placement description inside production plan."),
    (133, "M", "Physical Gear List", "deferred", ["real_shoot"], ["gear_list"], "Physical grip/truck inventory; deferred as out of scope for synthetic generation MVP."),
    (134, "M", "Physical Location Scout", "deferred", ["real_shoot"], ["location_scout"], "On-site physical permitting and sun-path scouting; deferred out of synthetic V1 scope."),
    (135, "M", "Production Call Sheet", "deferred", ["real_shoot"], ["call_sheet"], "Crew scheduling document; deferred out of synthetic V1 scope."),
    (136, "M", "Crew Assignment", "deferred", ["real_shoot"], ["crew_roles"], "Physical crew staffing; deferred out of synthetic V1 scope."),
    (137, "M", "On-Set QC Discipline", "adapted", ["always"], ["generation_inspection_gate"], "Adapted as immediate post-generation advisory inspection gate before export or acceptance."),
    (138, "M", "Media Backup and Checksumming", "adapted", ["always"], ["asset_sha256", "storage_integrity"], "Adapted into SHA-256 content-addressed private storage and atomic SQLite snapshots."),
    (139, "M", "Continuity Supervision", "adapted", ["video", "multi_shot", "revision"], ["continuity_checklist"], "Adapted as explicit video shot-to-shot continuity ledger and post-generation continuity review."),
    (140, "M", "Production Safety and Rights Compliance", "adapted", ["always"], ["safety_and_rights_check"], "Adapted into content-safety preflight, rights disclosure, and billing confirmation guardrails."),

    # Layer N: Post Production (141-150)
    (141, "N", "Asset Selection and Culling", "adapted", ["multi_version", "revision"], ["selected_version_id"], "Track version lineage and mark preferred candidate assets within project history."),
    (142, "N", "Restrained Retouching Logic", "conditional", ["edit_mode", "portrait", "product"], ["retouch_boundaries"], "Preserve natural skin pores and fabric weave; forbid plastic over-smoothing."),
    (143, "N", "Compositing Coherence", "conditional", ["has_references", "background_replace"], ["compositing_edge_checks"], "Check edge light wrap, perspective match, and ambient occlusion when placing subjects into environments."),
    (144, "N", "VFX and Physical Simulation Plausibility", "conditional", ["video", "fx_elements"], ["vfx_physics_checks"], "Check fluid, smoke, cloth, and particle motion for gravity and timing plausibility."),
    (145, "N", "Base Tonal Correction", "conditional", ["finishing", "edit_mode"], ["base_exposure_correction"], "Verify balanced white point, black point, and exposure before creative grade."),
    (146, "N", "Creative Color Grade", "conditional", ["editorial", "cinematic", "video"], ["creative_grade_intent"], "Keep grade supportive of scene light field rather than fighting physical lighting."),
    (147, "N", "Cross-Shot Grade Matching", "adapted", ["video", "multi_shot"], ["grade_continuity_notes"], "Ensure color temperature and contrast stay matched across consecutive video shots."),
    (148, "N", "Sharpening and Noise Consistency", "conditional", ["finishing", "qc_phase"], ["sharpness_noise_check"], "Flag global over-sharpening halos or uniform synthetic noise overlays."),
    (149, "N", "Final Retouch QC", "adapted", ["qc_phase"], ["finishing_qc_status"], "Verify no haloing, edge cutouts, or detail destruction occurred before delivery."),
    (150, "N", "Master Export Packaging", "core", ["export"], ["export_format", "metadata_sidecar"], "Export original generated media file with clean filename and sanitized provenance sidecar."),

    # Layer O: Product Ready Delivery (151-160)
    (151, "O", "Platform Delivery Specification", "core", ["always"], ["delivery_format", "mime_type"], "Confirm output MIME type, resolution, aspect ratio, and duration meet target specification."),
    (152, "O", "Responsive Crop Readiness", "conditional", ["commercial", "web_hero"], ["crop_safe_notes"], "Check subject placement survives standard framing crops without cutting hero elements."),
    (153, "O", "Typography Integration Space", "conditional", ["commercial", "poster", "text_overlay"], ["typography_safe_zone"], "Verify clean negative space or text legibility constraints when text/logos are required."),
    (154, "O", "Layout Placement Fit", "conditional", ["commercial", "ui_slot"], ["layout_fit_notes"], "Apply Designer-Studio handoff separation: verify asset placement fit independently from raw media QC."),
    (155, "O", "Brand Consistency Alignment", "conditional", ["brand", "commercial"], ["brand_constraints"], "Keep brand constraints scoped to runtime workspace/project without mutating universal engine rules."),
    (156, "O", "Delivery Accessibility Check", "conditional", ["commercial", "text_overlay"], ["accessibility_notes"], "Check contrast of any embedded text regions and ensure descriptive asset metadata/alt text."),
    (157, "O", "Review and Approval Handoff", "core", ["always"], ["approval_status"], "Require explicit user confirmation before billable generation and track asset acceptance state."),
    (158, "O", "Asset Versioning", "core", ["always"], ["version_number", "parent_asset_id"], "Maintain immutable parent-child version lineage from brief -> plan -> job -> asset -> revision."),
    (159, "O", "Controlled Revision Loop", "core", ["revision"], ["revision_delta", "preserved_decisions"], "Apply smallest targeted plan change while preserving unaffected approved decisions."),
    (160, "O", "Sanitized Provenance Handoff", "core", ["export"], ["provenance_manifest"], "Include provider, model, timestamp, checksum, and approved settings in export metadata; exclude secrets."),

    # Layer P: Quality Control and Learning (161-170)
    (161, "P", "Advisory Quality Scoring", "core", ["qc_phase"], ["weighted_advisory_score", "confidence", "inspection_coverage"], "Compute transparent weighted advisory score with explicit confidence and coverage limits (never objective certification)."),
    (162, "P", "Structured Failure Diagnosis", "core", ["qc_phase"], ["qc_findings"], "Record findings with severity, affected region/timestamp, observed evidence, inferred cause, and suggested fix."),
    (163, "P", "Production Realism Assessment", "core", ["qc_phase"], ["physical_causality_check"], "Evaluate whether shadows, highlights, reflections, and material responses obey physical causality."),
    (164, "P", "Visual and Temporal Coherence", "core", ["qc_phase"], ["coherence_check"], "Check still composition coherence and video temporal/continuity coherence within actual inspection limits."),
    (165, "P", "Emotional and Brief Alignment", "core", ["qc_phase"], ["brief_alignment_check"], "Measure whether generated output fulfills the structured brief objective and constraints."),
    (166, "P", "Technical Specification Accuracy", "core", ["qc_phase"], ["technical_compliance_check"], "Deterministically verify actual pixel dimensions, aspect ratio, duration, FPS, and container validity via Pillow/FFprobe."),
    (167, "P", "Commercial Delivery Readiness", "conditional", ["qc_phase", "commercial"], ["delivery_readiness_notes"], "Assess whether asset meets stated output purpose or requires targeted rework."),
    (168, "P", "Rework vs Accept Decision", "core", ["qc_phase"], ["recommended_next_action"], "Trigger fail-closed rework recommendation if critical dimensions (preservation, causality, technical spec) score <= 2.0."),
    (169, "P", "Project Archive and Audit Trail", "core", ["always"], ["audit_event_log"], "Record immutable, secret-redacted audit history for projects, plans, approvals, jobs, reviews, and exports."),
    (170, "P", "Governed Learning Feedback", "conditional", ["feedback_phase"], ["human_feedback_records"], "Capture user accept/reject feedback without auto-mutating universal intelligence rules (governed review required)."),
]


def build_registry() -> dict[str, Any]:
    assert len(RAW_PROTOCOLS) == 170, f"Expected 170 protocols, found {len(RAW_PROTOCOLS)}"
    ids = [p[0] for p in RAW_PROTOCOLS]
    assert ids == list(range(1, 171)), "Protocol IDs must be strictly contiguous 1..170"

    entries: list[dict[str, Any]] = []
    for pid, layer_code, title, disposition, triggers, fields, desc in RAW_PROTOCOLS:
        layer_name, (lo, hi) = LAYERS[layer_code]
        assert lo <= pid <= hi, f"Protocol {pid} outside layer {layer_code} bounds {lo}-{hi}"
        assert disposition in {"core", "conditional", "adapted", "deferred"}

        is_video_only = "video" in triggers and "always" not in triggers and layer_code in {"J", "M"}
        image_behavior = (
            "Not directly applied to still images unless planning storyboard stills."
            if is_video_only
            else f"Evaluates and sets {', '.join(fields)} for still-image production planning."
        )
        video_behavior = (
            f"Evaluates {', '.join(fields)} across timed shots, motion continuity, and sequence validation."
            if disposition != "deferred"
            else "Deferred out of MVP/V1 video execution scope."
        )
        provider_notes = (
            "Translated cleanly inside provider adapter boundary; never coupled to engine rules."
            if disposition != "deferred"
            else "Not sent to generation providers in current phase."
        )
        qc_checks = (
            [f"verify_{f}" for f in fields[:2]]
            if disposition != "deferred"
            else []
        )
        impl_notes = (
            f"Product adaptation: {desc}"
            if disposition == "adapted"
            else f"Source-aligned rule ({disposition}): {desc}"
        )

        entries.append(
            {
                "activation_conditions": triggers,
                "canonical_title": title,
                "decision_fields": fields,
                "disposition": disposition,
                "image_behavior": image_behavior,
                "implementation_notes": impl_notes,
                "original_description": desc,
                "protocol_code": f"P{pid:03d}",
                "protocol_id": pid,
                "provider_translation_notes": provider_notes,
                "qc_checks": qc_checks,
                "source_confidence": SOURCE_CONFIDENCE,
                "source_layer": layer_name,
                "source_reference": SOURCE_REF,
                "video_behavior": video_behavior,
            }
        )

    counts = {d: sum(1 for e in entries if e["disposition"] == d) for d in ("core", "conditional", "adapted", "deferred")}
    payload = {
        "registry_version": "1.0.0",
        "source_integrity_note": (
            "All 170 protocol IDs (1-170) and 16 layers (A-P) are reconciled with "
            "docs/PROTOCOL_MAPPING.md and zakshub/studio:knowledge/production-intelligence/170-protocol-summary.md. "
            "Full manual PDF page numbers remain pending owner upload of the source manual file."
        ),
        "total_protocols": len(entries),
        "disposition_summary": counts,
        "protocols": entries,
    }
    return payload


def write_outputs(payload: dict[str, Any]) -> str:
    DATA_OUT.parent.mkdir(parents=True, exist_ok=True)
    serialized = json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n"
    tmp = DATA_OUT.with_suffix(".json.tmp")
    tmp.write_text(serialized, encoding="utf-8")
    tmp.replace(DATA_OUT)
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()

    counts = payload["disposition_summary"]
    lines = [
        "# 170-Protocol Registry Coverage Report",
        "",
        f"- **Registry Version:** `{payload['registry_version']}`",
        f"- **Total Protocols Mapped:** `{payload['total_protocols']} / 170`",
        f"- **Registry SHA-256:** `{digest}`",
        f"- **Source Reference:** `{SOURCE_REF}`",
        f"- **Source Confidence:** `{SOURCE_CONFIDENCE}`",
        "",
        "## Disposition Summary",
        "",
        "| Disposition | Count | Meaning |",
        "|---|---:|---|",
        f"| `core` | {counts['core']} | Directly applied in core image/video production planning & QC |",
        f"| `conditional` | {counts['conditional']} | Activated contextually only when brief, references, or media mode require it |",
        f"| `adapted` | {counts['adapted']} | Source manual production procedure explicitly adapted for synthetic image/video generation |",
        f"| `deferred` | {counts['deferred']} | Intentionally outside MVP/V1 synthetic production scope (e.g., physical shoot crew/call sheets) |",
        "",
        "## Complete 170-Protocol Inventory",
        "",
        "| ID | Code | Layer | Canonical Title | Disposition | Triggers | Decision Fields |",
        "|---:|---|---|---|---|---|---|",
    ]
    for p in payload["protocols"]:
        lines.append(
            f"| {p['protocol_id']} | `{p['protocol_code']}` | {p['source_layer']} | {p['canonical_title']} | "
            f"`{p['disposition']}` | `{', '.join(p['activation_conditions'])}` | `{', '.join(p['decision_fields'])}` |"
        )

    COVERAGE_OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return digest


if __name__ == "__main__":
    registry = build_registry()
    sha = write_outputs(registry)
    print(f"Built {registry['total_protocols']} protocols -> {DATA_OUT} (sha256={sha[:16]}...)")
    print(f"Disposition summary: {registry['disposition_summary']}")
