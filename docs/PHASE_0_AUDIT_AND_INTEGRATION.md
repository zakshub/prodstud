# Phase 0: Repository Audit, Intelligence Integration Assessment & Provider Verification

**Verification Date:** 2026-11-19  
**Status:** Completed (Baseline Established for Phase 1 MVP Implementation)  
**Scope:** `zakshub/prodstud` (primary), `zakshub/studio` (Studio Brain reference), `zakshub/designer` (Designer Brain reference), and Official Google Generative Media APIs.

---

## 1. Repository Audit

### 1.1 `zakshub/prodstud` (Primary Repository)
- **State before Milestone 0:** Documentation-only bootstrap repository on `main` (`60db3a4`).
- **Files present:** `AGENTS.md`, `README.md`, and 11 specification documents under `docs/` (`ARCHITECTURE.md`, `DECISIONS.md`, `FEATURE_PLAN.md`, `PRD.md`, `PROTOCOL_MAPPING.md`, `PROVIDERS.md`, `QUALITY_AND_EVALUATION.md`, `ROADMAP.md`, `SECURITY.md`, `UX_SPEC.md`, `WORKFLOWS.md`).
- **Application code / tests / infrastructure:** None. Stack was explicitly left unpreselected (`D008`).
- **Source Manual Availability Finding (Epistemic Integrity):** The full PDF/text of the original "Production Intelligence Engine 170 Protocol Manual" is not committed inside `zakshub/prodstud`. However, `zakshub/studio` (`knowledge/production-intelligence/170-protocol-summary.md`) preserves the canonical 16-layer structure (Layers A–P) and all 170 protocol names/topics. Per `docs/PROTOCOL_MAPPING.md`, all 170 entries are materialized into `data/protocols_170.json` with explicit `source_reference` pointing to `zakshub/studio:knowledge/production-intelligence/170-protocol-summary.md` and `source_confidence = "summary_verified_pending_full_manual_page_audit"` rather than fabricating manual page numbers.

### 1.2 `zakshub/studio` (Studio Brain Reference)
- **Actual files inspected:**
  - Operating doctrine & skills: `AGENTS.md`, `SKILL.md`, `architecture/operating-constitution.md`, `architecture/orchestration.md`, `architecture/runtime-contract.md`, `architecture/model-routing.md`, `architecture/learning-loop.md`, `architecture/privacy-trade-secret-boundary.md`.
  - Canonical imagery knowledge & QC: `knowledge/production-intelligence/170-protocol-summary.md`, `knowledge/photographic-reality/photographic-reality-engine.md`, `knowledge/anti-ai-realism/anti-ai-realism.md`, `knowledge/source-preservation/source-preservation.md`, `qc/forensic-reality-qc.md`.
  - Executable backend implementation: `backend/TECH-STACK.md`, `services/intelligence-api/pyproject.toml`, `services/intelligence-api/src/fashionos_intelligence/services/` (`orchestrator.py`, `structured_rules.py`, `qc_runtime.py`, `provider_adapters.py`, `live_gemini.py`, `video_intelligence.py`).
- **Implementation assessment:** Python 3.13 / FastAPI / Pydantic v2 / SQLAlchemy modular monolith built for FashionOS (`fashionos_intelligence`). Implements strong domain principles (19 visual task modes, hard/soft source-preservation locks, Physical Causality Rule, 22 AI Tells, 10-category Forensic Reality QC fail-closed gate, structured rule conflict resolution, provider adapter protocol). However, its runtime code is coupled to FashionOS domain objects (collections, looks, living-photographer expert rosters, website intake crawlers) and its `video_intelligence.py` (46 lines) only averages already-supplied timestamps rather than planning timed shots, motion, continuity, or video generation.

### 1.3 `zakshub/designer` (Designer Brain / Sentinel Reference)
- **Actual files inspected:**
  - Identity & constitution: `README.md`, `constitution/designer-studio-contract.md`, `constitution/evidence-policy.md`, `constitution/originality-policy.md`, `constitution/review-and-quality.md`.
  - Architecture & visual intelligence: `brain/architecture.md`, `brain/brand-intelligence/decision-protocol.md`, `brain/brand-intelligence/color-intelligence.md`, `brain/brand-intelligence/anti-monotony.md`.
  - Executable backend implementation: `sentinel/engine.py`, `sentinel/studio.py`.
