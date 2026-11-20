# Decision Log

## D001: Focused image and video product
Status: Accepted
Production Studio creates image and video deliverables only. It is not a general purpose assistant.

## D002: Intelligence engine separated from generation
Status: Accepted
The Production Intelligence Engine plans and evaluates. Provider adapters execute generation.

## D003: Google first
Status: Accepted
Google is the initial provider. Image and video capabilities must be independently verified and implemented.

## D004: 170 Protocol Manual as source framework
Status: Accepted
The supplied manual is the source of truth for protocol identity. Product adaptations must be traceable and clearly labeled.

## D005: Video has a dedicated planner
Status: Accepted
Video planning includes time, shots, action, camera movement, continuity, and transitions.

## D006: No autonomous paid generation
Status: Accepted
The user must explicitly approve billable generation. No blind automatic paid retries.

## D007: Public repository security
Status: Accepted
No secrets, private media, or sensitive user data may be committed.

## D008: Stack not preselected
Status: Accepted
Inspect the repository and validate requirements before choosing a framework or infrastructure.

## D009: Quality review is advisory
Status: Accepted
The application must communicate evidence, confidence, and inspection limitations. It must not claim objective certification.

## D010: Modular Python monolith + React TypeScript workspace
Status: Accepted (Phase 0 — Verified 2026-11-19)
Backend and Level 1 CLI use Python 3.11+, FastAPI, Pydantic v2, SQLite (WAL mode with startup `PRAGMA integrity_check` and repository boundaries ready for PostgreSQL in Phase 4/5), `httpx`, `cryptography` (Fernet), Pillow, and FFmpeg/FFprobe. Frontend uses React 19, TypeScript, Vite, and Vanilla CSS semantic tokens with independently tuned Light and Dark appearances.

## D011: Verified Google generative media endpoints (Nov 2026)
Status: Accepted (Phase 0 — Verified 2026-11-19)
Because Imagen models and Veo 3.1 Preview were shut down in the Gemini Developer API, `GoogleImageAdapter` targets `gemini-nano-banana-2.1` (with `gemini-3-pro-image`, `gemini-3.1-flash-lite-image`, and legacy `gemini-2.5-flash-image`) and `GoogleVideoAdapter` targets `gemini-omni-1.2-flash` via the Gemini Interactions API (`/v1beta/interactions`). Veo 3.1 GA (`veo-3.1-generate-001`) is catalogued as conditional on Gemini Enterprise Agent Platform (Vertex AI) cloud credentials.

## D012: Pre-billing transparency takes precedence over provider secrecy
Status: Accepted (Phase 0 — Reconciles Studio Brain contradiction C-001)
Users must always see provider, model, generation settings, and available cost estimates before confirming a billable generation. Internal Studio Brain and Designer Brain methodology, prompt-assembly internals, scoring formulas, and reference repo structure remain strictly hidden from customer-facing UI and APIs.

## D013: Hard zero-dollar default spend guard and explicit local test fixture separation
Status: Accepted (Phase 0)
User daily spend cap defaults to `$0.00`, hard-blocking live billable Google calls until the user explicitly configures both a server-side API key and a non-zero spend cap plus confirms each request. For offline/CI workflow verification at `$0.00` spend, an explicitly badged `local_test_fixture` adapter (enabled only in development/test environments) generates deterministic real PNG/MP4 test artifacts labeled clearly as non-billable local test renders — never simulating or masquerading as Google live outputs.

## D014: Independent Production Intelligence Engine with read-only distilled Studio & Designer intelligence
Status: Accepted (Phase 0)
`prodstud` embeds a versioned, data-driven 170-Protocol Registry reconciled with `zakshub/studio`'s 170-Protocol Summary and adapts Studio Brain's Photographic Reality / Source Preservation / Forensic QC principles without importing FashionOS-specific collections, crawlers, or living-artist rosters. Designer Brain governs UI architecture, anti-monotony, companion appearances, and WCAG 2.2 AA review offline without exposing Sentinel internals to customers.

## D015: Evolutionary UI maturity tracked per phase (Levels 1–6)
Status: Accepted (Phase 0)
All core capabilities are API- and CLI-first (Level 1), exposed through a restrained asset-first MVP web workspace (Level 2), and evolved progressively through Level 6 Enterprise Platform per `docs/INTERFACE_EVOLUTION_ROADMAP.md`.

## D016: Epistemic honesty on 170-Protocol source references
Status: Accepted (Phase 0)
Until the full original manual PDF is added to the repository for page-by-page cross-checking, every protocol entry in `data/protocols_170.json` records `source_reference = "zakshub/studio:knowledge/production-intelligence/170-protocol-summary.md"` and `source_confidence = "summary_verified_pending_full_manual_page_audit"`. Adaptations are explicitly flagged.

