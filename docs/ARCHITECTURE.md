# Technical Architecture

## Architectural principle
Separate production intelligence from media generation. The engine plans and evaluates. Provider adapters submit generation jobs and retrieve assets. The application owns projects, permissions, history, and user experience.

## Logical components
1. Client application: project workspace, brief, plan review, generation approval, asset review.
2. Application API: authentication, validation, project operations, billing confirmation, job orchestration.
3. Production Intelligence Engine: intent parsing, protocol activation, plan generation, feasibility checks, revision mapping, quality interpretation.
4. Protocol Registry: versioned source mapping for all 170 protocols.
5. Provider layer: independent image and video adapters.
6. Job service: asynchronous state management, polling or callbacks, retry safety.
7. Asset service: secure upload, storage, metadata, preview, export.
8. Persistence: projects, briefs, plans, protocol traces, provider jobs, assets, revisions, audit events.

## Request lifecycle
Brief -> normalized intent -> protocol selection -> production plan -> feasibility validation -> user approval -> provider adapter -> asynchronous job -> asset persistence -> quality review -> revision or export.

## Provider neutral contracts
Define internal request and response contracts before implementing provider adapters. Keep provider specific fields inside adapter boundaries. Record model and capability versions used for every job.

## Job states
Use explicit states such as draft, awaiting_approval, submitted, queued, processing, succeeded, failed, cancelled, and unknown. Unknown is necessary when a network interruption makes submission status uncertain.

## Suggested core entities
- User
- Project
- ProductionBrief
- ReferenceAsset
- ProductionPlan
- ProtocolActivation
- ProviderCapability
- GenerationRequest
- GenerationJob
- GeneratedAsset
- QualityReview
- Revision
- AuditEvent

## Data and persistence
Inspect the repository before selecting the concrete stack. Choose the simplest stack that supports secure server side secrets, asynchronous jobs, durable project history, and media storage. Do not introduce distributed infrastructure without evidence that it is required.

## Reliability
- Use idempotency keys where supported.
- Persist request intent before provider submission.
- Distinguish a failed request from an unknown submission state.
- Do not automatically repeat a billable operation after an ambiguous timeout.
- Record provider request IDs and safe diagnostic metadata.
- Keep secrets out of logs.

## Observability
Track job lifecycle, latency, provider errors, estimated and actual usage where available, and asset persistence outcomes. Never invent analytics values.