- **Implementation assessment:** Local Python 3.11+ SQLite-backed design judgment engine enforcing strict JSON contracts, attributed evidence, human review gates, transitive dependency staleness, and Designer–Studio handoff QC (`image_qc` vs `design_fit_qc`). Brand & Category Visual Intelligence provides the 9-step Visual Language Decision Protocol, semantic-role-first color architecture, mandatory independent Light/Dark companion appearance tuning, and the 6-axis Anti-Monotony Audit.

---

## 2. Cross-Repository Contradiction & Drift Audit

| ID | Subject | Claim A (Source) | Claim B (Source) | Resolution |
|---|---|---|---|---|
| **C-001** | Pre-billing Provider & Model Visibility | `zakshub/studio/architecture/privacy-trade-secret-boundary.md`: "Customer UI must not expose provider/model names." | `zakshub/prodstud/docs/SECURITY.md` & `UX_SPEC.md`: "Show provider, model, request settings, and available cost information before submission. Require an explicit confirmation for billable generation." | **Reconciled (`prodstud` authoritative):** Production Studio MUST transparently show provider, model, generation settings, and estimated cost before billable approval (users supply their own API keys and authorize spend). Internal Studio/Designer methodology, prompt assembly internals, hidden reasoning, private scoring weights, and reference repository structure remain strictly private. |
| **C-002** | Default Google Image Model ID | `zakshub/studio/services/live_gemini.py`: defaults to `gemini-3.1-flash-image` on `/v1/models/{model}:generateContent`. | Official Google Gemini API Changelog & Deprecations (verified 2026-11-19): `gemini-3.1-flash-image` is **deprecated**; official migration target is `gemini-nano-banana-2.1` via `v1beta/interactions` or `v1beta/models/{model}:generateContent`. | **Superseded by official primary docs:** `prodstud` uses `gemini-nano-banana-2.1` as default Google image model and records `gemini-3.1-flash-image` explicitly as deprecated. |
| **C-003** | Google Image & Video Model Names | Legacy assumptions often reference Imagen 3/4 and Veo 3.1 Preview in the Gemini Developer API. | Official Google Gemini API docs (verified 2026-11-19): **Imagen models are shut down** in Gemini API; **Veo 3.1 Preview in Gemini API was shut down October 22, 2026**. Active GA Gemini API video model is `gemini-omni-1.2-flash`; Veo 3.1 GA (`veo-3.1-generate-001`) lives on Gemini Enterprise Agent Platform (formerly Vertex AI). | **Superseded by official primary docs:** `prodstud` provider capability registry reflects live Nov 2026 models and marks shut-down models unsupported. |
| **C-004** | Video Production Planning | `zakshub/studio/services/video_intelligence.py` only computes average shot length over pre-segmented metadata. | `zakshub/prodstud/docs/DECISIONS.md` (`D005`) & `WORKFLOWS.md`: Video requires a dedicated timed shot planner modeling shots, durations, subject action, camera motion, continuity, transitions, and provider feasibility. | **Independent capability built in `prodstud`:** Dedicated `VideoShotPlanner` + `GoogleVideoAdapter` developed natively in `prodstud`. |

---

## 3. Intelligence Integration Assessment

