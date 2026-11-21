# Security and Privacy

## Public repository
This repository is public. Never commit API keys, access tokens, passwords, private media, personal data, production credentials, or sensitive provider responses.

## API credentials
- Accept keys only through a secure server side flow.
- Store credentials in a secret manager or encrypted server side store.
- Never expose secrets to browser JavaScript or client storage.
- Redact secrets from logs and diagnostics.
- Allow users to replace and revoke credentials.

## User media
- Validate file type, size, and content.
- Use private storage by default.
- Use time limited access URLs where appropriate.
- Define deletion and retention behavior.
- Do not use uploaded references for unrelated training or purposes.

## Generation approval
Show provider, model, request settings, and available cost information before submission. Require an explicit confirmation for billable generation.

## Reliability and billing safety
Do not blindly retry requests after timeouts. Resolve provider job status when possible. Record an unknown state when the outcome cannot be determined.

## Application security
Milestone 0 must identify authentication, authorization, input validation, rate limiting, dependency security, and deployment requirements based on the actual stack. Do not assume a public repository means the deployed application should be public.

## Implemented controls (Phase 1–2 baseline)
- **Authentication & Sessions:** Argon2id password hashing with constant-time dummy verification on unknown emails; session tokens are delivered strictly inside `HttpOnly`, `SameSite=Lax`, `Secure` (production) cookies (never returned in JSON bodies), stored hashed (SHA-256) server-side, revoked on logout, and lazily pruned on expiry.
- **CSRF & Headers:** Cross-origin `Origin` guard rejects forged cookie-authenticated mutations (`POST`/`PATCH`/`PUT`/`DELETE`) with `HTTP 403`; responses set strict `Content-Security-Policy`, `X-Content-Type-Options: nosniff`, `X-Frame-Options: DENY`, and `Referrer-Policy: no-referrer`.
- **Encrypted Key Vault & Redaction:** Provider API keys are encrypted at rest via server-side Fernet (`PRODSTUD_MASTER_KEY`, required in production) and redacted from error messages and audit payloads.
- **Spend Guard & Atomic Approvals:** Default `$0.00` daily spend cap blocks billable image, variation, batch, video extension, and multimodal Vision QC calls unless explicitly authorized; HMAC-signed quotes are consumed atomically (`UPDATE ... WHERE consumed = 0`) preventing concurrent replay; `JobStatus.UNKNOWN` timeouts conservatively reserve estimated spend to prevent cap bypass and never trigger automatic paid retries.
- **Media, Path & Provenance Safety:** Bounded upload streaming (`HTTP 413`), Pillow magic-byte and `25MP` decompression-bomb checks (`HTTP 400`), `Path.is_relative_to()` traversal protection, sanitized `Content-Disposition` filenames, Zip Slip prevention on bulk export, cross-user tenant isolation, and immutable server-owned video extension provenance on `PATCH /api/plans/{id}`.
- **Audit Verification:** See [`docs/RELEASE_CHECKLIST.md`](RELEASE_CHECKLIST.md) and `backend/tests/test_premerge_security_and_qc_audit.py`.

