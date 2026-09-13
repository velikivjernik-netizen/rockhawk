# Configuration system

RockHawk’s Administration Center (`/admin`) is the operator UI for settings that can change without a code deploy. The typed registry in `backend/app/config_registry.py` is the catalog.

## Precedence

1. Bootstrap / environment variable (when the env key is actually set)
2. Active global admin revision
3. Registry default

Workspace, matter, and user layers are reserved. User preferences are presentation-only and cannot weaken security, privacy, audit, legal-hold, or human-review floors.

## Apply path

Draft → validate → preview impact → test (AI providers) → reason + confirm → atomic apply → verify consumers → append-only audit.

Rollback creates a **new** revision that copies an older revision. Applied revisions are immutable.

There is no unvalidated Save for consequential keys.

## Secrets

Secret settings (API keys, `SECRET_KEY`) are stored as `secret_reference` rows. APIs, diffs, audits, logs, and exports return only a hint (`••••abcd`) or a reference id. Ciphertext is never serialized to the browser.

## Floors (cannot be weakened in-app)

| Key | Rule |
| --- | --- |
| `review.preserve_verified_cells` | Always true. Bulk runs skip verified cells unless the operator chooses **Rerun including verified**. |
| `audit.enabled` | Append-only audit cannot be disabled. |
| `security.require_auth` | Data APIs stay authenticated. |
| `users.invite_requires_admin` | `POST /api/users` stays admin-only. |

## Still env / offline (bootstrap)

These remain process settings. The Administration Center shows them as read-only:

- `SECRET_KEY`, `DATABASE_URL`, `REDIS_URL`, `STORAGE_DIR`
- `AI_PROVIDER` when set in the environment (Compose default is `mock`)
- OIDC issuer / client credentials
- Legal-hold / defensible deletion procedures (documented; no live purge API)

## AI administration

Default remote adapter is Open WebUI via `openai_compatible`. Six roles are assigned independently:

`orchestrator`, `triage`, `extraction`, `qc`, `synthesis`, `embeddings`

**Test Connection** and model discovery send a synthetic ping only. Matter documents are never attached.

Prompt bodies are versioned. Editing a prompt creates a new version; columns may pin `prompt_key` + `prompt_version`.