| Source Component | Classification | Decision & Rationale |
|---|---|---|
| **Studio Brain: 170-Protocol Structure** | **Reuse & Reconcile** | Materialize all 170 IDs (`1–170`) into `data/protocols_170.json` preserving source layer membership and canonical titles; label all product-specific adaptations explicitly. |
| **Studio Brain: Photographic Reality Engine, Physical Causality Rule, 22 AI Tells, 10-Category Forensic QC, Source Preservation Hard/Soft Locks** | **Reuse & Adapt** | Generalize fashion/garment terminology into universal subject/product/character/scene production rules inside `prodstud.engine`. Preserve fail-closed critical QC gate (`<= 2.0` -> rework) while keeping all quality reports strictly advisory (`D009`). |
| **Studio Brain: Structured Rule Conflict Resolution** | **Adapt** | Implement deterministic hard-lock vs allowed-change contradiction detection inside `prodstud.engine.brief_interpreter` and `contradiction_checker`. |
| **Studio Brain: FashionOS Collections, Living-Photographer Expert Rosters, Website Harvester, Autonomous Learning Auto-Promotion** | **Do Not Import** | Outside Production Studio's brand-agnostic MVP scope and violates anti-copy / anti-bloat discipline. |
| **Studio Brain: `live_gemini.py` runtime code** | **Do Not Import Directly** | Uses deprecated `gemini-3.1-flash-image` default and lacks billable approval gates, spend caps, idempotency, and video generation. Build fresh verified `GoogleImageAdapter` & `GoogleVideoAdapter` inside `prodstud.providers`. |
| **Designer Brain: Visual Language Decision Protocol, Semantic Color Architecture, Companion Light/Dark Tuning, 6-Axis Anti-Monotony Audit, WCAG 2.2 AA Controls** | **Reuse (Design-Time Governance)** | Directly governs Production Studio's Evolutionary UI across Levels 1–6 (documented in `docs/INTERFACE_EVOLUTION_ROADMAP.md` and enforced in UI tokens and browser QA). Never exposed to end-user customers. |
| **Designer Brain: Designer–Studio Handoff Separation (`image_qc` vs `design_fit_qc`)** | **Adapt** | Separates technical/photographic media QC from brief/UX/placement fitness review in `prodstud`'s advisory Quality Review report. |
| **Designer Brain: Sentinel SQLite DB, Fixture Records, Internal CLI** | **Do Not Import** | Fictional fixtures and internal governance engine must remain strictly separated from customer-facing Production Studio runtime. |
| **Integration Topology** | **Distilled Read-Only Knowledge + Independent Core Engine (MVP–V1); Optional Service Federation Hook (Phase 5–6)** | Zero hard runtime coupling to external repositories; no duplicated monolithic services; clean `IntelligenceBridge` extension point preserved for future enterprise federation. |

---

## 4. Official Google Documentation Verification & Provider Capability Matrix

**Verified Against Official Google Documentation on:** `2026-11-19`

### 4.1 Official Documentation Links Verified
- Gemini API Models Catalogue: `https://aistudio.google.com/docs/models` (`https://ai.google.dev/gemini-api/docs/models`)
- Nano Banana Image Generation Guide: `https://aistudio.google.com/docs/image-generation` (`https://ai.google.dev/gemini-api/docs/image-generation`)
- Gemini Nano Banana 2.1 Model Card: `https://aistudio.google.com/docs/models/gemini-nano-banana-2.1`
- Gemini 3.1 Flash Image (Deprecated): `https://aistudio.google.com/docs/models/gemini-3.1-flash-image`
- Imagen Shutdown Notice: `https://ai.google.dev/gemini-api/docs/imagen`
- Video Generation in Gemini API: `https://aistudio.google.com/docs/video` (`https://ai.google.dev/gemini-api/docs/video`)
- Gemini Omni 1.2 Flash Guide & Model Specs: `https://aistudio.google.com/docs/omni` & `https://aistudio.google.com/docs/models/gemini-omni-flash`
- Veo 3.1 Gemini API Shutdown Notice: `https://aistudio.google.com/docs/veo`
- Veo 3.1 GA on Gemini Enterprise Agent Platform (Vertex AI): `https://docs.cloud.google.com/gemini-enterprise-agent-platform/models/veo/3-1-generate`
- Gemini Interactions API Reference: `https://aistudio.google.com/api-reference/interactions-api/create-interaction`
- Gemini Developer API Pricing: `https://aistudio.google.com/docs/pricing`
- Gemini API Deprecations: `https://aistudio.google.com/docs/deprecations`
- Gemini API Rate Limits, Billing, Regions & Terms: `https://aistudio.google.com/docs/rate-limits`, `https://aistudio.google.com/docs/billing`, `https://aistudio.google.com/docs/available-regions`, `https://aistudio.google.com/docs/terms`

### 4.2 Google Image Capability Matrix (Separate Adapter: `GoogleImageAdapter`)

