# Interface Evolution Roadmap & Visual Direction Brief

**Governance:** Informed continuously by Designer Brain (`zakshub/designer`) visual intelligence, originality, evidence, and WCAG 2.2 AA review standards. Internal Designer Brain methodology and repository structure are strictly excluded from customer-facing UI and APIs.

---

## 1. Designer Brain 9-Section Project Visual Brief

### 1.1 Product Profile & Category Classification
- **Category:** Professional Media Production Workbench (Still Photography & Timed Motion Production).
- **Primary Task:** Create, plan, approve, inspect, revise, and export high-craft image and video deliverables.
- **Audience Sophistication:** Independent creators, commercial art directors, studio producers, and enterprise creative operations teams.
- **Trust & Risk Level:** High — users authorize paid API compute and deliver brand-critical visual assets.
- **Information Density:** Structured workbench (`Medium-High` progressive density: calm summary surface by default, precision technical controls on demand).

### 1.2 Category Cliché Traps Identified & Avoided
| Cliché Trap | Why Rejected | Production Studio Alternative |
|---|---|---|
| Dark obsidian + neon purple/violet AI gradients | Generic "AI prompt wrapper" aesthetic; distorts color perception of user imagery | Color-neutral calibrated graphite (`#131518`) + tactile cinema tungsten/amber accent (`#D98A2B`) |
| Chat-bubble primary canvas | Hides production structure, shot timing, and preservation locks inside scrolling prose | Asset-first 3-zone workbench: Project Rail, Dominant Asset/Plan Stage, Contextual Inspector |
| Glowing orbs, headline pill badges, fake KPI dashboards | Erodes professional credibility and violates `UX_SPEC.md` | Real previews, factual job states, honest telemetry, crisp 1px hairlines |
| Warm cream + near-black sidebar + emerald green house style | Flagged by Designer Brain 6-Axis Anti-Monotony Audit as repeated unrelated portfolio habit | Cool archival proofing stone (`#F4F5F7`) in Light mode; neutral neutral-grey studio slate in Dark mode; burned ochre/tungsten accent |

### 1.3 Brand Posture & 4-Tier UI Governance Classification
- **Brand Posture:** `Multi-Brand Container` + `Selective Contrast` — quiet, color-neutral architectural chrome recedes so generated photographs and video frames remain the undisputed chromatic focal point.
- **4-Tier UI Style Classification:**
  - `CORE FIT`: Calibrated Swiss Editorial Workbench, Neutral Media Darkroom / Proofing Table, Tabular Monospace Telemetry (`tabular-nums`).
  - `SUPPORTING`: Subtle hairline dividers, crisp focus outlines (`2px solid`), restrained modal elevation for high-consequence billing confirmation.
  - `EXPERIMENTAL`: None in production MVP.
  - `REJECTED`: Glassmorphism, neon brutalism, claymorphism, purple-on-dark AI gradients, decorative mesh backgrounds, fake NLE timelines.

### 1.4 Functional Surface Profile
- **Primary Layout:** Asset-First 3-Zone Production Workbench (Desktop-first `>= 1280px`, responsive collapse at `<= 1024px` and `<= 768px`).
  - Zone 1 (Left Rail, `240px`): Project switcher, mode navigation, asset history strip.
  - Zone 2 (Center Stage, fluid `1fr`): Dominant asset preview, structured production plan, timed video shot storyboard, or version comparison.
  - Zone 3 (Right Inspector, `380px`): Brief input, references, progressive technical controls, explicit billing approval gate, advisory QC findings.

### 1.5 3-Origin Reference Triangulation (Mechanisms Only — No Surface Imitation)
1. **Functional Peer (Color-Accurate Media Tools):** Capture One / DaVinci Resolve — neutral non-tinted darkroom surround that protects color judgment; monospace optical/timing readouts.
2. **Category Peer (Structured Modern Workbenches):** Linear / Figma Inspector — tight keyboard navigation, progressive disclosure panels, clear status badges without card-in-card clutter.
3. **Adjacent Domain (Archival Proofing & Print Pre-Flight):** Kodak/Hasselblad physical contact sheets & print pre-flight checklists — explicit pre-commit sign-off gates, visible inspection coverage, clean metadata sidecars.

### 1.6 Semantic Color Architecture & Independently Tuned Companion Appearances
Allocation: Canvas `65–72%`, Structural Surface `18–24%`, Interactive Brand Accent `5–8%`, Semantic Status `<5%`.

