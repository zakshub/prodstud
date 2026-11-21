# Live Google Provider Verification Protocol & Current Blocker

**Last Checked:** 2026-11-20  
**Current Status:** **CONTRACT-TESTED (MOCKED HTTP) ONLY — LIVE GOOGLE API NOT YET VERIFIED**

Production Studio maintains strict epistemic honesty: adapter endpoints, headers, request/response schemas, timeout `UNKNOWN` transitions, async polling/cancellation, multi-turn `previous_interaction_id` extension, and Spend Guard enforcement have all been verified against official November 2026 Google API documentation and deterministic mocked HTTP tests, **not** against live Google billing servers yet.

---

## 1. Exact Remaining Blocker

| Prerequisite | Current VM / Repo State | Required Owner Action |
|---|---|---|
| `GEMINI_API_KEY` (Paid Tier) | **Unset** in environment (`GEMINI_API_KEY` and `GOOGLE_API_KEY` absent) | Supply an owner-owned Gemini Developer API key (Paid Tier required for `gemini-omni-1.2-flash` video) via environment variable or Settings Vault. |
| Explicit Spend Authorization | Locked at **`$0.00` Spend Guard default** | Authorize an explicit one-time smoke-test spend cap (e.g., `$0.50`–`$1.00`) and pass `--confirm-billable`. |

---

## 2. Exact Pre-Flight Cost Disclosure (1 Image + 1 Video)

| Request | Provider & Verified Model | Target Parameters | Published Pricing / Expected Cost |
|---|---|---|---|
| 1× Still Image | `google_gemini_image` · `gemini-nano-banana-2.1` | `3:2` · `1K` · 0 references | ~\$0.0336 (output image tokens) + ~\$0.0005 (input prompt tokens @ \$1.50/1M) ≈ **~\$0.035 total** |
| 1× Short Video | `google_gemini_video` · `gemini-omni-1.2-flash` | `16:9` · `720p` · `4s` · 24 FPS | **Paid Tier ONLY — Dynamic token/per-second billing.** Exact USD figure is NOT hardcoded to avoid fabrication; verify current rate at [aistudio.google.com/docs/pricing](https://aistudio.google.com/docs/pricing) before approving. |
| Optional Vision QC | `gemini-3.5-flash-lite` | 1 image or 3 video frames | \$0.30/1M input + \$2.50/1M output ≈ **~\$0.0020–\$0.0035 per review** (opt-in only; skipped during default smoke test). |

---

## 3. Controlled Execution Procedure (`scripts/live_google_smoke_test.py`)

### Step 1 — Zero-Cost Dry Run (`$0.00`, already verified in VM)
```bash
python3 scripts/live_google_smoke_test.py --dry-run
```
Builds real Image + Video plans via `AppRuntime`, generates signed approval quotes, confirms Spend Guard blocks at `$0.00`, and exits with `$0.00` spent.

### Step 2 — Non-Billable Credential Check (`$0.00`)
```bash
export GEMINI_API_KEY="AIza..."
python3 scripts/live_google_smoke_test.py --validate-key-only
```
Calls `GET /v1beta/models/gemini-nano-banana-2.1` and `GET /v1beta/models/gemini-omni-1.2-flash` with `x-goog-api-key` header only (`$0.00`).

### Step 3 — Authorized Live Smoke Test (1 Image + 1 Video)
Only run after reviewing Step 1 cost disclosure and explicitly authorizing spend:
```bash
python3 scripts/live_google_smoke_test.py \
  --execute-live \
  --authorize-spend-usd 1.00 \
  --confirm-billable \
  --output-dir ./live_smoke_output
```
Optional image-only smoke test (`~$0.035` estimated):
```bash
python3 scripts/live_google_smoke_test.py \
  --execute-live \
  --skip-video \
  --authorize-spend-usd 0.10 \
  --confirm-billable
```

---

## 4. Verification Checklist (To Complete Once Owner Supplies Credentials)

- [ ] Non-billable key metadata check succeeds (`HTTP 200`) for both `gemini-nano-banana-2.1` and `gemini-omni-1.2-flash`.
- [ ] Live image request returns valid PNG bytes, verified dimensions, SHA-256 hash, `provider_job_id`, and advisory QC report.
- [ ] Live video request enters `processing`, polls cleanly to `succeeded` (or halts safely on `unknown` without blind retry), returns playable H.264 MP4 verified via `ffprobe`, and records `provider_job_id` ready for `previous_interaction_id` multi-turn extension.
- [ ] Error handling confirmed cleanly on invalid parameter or quota error without secret leakage in logs or audit trail.
- [ ] Update `docs/IMPLEMENTATION_STATUS.json` (`P2-LIVE-GOOGLE`) from `blocked_external` to `verified` only after live evidence is captured.