| Model ID | Product Name | Status | API Endpoint(s) | Resolutions | Aspect Ratios | Reference Inputs | Multi-Turn / Edit | Pricing (Verified Estimates) | Known Constraints / Notes |
|---|---|---|---|---|---|---|---|---|---|
| `gemini-nano-banana-2.1` | Gemini Nano Banana 2.1 | **Supported (Recommended Default)** | `POST /v1beta/interactions` (`response_format.type="image"`) and `POST /v1beta/models/gemini-nano-banana-2.1:generateContent` | `1K` (default), `2K`, `4K` | `1:1`, `3:4`, `4:3`, `9:16`, `16:9`, `2:3`, `3:2`, `4:5`, `5:4`, `21:9`, `1:4`, `4:1`, `1:8`, `8:1` | Supported: up to **14 reference images** (up to 4 characters, 10 objects) | Supported via `previous_interaction_id` & inline image inputs | Token-billed (~`$30/1M` image output tokens; Google published equivalents: ~`$0.0336` at 1K, ~`$0.0504` at 2K, ~`$0.113` at 4K + `$1.50/1M` input tokens; verify live billing page before spend) | SynthID watermark on outputs; `generateContent` enforces 65,536 input token cap; named real individuals may trigger `IMAGE_OTHER`/`IMAGE_SAFETY` blocks. |
| `gemini-3-pro-image` | Nano Banana Pro | **Supported** | `POST /v1beta/interactions` & `:generateContent` | `1K`, `2K`, `4K` | Standard photographic ratios (`1:1`, `3:4`, `4:3`, `9:16`, `16:9`, `2:3`, `3:2`) | Supported (Text, Image) | Supported | Higher tier (~2x Flash rate; check live `aistudio.google.com/docs/pricing`) | Optimized for complex layouts & precise text rendering. |
| `gemini-3.1-flash-lite-image` | Nano Banana 2 Lite | **Supported (Fast/Low-Cost)** | `POST /v1beta/interactions` & `:generateContent` | `0.5K`, `1K`, `2K`, `4K` | Standard ratios | **Limited** (docs warn: not optimized for multi-reference or multi-turn edits) | **Unsupported / Not Recommended** | Lowest Flash-Lite tier (verify live pricing page) | Best for single-turn drafts without multi-reference preservation. |
| `gemini-2.5-flash-image` | Nano Banana (Legacy Stable) | **Supported (Deprecated — Shutdown 2027-03-15)** | `:generateContent` | `1K` default | Standard ratios | Supported | Supported | Token-billed (1,290 min output tokens/image) | Scheduled shutdown March 15, 2027; prefer `gemini-nano-banana-2.1`. |
| `gemini-3.1-flash-image` | Nano Banana 2 | **Deprecated** | `:generateContent` / `interactions` | `0.5K`–`4K` | Standard + panoramic | Supported | Supported | Deprecated | Migrate to `gemini-nano-banana-2.1`. |
| `imagen-3.0-*` / `imagen-4.*` | Imagen (Gemini API) | **Unsupported (Shut Down)** | N/A | N/A | N/A | N/A | N/A | N/A | Shut down in Gemini Developer API; disabled in capability registry. |

### 4.3 Google Video Capability Matrix (Separate Adapter: `GoogleVideoAdapter`)

| Model ID | Surface / Auth | Status | API Endpoint & Async Lifecycle | Supported Durations | Resolutions & FPS | Aspect Ratios | Reference / Interpolation / Extension | Pricing & Tier Notes |
|---|---|---|---|---|---|---|---|---|
| `gemini-omni-1.2-flash` | Gemini Developer API (`x-goog-api-key`) | **Supported (Recommended Default)** | **Interactions API:** `POST /v1beta/interactions` (async/background) -> poll `GET /v1beta/interactions/{id}` -> cancel supported | **3s to 15s** single-turn (`3s–10s` for first/last frame interpolation and per-turn extension, up to **30s total**) | `360p`, `720p`, `1080p`, `4K` at **24 FPS** (`video/mp4` with native audio) | `16:9`, `9:16`, `1:1` | Up to **6 reference images** across all durations; 1st/last frame interpolation (`3–10s`); multi-turn edit & tail extension (`previous_interaction_id`, 10s lookback) | **Paid Tier ONLY** (Free tier not supported). Exact per-second USD depends on output token rate & resolution; verify live at `aistudio.google.com/docs/pricing#gemini-omni-1.2-flash`. UI displays `Pricing unverified / dynamic token billing — check Google AI Studio billing` rather than guessing. |
| `gemini-omni-1.1-flash` | Gemini Developer API | **Transitional** | Same Interactions API | Same | Same | Same | Same | Auto-routes to `gemini-omni-1.2-flash` effective Dec 3, 2026. |
| `veo-3.1-generate-preview` (and `fast`/`lite` previews) | Gemini Developer API | **Unsupported (Shut Down 2026-10-22)** | N/A | N/A | N/A | N/A | N/A | Shut down Oct 22, 2026 in Gemini API. Disabled with migration notice. |
| `veo-3.1-generate-001` / `veo-3.1-fast-generate-001` | Gemini Enterprise Agent Platform (Vertex AI, Google Cloud OAuth/ADC) | **Provider Conditional (Enterprise Auth Required)** | `predictLongRunning` + `fetchPredictOperation` (stores MP4 in GCS bucket) | **4s, 6s, or 8s** (must be **8s** for 1080p/4K or reference images; extension adds 7s up to 30s) | `720p`, `1080p` (`4K` preview/tier-conditional) at **24 FPS**, `video/mp4` | `16:9`, `9:16` | Up to 3 reference images (8s only), first/last frame interpolation, video extension, seed (`0–4294967295`), `sampleCount` (`1–4`) | Requires GCP Project ID, OAuth/ADC, and GCS bucket; deferred to Phase 3/5 Enterprise cloud adapter. |