| Semantic Token | Calibrated Studio Dark (Primary) | Archival Proofing Light (Companion) | Role & Contrast Verification |
|---|---|---|---|
| `--bg-canvas` | `#131518` | `#F4F5F7` | Zero-tint proofing surround |
| `--bg-surface` | `#1B1E23` | `#FFFFFF` | Primary panels & forms |
| `--bg-elevated` | `#23272E` | `#ECEFF3` | Cards, shot rows, modals |
| `--border-subtle` | `#2E333C` | `#D4D9E1` | Crisp 1px structural borders |
| `--border-strong` | `#424956` | `#A9B2C0` | Input edges & active dividers |
| `--text-primary` | `#F1F3F5` (`>14:1` on canvas) | `#14171C` (`>15:1` on surface) | Headings & primary copy |
| `--text-secondary` | `#9CA5B4` (`>6.8:1` on surface) | `#4F5866` (`>6.6:1` on surface) | Labels, metadata, notes |
| `--accent-primary` | `#E0912E` (ink `#111316`, `>7.5:1`) | `#A65A0A` (ink `#FFFFFF`, `>5.1:1`) | Primary action & active state (Cinema Tungsten / Burned Ochre) |
| `--status-success` | `#3EB489` | `#177350` | Succeeded / Pass QC (paired with text/icon) |
| `--status-warning` | `#E6A835` | `#9A6000` | Unknown state / Advisory warning / Pending |
| `--status-danger` | `#E05A5A` | `#B82929` | Failed / Contradiction / Critical QC block |
| `--status-info` | `#5B9BD5` | `#1C5D99` | Queued / Processing / Inferred badge |

*Both appearances are independently tuned (luminance steps, border contrast, shadow vs crisp border, saturated vs deepened ochre accent) — never mechanically inverted.*

### 1.7 Typography Pairing & Grid Parameters
- **Display / UI Sans:** `IBM Plex Sans`, `Space Grotesk`, system-ui fallback — tight editorial tracking (`-0.02em` headings), single `<h1>` per view.
- **Technical / Telemetry Mono:** `IBM Plex Mono`, `JetBrains Mono`, monospace with `font-variant-numeric: tabular-nums` for focal lengths (`50mm f/2.8`), timecodes (`00:00 – 00:08`), aspect ratios (`16:9`), protocol IDs (`P081`), and spend figures (`$0.0336`).
- **Spacing Grid:** 4px base unit (`4, 8, 12, 16, 24, 32`), crisp `4px–8px` border radius (instrument precision, not bubble-pill UI).

### 1.8 6-Axis Anti-Monotony Audit Scorecard
1. **Palette Dominance:** Neutral photographic graphite / archival cool stone (distinct from warm ivory or dark violet). **PASS**
2. **Typography Voice:** Technical editorial sans + tabular monospace optics (distinct from serif luxury or rounded SaaS). **PASS**
3. **Surface Elevation:** 1px hairline luminance stepping without heavy drop shadows or glass blur. **PASS**
4. **Layout Rhythm:** Asset-first 3-zone workbench with dominant media stage. **PASS**
5. **Brand Warmth:** Calibrated studio tungsten accent strictly budgeted to `<8%`. **PASS**
6. **Density:** Progressive-disclosure workbench (summary first, precision controls expandable). **PASS**

### 1.9 WCAG 2.2 AA Compliance Matrix
- Normal text contrast `>= 4.5:1`; large text & UI controls `>= 3.0:1` across both Dark and Light appearances.
- Visible label-in-name (`WCAG 2.5.3`) and explicit programmatic `<label htmlFor>` on all form controls (`WCAG 3.3.2`).
- Keyboard navigable workflows, visible `:focus-visible` outlines (`2px solid var(--accent-primary)`), modal Escape/focus containment, `aria-live="polite"` for job status changes.
- Status never communicated by color alone (always paired with explicit status text & symbol).

---

## 2. Interface Evolution Roadmap (Level 1 through Level 6)

