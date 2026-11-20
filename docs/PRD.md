# Product Requirements Document

## 1. Product definition
Production Studio is an image and video production application. It uses a Production Intelligence Engine to translate a creative brief into a feasible production plan, then uses a generation provider to create the approved media.

The product is not a general purpose AI assistant, not a text only prompt enhancer, and not a social media publishing tool.

## 2. Problem
Most generation interfaces put the burden of production knowledge on the user. Users must independently decide concept, subject, environment, camera, lens, lighting, composition, motion, continuity, output constraints, and quality checks. A better interface should guide these decisions without making the user complete a long technical questionnaire.

## 3. Product promise
Turn a creative intent into a production plan, generate an image or video through an explicitly selected and supported provider capability, inspect the result, and make controlled revisions.

## 4. Primary users
- Creative professionals who need repeatable visual production
- Product and marketing teams creating approved visual assets
- Independent creators who need production guidance without being cinematography specialists

## 5. Supported deliverables
- Still images
- Generated videos

Text is used for briefs, production decisions, shot plans, review notes, settings, and diagnostics. The creative deliverables in V1 remain images and videos.

## 6. Core experience
1. Create a project.
2. Choose Image or Video.
3. Describe the intent and provide optional references, constraints, and output requirements.
4. Engine interprets the brief and activates relevant protocols.
5. User reviews a concise production plan and consequential decisions.
6. System checks provider capability and feasibility.
7. User approves the exact billable generation request.
8. Provider generates the asset.
9. User reviews the asset and quality findings.
10. User revises a targeted part or accepts and exports the result.

## 7. V1 functional requirements

### Project and brief
- Create, rename, archive, and reopen projects.
- Store brief, media type, references, constraints, aspect ratio, and output preferences.
- Preserve project history and generation records.

### Production intelligence
- Classify intent and production complexity.
- Select relevant protocol entries contextually.
- Identify missing information only when it materially affects the result.
- Produce a structured production plan and explain consequential decisions.
- Detect contradictions and feasibility risks before generation.
- Preserve approved decisions across revisions.

### Image generation
- Use a dedicated image provider adapter.
- Translate the approved plan into provider specific inputs.
- Support only parameters verified for the selected model.
- Store provider job metadata and resulting asset.

### Video generation
- Use a dedicated video provider adapter.
- Create a timed shot plan before generation.
- Represent shot duration, subject action, camera movement, scene continuity, transitions, and constraints.
- Verify provider supported duration, aspect ratio, resolution, reference inputs, and generation mode.
- Store asynchronous job state and output asset.

### Review and revision
- Display generated assets with their production brief and settings.
- Produce advisory quality findings with evidence and confidence.
- Allow targeted revision while preserving unaffected decisions.
- Keep a version history.

### Delivery
- Download or export generated image and video assets.
- Preserve basic metadata and provenance.

## 8. Out of scope for V1
- General purpose chat assistant
- Social publishing and scheduling
- Campaign analytics
- Audio and sound design
- Full timeline video editor
- 3D/CGI authoring
- Motion graphics authoring
- Team billing and enterprise administration unless required by the selected deployment
- Autonomous generation without user approval

## 9. Non functional requirements
- Secure server side credential handling
- Clear job states and recoverable failures
- No duplicate paid requests caused by blind retries
- Accessible controls and keyboard navigation
- Responsive desktop first workspace
- Traceable production decisions and generation settings
- Provider neutral internal data contracts

## 10. Success measures
- A user can move from brief to approved production plan without needing to understand every technical term.
- A user can generate an asset and understand which settings and decisions produced it.
- Revisions change the intended attribute without unnecessarily resetting unrelated decisions.
- Failed jobs communicate cause and next action.
- Provider integrations can be replaced or extended without rewriting the intelligence engine.

## 11. Acceptance criteria
V1 is not complete until image and video flows both support project creation, structured planning, explicit cost approval, job tracking, asset review, targeted revision, and export. Unsupported provider capabilities must be clearly disabled or explained rather than simulated.