### 4.4 Regional, Privacy, Safety & Billing Terms Verified
- **Auth:** Server-side `x-goog-api-key` header only (never browser, never query strings).
- **Regions:** Available in Google AI Studio supported countries (`aistudio.google.com/docs/available-regions`). **EEA/EU, UK, and Switzerland require Paid Services only** (Free tier disallowed for client apps serving EEA/UK/CH users).
- **Privacy & Retention:** Paid tier prompts/media are **not** used to improve Google products per Gemini API Terms (`aistudio.google.com/docs/terms`); Free tier data may be used by Google — Production Studio discloses this clearly and defaults to Paid-tier semantics.
- **Safety & Moderation:** Google enforces `IMAGE_SAFETY`, `IMAGE_OTHER`, and Prohibited Use filters; adapters classify safety blocks cleanly without blind retries.
- **Async Timeout Safety:** Network timeouts during submission transition jobs to explicit `unknown` state; operator/user must query provider interaction status (`GET /v1beta/interactions/{id}` where ID was received) before authorizing any new submission to prevent duplicate charges.

---

## 5. Proposed Architecture & Technical Stack (Smallest Viable, Modular Monolith)

1. **Backend & Level 1 CLI (`backend/src/prodstud/`):** Python 3.11+ / FastAPI / Pydantic v2 / Uvicorn / `httpx` / `cryptography` (Fernet AES-128-CBC + HMAC-SHA256 for server-side API key encryption) / `Pillow` (deterministic image forensics & local fixture rendering) + `ffmpeg`/`ffprobe` (deterministic video forensics & local fixture rendering).
2. **Persistence (`prodstud.storage`):** SQLite in WAL mode with startup `PRAGMA integrity_check`, atomic two-phase backup snapshots (`.sha256` manifest), parameterized SQL migrations, and clean repository abstraction so PostgreSQL can replace SQLite in Phase 4/5 without rewriting domain or engine code.
3. **Production Intelligence Engine (`prodstud.engine`):** Completely independent of `prodstud.providers`. Contains the 170-Protocol Registry loader, Brief Interpreter, Contradiction & Feasibility Checker, Physically Causal Image Planner, Dedicated Timed Video Shot Planner, Targeted Revision Mapper, and Advisory Quality Reviewer.
4. **Provider Layer (`prodstud.providers`):** Strictly separated `ImageProviderAdapter` and `VideoProviderAdapter` contracts, explicit `ProviderCapabilityRegistry` (`supported` / `unsupported` / `unverified`), `PolicyEvaluationGate` + `SpendGuard` (`$0.00` default cap), `GoogleImageAdapter`, `GoogleVideoAdapter`, and a clearly badged non-billable `LocalTestFixtureAdapter` (dev/test only — never masquerades as live Google output) enabling full end-to-end verification of binary PNG/MP4 workflows at `$0.00` spend.
5. **Frontend (`frontend/`):** React 19 + TypeScript + Vite + Vanilla CSS semantic design tokens implementing both tuned **Calibrated Studio Dark** and **Archival Proofing Light** appearances, keyboard accessibility, WCAG 2.2 AA contrast, and zero chat-first or generic AI tropes.

