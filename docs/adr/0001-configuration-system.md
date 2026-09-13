# ADR 0001 — Configuration system

## Status

Accepted

## Context

RockHawk must let administrators change operational settings without redeploying code, while keeping security, privacy, audit, legal-hold, and human-review floors intact.

## Decision

- A typed **configuration registry** in application code is the authoritative catalog of manageable settings (key, type, default, risk, editability, restart requirement, secret handling).
- Runtime overrides live in **immutable configuration revisions**. Exactly one revision is active. Apply creates a new revision and switches the pointer atomically.
- Effective value precedence: bootstrap/env > global admin revision > registry default. Workspace/matter/user layers may be added later; user prefs are presentation-only.
- Secrets are stored only as **secret references**. APIs, diffs, audits, logs, and exports never return raw secret material.
- Consequential settings follow: draft → validate → preview impact → (test where applicable) → confirm → apply → verify → audit. Rollback is a new revision copied from a prior revision.
- Settings that weaken security, privacy, audit completeness, legal hold, or verified-cell preservation are rejected by validation (floors).

## Consequences

Consumers read `get_effective(key)` rather than scattering `os.getenv` for managed keys. Environment variables remain the bootstrap override and stay read-only in the admin UI when set.
