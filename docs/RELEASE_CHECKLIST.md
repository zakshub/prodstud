# PR #1 Pre-Merge Release Checklist & Baseline Verification

**Repository:** `zakshub/prodstud`
**Pull Request:** `#1` (`feat/mvp-foundation-and-roadmap` -> `main`)
**Baseline Scope:** Phase 0 (`100.0%`), Phase 1 (`100.0%`), Phase 2 Software Deliverables (`83.3%`, with `P2-7` and `P2-8` honestly marked `blocked_external`)
**Phase 3 Status:** Not started (strictly held per owner directive)
**Paid Provider Spend Incurred:** `$0.00`

---

## 1. Pre-Merge Security Sign-Off Matrix

Every critical security surface was forensically audited against the live codebase and verified via automated regression tests (`backend/tests/test_premerge_security_and_qc_audit.py`, `backend/tests/test_security_and_spend_guard.py`, `backend/tests/test_phase2_acceptance.py`):

| Security Surface | Verified Controls & Pre-Merge Hardening | Verification Evidence |
| :--- | :--- | :--- |
| **Authentication & Sessions** | Argon2id password hashing; constant-time dummy hash verification on unknown email (prevents timing enumeration); session token issued **strictly** in `HttpOnly`, `SameSite=Lax`, `Secure` (prod) cookie and omitted from JSON bodies; SHA-256 hashed server-side session storage; explicit server-side session revocation on logout; lazy expired-session pruning; Cross-Origin `Origin` CSRF middleware blocking cross-site cookie mutations (`HTTP 403`). | `routes_auth.py`, `api/app.py`, `repositories.py`, `test_premerge_security_and_qc_audit.py` |
| **API Key Storage & Redaction** | Server-side Fernet symmetric encryption (`PRODSTUD_MASTER_KEY`, ephemeral key disallowed in prod); keys never sent to browser JS, URLs, or logs; `redact_secrets()` applied to errors/diagnostics; replace/revoke endpoints implemented. | `security.py`, `routes_auth.py`, `test_security_and_spend_guard.py` |
| **Approval Signatures & Replay** | HMAC-SHA256 signed per-quote confirmation tokens binding user, plan/asset, provider, model, cost, and expiry; **atomic single-use consumption** (`UPDATE ... WHERE consumed = 0` checking `rowcount == 1`) across single, batch, and Vision QC quotes preventing concurrent approval replay (`HTTP 403`). | `policy_gate.py`, `repositories.py`, `jobs/runner.py`, `test_premerge_security_and_qc_audit.py` |
| **Spending Controls & Timeout Safety** | Default `$0.00` daily spend cap (`PRODSTUD_DEFAULT_DAILY_SPEND_CAP_USD=0.00`) blocks all billable generation, multi-output variations, batches, video extensions, and multimodal Vision QC fail-closed; **conservative spend reservation on `JobStatus.UNKNOWN` timeouts** (`record_spend` idempotent upsert per `(user_id, job_id)`) prevents repeated timeouts from bypassing the daily spend cap; zero blind automatic paid retries. | `config.py`, `policy_gate.py`, `jobs/runner.py`, `test_premerge_security_and_qc_audit.py` |
| **File Uploads & Downloads** | Bounded streaming read (`max_reference_bytes + 1` -> `HTTP 413`); Pillow magic-byte verification + `25,000,000` pixel decompression-bomb limit (`HTTP 400`); `Path.is_relative_to()` path-traversal protection blocking sibling-prefix leaks (`../assets_evil/...`); `sanitize_download_filename()` on `Content-Disposition`; ZIP archive member sanitization and collision deduplication preventing Zip Slip. | `routes_projects.py`, `asset_store.py`, `api/app.py`, `security.py`, `test_premerge_security_and_qc_audit.py` |
| **Batch Execution & Video Extension** | Batch rejects duplicate `plan_id`s and enforces max `24` total outputs per batch; video extension enforces `3–10s` step and `30s` cumulative cap; `PATCH /api/plans/{id}` preserves immutable server-owned video extension provenance (`extended_from_asset_id`, `extension_duration_s`, `source_provider_job_id`); cross-user reference attachment (`reference_ids`) and asset/project access fail closed (`400`/`404`). | `routes_production.py`, `jobs/runner.py`, `test_phase2_acceptance.py`, `test_premerge_security_and_qc_audit.py` |
| **Engine / Provider Independence** | Multimodal Vision HTTP transport isolated in `providers/google_vision_qc.py` (`GoogleVisionQCAdapter`); AST verification confirms **0 imports** from `prodstud.providers` anywhere inside `backend/src/prodstud/engine/`. | `providers/google_vision_qc.py`, `engine/vision_qc.py`, `test_premerge_security_and_qc_audit.py` |

---

## 2. Vision QC Controlled Audit Summary

