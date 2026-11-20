# Production Studio

A focused image and video production application powered by a Production Intelligence Engine and a provider adapter layer.

## Product direction

Production Studio creates image and video assets. It is not a general chatbot or a generic prompt box. The Production Intelligence Engine interprets the brief, selects relevant production decisions from the 170 Protocol framework, prepares a production plan, checks feasibility, and evaluates outputs. Generation providers execute approved requests.

## Initial provider

Google is the first provider. Image and video generation must use separately verified provider capabilities and adapters. Do not assume that Gemini text, image generation, and video generation share the same API or model capabilities.

## Core principles

- Keep production intelligence separate from provider execution.
- Do not expose API keys in the browser or commit them to this public repository.
- Require explicit user approval before billable generation.
- Do not implement the 170 protocols as a 170 question form. Activate relevant protocols contextually.
- Treat video as a timed sequence of shots with action, camera movement, continuity, and transitions, not as a still image prompt with duration appended.
- Make quality evaluation advisory and state its limitations.

## Documentation

The product requirements, protocol mapping, workflows, UX specification, architecture, provider strategy, quality system, security model, roadmap, and decision log will be maintained under `docs/`.

## Status

Repository bootstrap in progress. Implementation must begin with Milestone 0: inspect the repository, validate the architecture, and verify current official Google documentation before selecting a stack or writing provider integration code.