---

## 6. Threat Model & Security Assessment

| Threat | Mitigation Implemented in Phase 1 MVP |
|---|---|
| API key leakage in browser, bundle, URLs, logs, or public Git repo | Keys accepted only over server-side `POST /api/settings/credentials`, encrypted at rest using server-managed Fernet master key (`PRODSTUD_MASTER_KEY` env or local `.prodstud_data/master.key` gitignored `0600`), masked to last 4 chars only, redacted by structured log filter, never sent back to browser. |
| Unauthorized or accidental paid generation | Two-step flow: plan creation -> explicit confirmation token bound to exact `plan_id`, `provider`, `model`, `settings_hash`, and `estimated_cost_usd` -> `PolicyEvaluationGate` + `SpendGuard` (default daily limit `$0.00`; blocks any billable provider call until user explicitly configures non-zero spend cap and confirms). |
| Duplicate charges on timeout / network blip | Every generation job persists intent and `idempotency_key` *before* external HTTP submission. Ambiguous network timeouts transition job to `unknown`, NOT `failed`. Auto-retries on billable calls are strictly prohibited (`D006`). |
| Malicious reference uploads (polyglots, oversized files, path traversal) | Strict allowlist (`image/png`, `image/jpeg`, `image/webp`), max size cap (15 MB), magic-byte + Pillow decode verification, content-addressed SHA-256 filenames inside isolated private storage directory, never served with executable headers. |
| Cross-user / unauthenticated access | Session-cookie (`HttpOnly`, `SameSite=Lax`) and CLI Bearer token auth with PBKDF2-HMAC-SHA256 salted password hashing, project ownership checks on every route, security response headers (`X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`). |
| Trade-secret / internal intelligence leakage | Customer API returns semantic product decisions, explainable rationales, and protocol titles/dispositions useful to production; internal Studio/Designer repository paths, raw prompt-assembly internals, and private scoring weights are excluded from customer responses. |

---

## 7. Milestone 1 Task Breakdown & MVP Acceptance Criteria

### Tasks
1. Materialize & validate all 170 protocols (`data/protocols_170.json`, `docs/PROTOCOL_COVERAGE.md`).
2. Implement SQLite persistence, migrations, integrity checks, atomic snapshots, auth, and Fernet credential vault.
3. Implement provider-independent Production Intelligence Engine (170-protocol contextual activation, brief interpreter, contradiction/feasibility validator, Image Planner, Dedicated Video Shot Planner, Revision Engine, Advisory Quality Reviewer with real Pillow/ffprobe forensics).
4. Implement Provider Layer (`GoogleImageAdapter`, `GoogleVideoAdapter`, `LocalTestFixtureAdapter`, `ProviderCapabilityRegistry`, `PolicyEvaluationGate`, `SpendGuard`, Async `JobService`).
5. Implement FastAPI REST API + Level 1 CLI (`prodstud`).
6. Implement Level 2 Web Workspace (React + TypeScript + Vanilla CSS, Light & Dark modes, full Image + Video end-to-end flows).
7. Execute automated tests (`pytest` + frontend build/tests) and headless Chromium visual/workflow inspection at desktop (`1440x900`) and tablet/narrow (`768x1024`) viewports.

### MVP Exit Criteria
- [ ] Single user can register/sign in, manage server-side credentials, and configure spend limits without any secret leaking to client or logs.
- [ ] User can create, rename, archive, and reopen projects with persistent history.
- [ ] User can submit an Image brief (with optional references), inspect contextual protocol activations (not 170 questions), review/edit the physically causal production plan, explicitly approve generation, track job status, preview the generated PNG, inspect advisory QC findings with limitations, perform a targeted revision preserving unaffected decisions, and download asset + metadata sidecar.
- [ ] User can submit a Video brief, review a genuine timed shot plan (shot order, duration, action, framing, camera movement, continuity, transitions, feasibility check), explicitly approve generation, track async job state, preview the playable MP4 video, inspect advisory continuity/metadata QC, revise a shot, and download asset + metadata sidecar.
- [ ] Billable provider requests are blocked when spend cap is `$0.00` or approval token is absent/mismatched; ambiguous timeouts enter `unknown` state without blind retry.
