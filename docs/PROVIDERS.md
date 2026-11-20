# Provider Strategy

## Initial provider
Google is the initial provider. Treat image generation and video generation as distinct capabilities with separate adapters and capability records.

## Mandatory verification before coding
Use current official Google documentation and verify:
- Product and API names
- Supported model identifiers
- Authentication and project setup
- Request and response schemas
- Image reference and editing support
- Video reference and generation modes
- Supported duration, aspect ratio, resolution, and formats
- Asynchronous operation lifecycle and status retrieval
- Regional availability
- Rate limits and quotas
- Pricing and billing behavior
- Safety and moderation behavior
- Data retention and privacy terms

Do not infer current model names or API behavior from old examples, blog posts, or conversational model capabilities. Record the official documentation URL and verification date in the implementation notes.

## Adapter boundary
Implement separate interfaces for image and video. Each adapter should expose capability discovery, request validation, submission, job status retrieval, cancellation where supported, and result retrieval. Keep Google specific schemas inside Google adapters.

## Capability registry
Represent support explicitly. A capability must be marked supported, unsupported, or unverified. Do not display controls for unverified features as if they work.

## Future providers
The architecture should allow future OpenAI or other providers through new adapters. Do not build speculative provider integrations in V1.

## Credential handling
- Credentials are entered by the user and stored server side using an appropriate secret store or encrypted persistence.
- Never put API keys in frontend bundles, browser local storage, query strings, source control, logs, or client visible error messages.
- Support credential validation without exposing the secret.
- Provide revoke and replace flows.

## Cost and retries
Show cost information only when backed by current provider data. Require explicit confirmation before a billable request. Do not automatically retry paid submissions if acceptance is uncertain.
