# Production Workflows

## Shared lifecycle
1. Project setup
2. Brief capture
3. Intent and constraint interpretation
4. Protocol activation
5. Production plan
6. Feasibility and provider capability check
7. User approval
8. Generation job
9. Asset review
10. Targeted revision or acceptance
11. Export and history

## Image workflow
Capture subject, intent, context, style direction, reference assets, constraints, aspect ratio, and intended use. The engine develops a concise production plan covering only relevant subject, environment, camera, lens, lighting, composition, color, texture, and finishing decisions. It checks that the selected image model supports the requested inputs and output settings. The user approves the billable request before submission.

## Video workflow
Capture the sequence intent, subject, action, environment, style, reference assets, duration target, aspect ratio, and constraints. The engine creates a timed shot plan. Each shot records:
- Shot identifier and order
- Duration
- Visual purpose
- Subject action
- Camera framing and movement
- Environment and lighting continuity
- Transition or cut behavior
- Required reference continuity
- Provider feasibility notes

The engine checks total duration and supported generation modes. If a provider cannot generate the full sequence as planned, propose a feasible alternative and explain the tradeoff before billing.

## Reference workflow
- Accept only supported reference types and file sizes.
- Record whether a reference is for identity, style, composition, environment, product fidelity, or motion.
- Do not assume a provider preserves every reference attribute.
- Surface conflicts between references and the brief.
- Respect user supplied rights and consent requirements.

## Revision workflow
- Identify the requested change.
- Map it to affected production decisions.
- Preserve unaffected approved decisions.
- Show the expected impact and any provider limitation.
- Require approval before a new billable generation.

## Failure recovery
- Distinguish validation, provider rejection, timeout, moderation, quota, network, and internal errors.
- Show whether the provider may have accepted the request before retrying.
- Check job status before retrying ambiguous submissions.
- Never blindly resubmit a potentially accepted paid job.
- Preserve the brief and approved plan after failure.

## Export workflow
Provide the original generated file where permitted, a clear filename, relevant dimensions or duration, and a small metadata record containing provider/model, creation time, and approved production settings. Never include secrets.