- Controlled 13-case synthetic evaluation benchmark (`scripts/audit_vision_qc.py`, `$0.00` spend) documented in [`docs/VISION_QC_EVALUATION_AUDIT.md`](VISION_QC_EVALUATION_AUDIT.md).
- Confirmed both **False Positives** (valid low-key chiaroscuro and high-key white seamless backdrops tripping global clipping/edge heuristics; hallucinated multimodal preservation `<= 2.0` triggering fail-closed `rework_recommended`) and **False Negatives** (deterministic pixel forensics missing garbled brand text; 3-frame video sampling missing inter-frame glitch bursts between `0.2s`, `3.0s`, and `5.7s`; lenient multimodal grading missing micro-defects).
- Confidence ceilings (`0.60`–`0.80`) are explicitly documented as structural coverage indicators — NOT calibrated accuracy probabilities. Human visual zoom inspection and 100% full-clip video playback remain mandatory before final acceptance.

---

## 3. Permanent Product Requirements Verification

1. **Interface Evolution Roadmap (`docs/INTERFACE_EVOLUTION_ROADMAP.md`)**:
   - **Level 1 CLI:** `prodstud` (`init-db`, `audit-db`, `plan`, `generate --variations`, `batch`, `extend`, `revise`, `export`, `verify-manual`, `snapshot`, `serve`) verified without GUI dependency.
   - **Level 2–3 Web Workspace:** Asset-first 3-zone workspace (`ProjectsView`, `WorkspaceView`, `PlanView`, `ApprovalModal`, `VariationContactSheet`, `BatchModal`, `VideoExtensionModal`, `LibraryCompareView`, `ProtocolsView`, `SettingsView`) backed 100% by real API endpoints (zero fake controls or chat-first wrappers).
   - **Calibrated Dark + Companion Light Modes:** Verified via live Chromium QA (`docs/UX_ACCEPTANCE_REPORT.md`) across `1440×900` and `768×1024` viewports with `0` console/page errors and `0` WCAG 2.2 AA violations.
2. **Designer Brain & Studio Brain Separation**:
   - **Studio Brain** drives photographic reality planning, contextual 170-protocol activation, source preservation hard/soft locks, and 10-category forensic QC inside `backend/src/prodstud/engine/`.
   - **Designer Brain** governs information architecture, anti-monotony visual direction, independently tuned dark/light tokens, and WCAG 2.2 AA acceptance criteria.
   - **Zero Private Methodology Leakage:** Automated test confirms `frontend/src/` contains zero references to private intelligence repositories or internal methodology terms (`zakshub/studio`, `zakshub/designer`, `Designer Brain`, `Studio Brain`, `Operating Constitution`).

---

## 4. Release Checklist

### Ready & Verified (Software Baseline)
- [x] Complete PR #1 diff inspected at latest `HEAD` commit.
- [x] All automated backend tests pass (`40 passed` in `pytest backend/tests`).
- [x] Frontend TypeScript typecheck (`npm run typecheck`) and production bundle (`npm run build`) pass cleanly.
- [x] Live headless Chromium browser QA passes (`0` console/page errors, `0` WCAG label/overflow regressions, Dark & Light themes, `HttpOnly` cookie session + CSRF guard active).
- [x] `scripts/audit_vision_qc.py` runs deterministically (`13` cases, `$0.00` spend) and `docs/VISION_QC_EVALUATION_AUDIT.md` documents FP/FN/confidence/human-review rules.
- [x] `scripts/verify_tracker.py` confirms `0.0%` drift (`44.2%` overall; Phase 0 `100.0%`, Phase 1 `100.0%`, Phase 2 `83.3%`).
- [x] `scripts/live_google_smoke_test.py --dry-run` passes at `$0.00` spend; paid provider calls remain strictly disabled unless explicitly authorized.
- [x] `data/protocols_170.json` maintains `170/170` entries at `summary_verified_pending_full_manual_page_audit` with `0` fabricated `source_manual_page` values.
- [x] GitHub Actions checks (`backend-test`, `frontend-build`) verified green on the latest `HEAD` commit SHA.

### Remaining Blockers (Owner Input Required)
- [ ] **`P2-7` — Live Google Provider Smoke Test (`blocked_external`):** Requires owner-supplied `GEMINI_API_KEY` + explicit authorization to run 1 live image (`gemini-nano-banana-2.1`, `~$0.034–$0.050`) and 1 live video (`gemini-omni-1.2-flash`, `~$0.20–$0.50`) via `scripts/live_google_smoke_test.py`. Until executed, Google adapters and live Gemini Vision QC remain **contract-tested via mocked HTTP only**.
- [ ] **`P2-8` — Original 170-Protocol Manual PDF Page-by-Page Audit (`blocked_external`):** Requires owner to supply the original PDF and execute `scripts/verify_manual_pages.py --source <manual.pdf> --update-registry`.

### Deployment Readiness Notes (Non-Blocking for Local/Dev Merge, Required Before Public Production Hosting)
- Set explicit persistent `PRODSTUD_ENV=production`, strong `PRODSTUD_MASTER_KEY`, HTTPS/TLS termination (`Secure` session cookies), and explicit `PRODSTUD_ALLOWED_ORIGINS` before exposing outside localhost.
- Add per-IP / per-user API rate limiting at reverse proxy or middleware before multi-user public hosting (scheduled in Phase 4/5).
