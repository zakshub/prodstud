# Roadmap

The complete feature scope and phase definitions live in [FEATURE_PLAN.md](FEATURE_PLAN.md). This roadmap translates those product phases into delivery milestones.

## Phase 0: Discovery and product validation — **Status: Verified (2026-11-19)**
- [x] Audit repository and confirm stack (`docs/PHASE_0_AUDIT_AND_INTEGRATION.md`, `D010`).
- [x] Inspect and reconcile the 170 Protocol framework into a data-driven versioned registry (`data/protocols_170.json`, `docs/PROTOCOL_COVERAGE.md`, `D016`).
- [x] Inspect `zakshub/studio` and `zakshub/designer` actual files and produce integration & contradiction assessment (`docs/PHASE_0_AUDIT_AND_INTEGRATION.md`, `D012`, `D014`).
- [x] Verify current official Google image (`gemini-nano-banana-2.1`) and video (`gemini-omni-1.2-flash` / Enterprise `veo-3.1-generate-001`) APIs and document Imagen/Veo-preview shutdowns (`D011`).
- [x] Produce capability matrix, cost/spend guard model (`$0.00` default cap, `D013`), architecture recommendation, threat model, and Interface Evolution Roadmap (`docs/INTERFACE_EVOLUTION_ROADMAP.md`, `D015`).

Exit gate: source manual summary inventory is traceable (`170/170` IDs), provider capabilities are verified against official Nov 2026 Google documentation, and architecture/security decisions are documented.


## Phase 1: MVP foundation
- Single user authentication and settings.
- Projects and project workspace.
- Image and video briefs.
- Reference uploads.
- Contextual protocol activation and production plans.
- Google image generation.
- Basic timed video shot planning and Google video generation.
- Explicit billable generation approval.
- Job status, asset preview, download, basic quality review, and controlled revision.
- Server side secrets and safe job handling.

Exit gate: one user can complete the full image and video production loop safely.

## Phase 2: Production Studio V1
- Verified full protocol registry and activation trace.
- Reusable templates and advanced plan controls.
- Stronger image and multi shot video workflows.
- Reference roles and continuity controls.
- Evidence based quality findings and regression tests.
- Search, tags, collections, version comparison, and bulk export.

Exit gate: dependable repeatable professional workflows for an individual user.

## Phase 3: Advanced Creator and Professional Edition
- Advanced production controls and reusable profiles.
- Subject, character, product, and environment consistency.
- Multiple provider adapters and model comparison.
- Batch and queue management, budgets, and usage history.
- Revision impact analysis and learning controls.
- Professional export presets and client review links.

Exit gate: power users can control detailed production, provider choice, volume, and delivery.

## Phase 4: Team and Studio Edition
- Organizations, shared workspaces, invitations, and roles.
- Shared asset libraries and team templates.
- Comments, annotations, approvals, assignments, and notifications.
- Workspace provider policies and shared credentials.
- Member permissions, budgets, audit trail, queues, and team usage reports.

Exit gate: teams can collaborate with controlled access, review, and cost management.

## Phase 5: Enterprise Edition
- SSO, SCIM, advanced access control, and tenant isolation.
- Security operations, retention, audit, key management, and compliance evidence.
- Approved provider and model policies.
- Brand and visual governance.
- Cost centers, chargeback, APIs, webhooks, service accounts, and storage integrations.
- Monitoring, backup, disaster recovery, and service objectives.

Exit gate: enterprise readiness validated through security, isolation, operational, and customer acceptance testing. Feature presence alone is not enterprise readiness.

## Phase 6: Enterprise Scale and Platform Ecosystem
- Provider catalogue and extensible adapters.
- Private or dedicated deployments where justified.
- Advanced routing and high volume orchestration.
- SDKs, workflow automation, custom protocol packs, and production policies.
- Evaluation pipelines and organization specific intelligence.

Exit gate: the platform can scale and extend across multiple enterprise environments without coupling its intelligence engine to a provider.

## Delivery rules
- Follow the phase sequence unless the owner explicitly reprioritizes.
- Provider dependent features remain conditional until verified against official documentation.
- Security, billing safety, and data integrity are release blockers.
- Do not begin enterprise infrastructure before the MVP workflow is validated.
- Report milestone status, changed files, tests, risks, remaining work, and completion percentage.
