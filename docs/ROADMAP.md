# Roadmap

The complete feature scope and phase definitions live in [FEATURE_PLAN.md](FEATURE_PLAN.md). This roadmap translates those product phases into delivery milestones.

## Phase 0: Discovery and product validation — **Status: Verified (2026-11-19)**
- [x] Audit repository and confirm stack (`docs/PHASE_0_AUDIT_AND_INTEGRATION.md`, `D010`).
- [x] Inspect and reconcile the 170 Protocol framework into a data-driven versioned registry (`data/protocols_170.json`, `docs/PROTOCOL_COVERAGE.md`, `D016`).
- [x] Inspect `zakshub/studio` and `zakshub/designer` actual files and produce integration & contradiction assessment (`docs/PHASE_0_AUDIT_AND_INTEGRATION.md`, `D012`, `D014`).
- [x] Verify current official Google image (`gemini-nano-banana-2.1`) and video (`gemini-omni-1.2-flash` / Enterprise `veo-3.1-generate-001`) APIs and document Imagen/Veo-preview shutdowns (`D011`).
- [x] Produce capability matrix, cost/spend guard model (`$0.00` default cap, `D013`), architecture recommendation, threat model, and Interface Evolution Roadmap (`docs/INTERFACE_EVOLUTION_ROADMAP.md`, `D015`).

Exit gate: source manual summary inventory is traceable (`170/170` IDs), provider capabilities are verified against official Nov 2026 Google documentation, and architecture/security decisions are documented.


## Phase 1: MVP foundation — **Status: Verified (100.0% — 2026-11-20)**
- [x] Single user authentication (with server-side session revocation on logout & CSP headers) and settings (`backend/src/prodstud/api/routes_auth.py`, `AuthView`, `SettingsView`).
- [x] Projects and asset-first 3-zone project workspace (`ProjectsView`, `WorkspaceView`).
- [x] Image and video briefs with contextual 170-protocol activation, explainable production plans, and automatic capability re-validation on plan edit/revision (`ProductionIntelligenceEngine`).
- [x] Reference uploads with MIME/magic-byte validation, roles, usage-rights confirmation, and sanitized `Content-Disposition` downloads.
- [x] Verified Google image adapter (`gemini-nano-banana-2.1`, `gemini-3-pro-image`, `gemini-3.1-flash-lite-image`; Imagen disabled) + non-billable dev/test local fixture (contract-tested via mocked HTTP).
- [x] Dedicated timed video shot planner (with inline shot editing) and verified Google video adapter (`gemini-omni-1.2-flash` Interactions API; Veo 3.1 Preview shutdown recorded; Veo 3.1 GA Enterprise marked conditional) + non-billable dev/test MP4 animatic fixture.
- [x] Explicit pre-billing generation approval quote & confirmation modal with `$0.00` default spend guard.
- [x] Durable job state tracking (including `unknown` state with zero blind paid retries), asset preview, sanitized ZIP + provenance sidecar export, advisory quality review (Pillow/FFprobe), and controlled targeted revision.
- [x] Level 1 CLI (`prodstud`) and Level 2 Web Workspace (independently tuned Calibrated Studio Dark & Archival Proofing Light themes).

Exit gate: verified via 40 automated pytest checks, CLI E2E, and live Chromium multi-viewport E2E + WCAG 2.2 QA (`1440x900` & `768x1024`).

## Phase 2: Production Studio V1 — **Status: In Progress (83.3% Verified; 2 External Owner-Input Gates Remaining — 2026-11-21)**
- [x] Verified full 170-protocol registry explorer (`ProtocolsView`) and per-plan protocol activation trace (`PlanView`).
- [x] Reusable production templates (`GET/POST /api/templates`) and reference role classification (`product`, `identity`, `style`, `composition`, `environment`, `start_frame`, `end_frame`).
- [x] Evidence-based advisory quality reports with human review feedback (`POST /api/reviews/{id}/feedback`) and representative brief regression test suite (`test_regression_and_video_async.py`).
- [x] Asset search, filters, tags, collections, favorites, side-by-side version comparison with API decision diffs (`LibraryCompareView`), storage usage visibility, and bulk ZIP export (`POST /api/projects/{id}/export-bulk`).
- [x] Multi-output image variations (`1–4` outputs with Variation Contact Sheet, Spend Guard cost scaling, and fail-closed halt on `unknown`), batch generation with combined cost approval (`POST /api/projects/{id}/batches/quote` & `/execute`), and multi-turn video extension (`POST /api/assets/{id}/extend`, `+3–10s` up to `30s` cumulative using verified `previous_interaction_id` contract).
- [x] Optional multimodal Vision QC (`POST /api/assets/{id}/review/vision/quote` & `/run`, explicitly gated behind `$0.00` Spend Guard + confirmation with honest coverage/limitations, isolated inside `providers/google_vision_qc.py`), controlled 13-case Vision QC evaluation audit (`scripts/audit_vision_qc.py`, `docs/VISION_QC_EVALUATION_AUDIT.md`), and deterministic 170-Protocol Manual page verifier tooling (`scripts/verify_manual_pages.py` & `prodstud verify-manual`).
- [x] Controlled live Google smoke test harness (`scripts/live_google_smoke_test.py`), Designer Brain UX acceptance audit (`docs/UX_ACCEPTANCE_REPORT.md`), and PR #1 Pre-Merge Security & Release Baseline (`docs/RELEASE_CHECKLIST.md`).
- [ ] **External Blocker (`P2-7`):** Execute live Google smoke test (1 image + 1 video) once owner supplies `GEMINI_API_KEY` and explicit spend authorization (`docs/LIVE_PROVIDER_VERIFICATION.md`).
- [ ] **External Blocker (`P2-8`):** Run `scripts/verify_manual_pages.py --source <manual.pdf> --update-registry` once owner supplies the original 170-Protocol Manual PDF.

Exit gate: all Phase 2 software capabilities are implemented and verified; Phase 3 remains intentionally unstarted pending owner approval of PR #1 and completion of the controlled live provider smoke test.

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
