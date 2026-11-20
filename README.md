# Production Studio

A focused image and video production workbench powered by a **170-Protocol Production Intelligence Engine** and an isolated provider adapter layer.

## Product Direction

Production Studio plans, generates, inspects, revises, and exports still images and timed video sequences. It is an asset-first production studio — not a general chatbot, generic prompt wrapper, or social publishing scheduler.

- **Production Intelligence Engine (`backend/src/prodstud/engine/`):** Provider-independent brief interpretation, contextual activation of the 170-Protocol Registry (`data/protocols_170.json`), physically causal image planning, dedicated timed video shot planning, contradiction/feasibility checks, controlled revision mapping, and advisory quality evaluation with real Pillow/FFprobe forensics.
- **Provider Layer (`backend/src/prodstud/providers/`):** Separate verified Image (`GoogleImageAdapter` targeting `gemini-nano-banana-2.1`, `gemini-3-pro-image`, `gemini-3.1-flash-lite-image`) and Video (`GoogleVideoAdapter` targeting `gemini-omni-1.2-flash` Interactions API, plus Enterprise `veo-3.1-generate-001` capability record) adapters. Shut-down models (`imagen-4`, `veo-3.1-generate-preview`) are explicitly disabled with migration guidance.
- **Security & Spend Governance:** Server-side Fernet-encrypted API key vault (`PRODSTUD_MASTER_KEY`), default `$0.00` daily spend guard (`D013`), HMAC-signed explicit per-request approval tokens, idempotency protection, `unknown` timeout state with zero blind paid retries, and secret-redacted audit logs.
- **Evolutionary Interface (`docs/INTERFACE_EVOLUTION_ROADMAP.md`):** Level 1 CLI (`prodstud`) and Level 2–3 Web Workspace (`frontend/`) with independently calibrated **Calibrated Studio Dark** and **Archival Proofing Light** appearances.

## Quickstart (Local Development)

### 1. Backend & Level 1 CLI
```bash
uv venv .venv --python 3.11
uv pip install --python .venv/bin/python -e "backend[dev]"

# Initialize and verify database integrity
.venv/bin/prodstud init-db
.venv/bin/prodstud audit-db

# Run backend automated test suite (21 tests)
.venv/bin/pytest backend/tests -v
```

### 2. Frontend Build & Full-Stack Server
```bash
cd frontend
npm install
npm run build
cd ..

# Serve API + compiled Web Workspace on http://127.0.0.1:8000
.venv/bin/prodstud serve --host 127.0.0.1 --port 8000
```

> **Zero-Dollar Default Safety:** Newly registered accounts start with a `$0.00` daily spend cap. In `development` / `test` mode, an explicitly badged non-billable `local_test_fixture` adapter lets you verify the full Image (PNG) and Video (H.264 MP4) lifecycle locally at `$0.00`. To run live Google generations, add your Google Gemini API key in **Settings -> Server-Side Provider Credentials** and explicitly raise your daily spend cap.

## Documentation

- [Phase 0 Repository Audit, Intelligence Integration & Verified Google Capability Matrix](docs/PHASE_0_AUDIT_AND_INTEGRATION.md)
- [Interface Evolution Roadmap & Designer Brain Visual Brief](docs/INTERFACE_EVOLUTION_ROADMAP.md)
- [170-Protocol Registry Coverage Report](docs/PROTOCOL_COVERAGE.md)
- [Phased Feature Plan: MVP to Enterprise](docs/FEATURE_PLAN.md)
- [Delivery Roadmap](docs/ROADMAP.md)
- [Decision Log (`D001–D016`)](docs/DECISIONS.md)
- [Architecture](docs/ARCHITECTURE.md), [Providers](docs/PROVIDERS.md), [Quality & Evaluation](docs/QUALITY_AND_EVALUATION.md), [Security](docs/SECURITY.md), [UX Spec](docs/UX_SPEC.md), [Workflows](docs/WORKFLOWS.md)
