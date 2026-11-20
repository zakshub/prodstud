# UX Specification

## Product experience
Design an asset first production workspace, not a chat application and not a generic AI dashboard. The main object is the project and its generated assets. Production decisions are visible when useful but do not overwhelm the user.

## Information architecture
- Projects
- Project workspace
- Create Image
- Create Video
- Production Plan
- Asset Review
- Versions
- Settings and Provider Credentials

## Project workspace
The workspace should make the current project, active brief, selected media type, latest asset, generation status, and next action immediately clear.

## Creation flow
1. Select image or video.
2. Enter a plain language brief.
3. Add references and constraints if needed.
4. Review the engine interpretation.
5. Review the production plan with progressive disclosure.
6. Confirm provider, model, estimated cost where available, and generation settings.
7. Explicitly approve generation.

## Production plan
Show a concise human readable summary first. Advanced controls may expose camera, lens, lighting, composition, motion, continuity, and other technical settings. Explain specialist terms in plain language. Show why a consequential choice was made and whether it was inferred or user specified.

## Video plan
Use a readable shot list or storyboard structure with shot order, duration, action, framing, camera movement, and continuity notes. Do not present a fake timeline editor in V1.

## Asset review
Make the generated image or video the visual focus. Keep prompt and plan metadata accessible without competing with the asset. Support version comparison and targeted revision.

## Visual direction
- Precise, restrained, editorial production tool aesthetic
- Strong typography and clear hierarchy
- Neutral surfaces with purposeful accent use
- No decorative AI gradients, glowing orbs, fake analytics, or excessive glass effects
- Avoid chat as the primary interaction pattern
- Prioritize real previews, clear controls, and useful empty states

## UX quality requirements
- Clear loading, queued, processing, succeeded, failed, and unknown states
- Keyboard accessible controls
- Responsive layouts
- Clear cost and provider disclosure before generation
- Destructive actions require confirmation
- Do not hide important provider limitations in tooltips
- No fabricated metrics or simulated generation results