| Maturity Level | Product Phase | Interface Target | New Screens & Workflows | Reusable Components Introduced | Existing Screens Upgraded | Accessibility & UX Requirements | Functional Acceptance Criteria |
|---|---|---|---|---|---|---|---|
| **Level 1: CLI & Operational Foundation** | Phase 1 (Milestone 1) | Command-driven execution, diagnostics, and full API parity without GUI dependency | `prodstud` CLI (`init-db`, `register`, `project`, `plan image/video`, `generate --approve`, `job status`, `review`, `revise`, `export`, `snapshot`, `audit-db`) | Structured JSON/table CLI formatter, typed Pydantic schemas, exit-code contract | N/A (Foundational) | Deterministic machine-readable `--json` output, clear non-zero error codes, zero secrets echoed | Full image & video brief -> plan -> approval -> job -> review -> revise -> export loop executable via CLI alone |
| **Level 2: MVP Graphical Interface** | Phase 1 (Milestone 2) | Usable, asset-first desktop-first web application | Auth (Sign In / Register), Projects Hub, Project Workspace, Create Image, Create Video (Timed Shot List), Production Plan & Progressive Disclosure, Explicit Billing Approval Modal, Job Progress & Unknown-State Recovery, Asset Review & Advisory QC, Targeted Revision, Version History, Settings & API Key Vault | `AppShell`, `ThemeToggle`, `StatusBadge`, `ProjectCard`, `BriefComposer`, `ReferenceUploader`, `ProtocolPillList`, `PlanInspector`, `ShotStoryboard`, `ApprovalGateModal`, `JobStatusBanner`, `AssetStage`, `QualityReportPanel`, `RevisionDrawer`, `VersionStrip`, `CredentialVaultCard` | CLI foundation exposed identically over REST API | WCAG 2.2 AA contrast in Dark & Light modes, keyboard navigation, `aria-live` job polling, explicit cost/provider/limitation disclosure, responsive `1440px` & `768px` layouts | Single user completes full Image & Video lifecycle end-to-end in browser, downloads real assets + metadata sidecars, safely manages keys and spend cap |
| **Level 3: Advanced Production Workspace** | Phase 2 (V1) | Repeatable professional asset-first workspace | Production Templates Browser, Protocol Activation Trace Drawer, Reference Role Board (identity/style/composition/environment/product/motion), Side-by-Side Version Comparator, Asset Search/Filter/Tags/Collections/Favorites, Timestamped Video QC Findings, Bulk Export & Storage Meter | `TemplatePicker`, `ProtocolTraceTable`, `ReferenceRoleMatrix`, `VersionDiffViewer`, `AssetFilterBar`, `CollectionTagManager`, `TimestampFindingRow`, `StorageUsageMeter` | Project Workspace, Create Image, Create Video, Asset Review, Version History | Keyboard shortcuts for A/B compare, accessible filter chips, screen-reader timestamp jumps | User saves/applies reusable templates, compares any two asset versions side-by-side, filters assets by tags/collections, records human QC feedback, and bulk exports |
| **Level 4: Professional Creative Environment** | Phase 3 (Pro) | High-control multi-provider studio environment | Precision Camera/Lens/Lighting Studio Controls, Reusable Consistency Profiles (Subject/Product/Environment), Multi-Provider Model Selector & Comparison Matrix, Batch Queue & Budget Manager, Revision Impact Analyzer, Export Presets & Expiring Client Review Links | `OpticalControlDeck`, `LightingDiagramCard`, `ConsistencyProfileEditor`, `ProviderComparisonGrid`, `BatchQueueTable`, `BudgetGuardPanel`, `ClientReviewShareDialog` | Production Plan, Asset Review, Settings, Asset Library | High-density tabular keyboard navigation, clear multi-provider capability availability matrix | Power user attaches consistency profiles, compares multiple verified providers/models, runs approved batches under budget caps, and generates expiring review packages |
| **Level 5: Collaborative Studio** | Phase 4 (Team) | Multi-user studio with shared libraries & approvals | Organization Switcher, Team Member & Role Manager (`owner`, `admin`, `producer`, `creator`, `reviewer`, `viewer`), Spatial Asset Annotations & Plan Comments, Approval Routing Queue, Team Activity Feed, Shared Brand Libraries, Team Usage & Budget Dashboard | `OrgWorkspaceSwitcher`, `RolePermissionTable`, `AnnotationPinOverlay`, `ApprovalWorkflowBar`, `ActivityTimeline`, `TeamQuotaSummary` | Projects Hub, Asset Review, Settings, Asset Library | Accessible comment threading, keyboard-navigable annotation markers, clear role-restricted control states | Multiple users collaborate on a shared project with role-enforced generation permissions, review annotations, approval trails, and shared workspace credential policies |
| **Level 6: Enterprise Production Platform** | Phase 5–6 (Enterprise & Ecosystem) | Governed, extensible multi-tenant enterprise platform | Enterprise Admin Console, SSO/OIDC & SCIM Provisioning, Custom RBAC Policy Editor, Immutable Audit Log Explorer, Retention & Legal Hold Controls, Approved Model Catalogue & Brand Policy Guardrails, REST API Keys / Service Accounts / Webhooks Manager, Custom Protocol Pack Studio, Provider Catalogue & Routing Benchmark Console | `PolicyRuleBuilder`, `AuditLogExplorer`, `WebhookDeliveryInspector`, `ProtocolPackEditor`, `ProviderCatalogueCard`, `TenantIsolationStatus` | Organization Settings, Provider Layer UI, Analytics/Usage Reporting | Enterprise WCAG 2.2 AA audit compliance, high-contrast mode, full keyboard operability across tables & drawers | Enterprise admin enforces SSO, tenant isolation, approved provider catalogues, cost centers, immutable audit exports, webhooks, and custom organization protocol packs |
