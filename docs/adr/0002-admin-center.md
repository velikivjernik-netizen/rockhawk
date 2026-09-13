# ADR 0002 — Administration Center

## Status

Accepted

## Context

Operators need a first-class `/admin` surface for branding, AI providers, prompts, review floors, and related settings.

## Decision

- `/admin` is a protected React route. Every mutating admin API requires `role=admin` server-side.
- The UI is a dense, searchable category navigator driven by the registry.
- The first vertical slice is a low-risk branding setting through the full draft/validate/preview/apply/audit/rollback path.
- AI administration (Open WebUI / OpenAI-compatible providers, six model roles, prompt versions) ships in the same increment.
- Remaining registry categories are present as metadata; values that still require process/env changes are marked `bootstrap` or `todo`.

## Consequences

Non-admins receive 403. Demo `admin@rockhawk.local` can operate the center. Ordinary reviewer/viewer accounts cannot.
