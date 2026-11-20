# 170 Protocol Framework Mapping

## Source of truth
The supplied Production Intelligence Engine 170 Protocol Manual is the source framework. Preserve its protocol IDs, canonical titles, layer membership, and original intent. Do not silently rewrite the source. Where the product changes or combines a procedure, label that behavior as an adaptation.

The manual is organized into these ranges:

| Layer | Protocol range | Product role |
|---|---:|---|
| A. Concept and Intent | 1–10 | Intent interpretation and creative objective |
| B. Strategy and Creative Direction | 11–20 | Direction, audience, style, and constraints |
| C. Research and Reference | 21–30 | Reference analysis and visual grounding |
| D. Production Feasibility | 31–40 | Capability, risk, and execution checks |
| E. Subject / Character / Object | 41–50 | Subject identity, attributes, and behavior |
| F. Environment and Set | 51–60 | Location, background, props, and atmosphere |
| G. Camera System | 61–70 | Camera position, movement, and capture logic |
| H. Lens and Optical | 71–80 | Focal length, depth, perspective, optical behavior |
| I. Lighting Intelligence | 81–100 | Light source, direction, quality, contrast, and exposure |
| J. Composition and Motion | 101–110 | Framing, visual hierarchy, and movement |
| K. Color, Texture and Atmosphere | 111–120 | Palette, material response, texture, mood |
| L. AI Image Production | 121–130 | Translation into image generation execution |
| M. Real Shoot Execution | 131–140 | Adapt only where useful to synthetic production planning |
| N. Post Production | 141–150 | Finishing, correction, and controlled refinement |
| O. Product Ready Delivery | 151–160 | Output requirements, formats, and handoff |
| P. Quality Control and Learning | 161–170 | Review, defect detection, feedback, and improvement |

## Disposition model
Every protocol entry must be represented in a versioned, data driven registry and assigned one disposition:
- Core: directly needed for image or video production
- Conditional: activated only when the brief or production requires it
- Adapted: original production logic translated for generated media
- Deferred: outside V1 scope or not currently actionable

Do not assign a disposition solely from the layer name. Inspect the source protocol content before finalizing individual protocol mappings.

## Activation principles
- Protocol selection is conditional, not sequential.
- The system should infer safe defaults where ambiguity has low impact.
- Ask the user only when an unknown materially changes the creative result, feasibility, cost, rights, or safety.
- Keep advanced decisions available through progressive disclosure.
- Store which protocol entries influenced each plan for traceability.

## Image activation
Image planning commonly considers concept, intent, reference, subject, environment, camera, lens, lighting, composition, color, texture, generation feasibility, finishing, delivery, and quality control. The engine must select the exact relevant protocol entries from the source registry rather than assuming every image requires every item.

## Video activation
Video requires all relevant image decisions plus temporal structure. The product must model:
- Story or sequence intent
- Shot order and duration
- Subject action and motion
- Camera movement
- Spatial and temporal continuity
- Transitions and scene changes
- Frame level constraints where supported
- Provider specific duration and generation limits

Video is not simply an image prompt with a duration field.

## Registry schema
Each source entry should include:
- protocol_id
- canonical_title
- source_layer
- source_reference
- original_description
- disposition
- activation_conditions
- image_behavior
- video_behavior
- decision_fields
- provider_translation_notes
- qc_checks
- source_confidence
- implementation_notes

## Source integrity
- Maintain a traceable mapping to the manual page or section.
- If the source text is unclear, duplicated, inconsistent, or apparently mismatched with its title, flag it for owner review.
- Do not silently correct source content.
- Distinguish source statements from engineering interpretations.
- Build a coverage report showing all 170 IDs and their current disposition.

## Implementation requirement
Milestone 0 must inspect the actual manual file and extract the full 170 protocol titles and relevant details. This document defines the mapping method and layer ranges, not a substitute for full source extraction. Do not claim the registry is complete until all 170 entries have been checked.
