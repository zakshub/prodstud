# Antigravity Implementation Contract

## Mission
Build Production Studio as a focused image and video production application. The product combines a Production Intelligence Engine based on the supplied Production Intelligence Engine 170 Protocol Manual with provider adapters. Google is the initial generation provider.

## Read first
1. README.md
2. docs/FEATURE_PLAN.md
3. docs/PRD.md
4. docs/PROTOCOL_MAPPING.md
5. docs/WORKFLOWS.md
6. docs/UX_SPEC.md
7. docs/ARCHITECTURE.md
8. docs/PROVIDERS.md
9. docs/QUALITY_AND_EVALUATION.md
10. docs/SECURITY.md
11. docs/ROADMAP.md
12. docs/DECISIONS.md

## Non negotiable rules
- Inspect the existing repository before selecting a framework or replacing files.
- Begin with Milestone 0 only. Report the current repository state, propose the smallest viable architecture, identify unresolved decisions, and verify official Google documentation before coding provider integrations.
- Do not silently invent or alter the source manual's protocol names, IDs, or meanings. Preserve source identity. Mark interpretations as product adaptations.
- Do not turn the 170 protocols into 170 user questions. Activate relevant protocols internally and expose only decisions that materially affect the result.
- Keep the Production Intelligence Engine independent from image and video provider adapters.
- Image and video generation are separate capabilities. Verify current API endpoints, models, schemas, constraints, pricing, quotas, regions, and asynchronous job behavior from official documentation.
- Do not expose API keys in client code, browser storage, URLs, logs, screenshots, or source control.
- Never submit a billable generation without an explicit user action and confirmation.
- Never perform automatic paid retries that may duplicate charges.
- Do not claim objective quality certification. Report evaluation confidence and limitations.
- Video planning must include timed shots, action, camera behavior, continuity, transitions, and feasibility.
- Avoid generic AI dashboards, decorative gradients, fake metrics, and chat-first UX. Design an asset-first production workspace.
- Do not add unrelated product scope such as social publishing, campaign analytics, audio authoring, 3D/CGI, or a general chatbot without owner approval.

## First milestone output
Before implementation, deliver:
- Repository audit and existing stack assessment
- Official Google documentation links and capability matrix for image and video
- Proposed architecture and stack with reasons
- Risks, unknowns, and security implications
- Milestone 1 task breakdown and acceptance criteria

Wait for owner approval before starting paid provider integration or making irreversible architecture choices.

## Delivery discipline
Work in milestones. After each milestone, provide completed tasks, changed files, tests run and results, risks, remaining work, and completion percentage. Run a concise acceptance check, then continue when critical checks pass. Do not repeat long validation loops without new evidence.
