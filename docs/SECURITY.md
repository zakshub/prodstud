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
