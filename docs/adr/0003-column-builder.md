# ADR 0003 — User-defined review columns

## Status

Accepted

## Context

Review tables must be configurable by legal teams without code changes. Seeded starter columns remain a convenience, not the only schema.

## Decision

- Columns are first-class entities with a full builder: label, instruction, output type, enums, validation, dependencies, citation policy, model role, prompt version, overwrite policy.
- Natural-language “suggest columns” and checklist/CSV/XLSX import produce **proposals only**. Nothing is persisted until the user approves.
- Each document (or family) remains one table row. Column questions run asynchronously per selected row.
- Verified cells are a human-review floor: default overwrite policy skips verified answers unless the operator explicitly reruns including verified.

## Consequences

The table toolbar exposes Add column, Suggest, and Import. `POST /columns` no longer requires an API client.
