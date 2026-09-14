# Configuration system

RockHawk’s Administration Center (`/admin`) is the operator UI for settings that can change without a code deploy. The typed registry in `backend/app/config_registry.py` is the catalog.

## Precedence

1. Bootstrap / environment **pin** (`SECRET_KEY`, database/redis/storage URLs, or `ROCKHAWK_PIN_AI_SETTINGS=true` for AI keys)
2. Active global admin revision
3. Environment fallback (for example `AI_PROVIDER=mock` in `.env` until an admin applies a change)
4. Registry default

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
- AI provider/URL/key/model **only when** `ROCKHAWK_PIN_AI_SETTINGS=true`
- OIDC issuer / client credentials
- Legal-hold / defensible deletion procedures (documented; no live purge API)

## AI administration

Open **Administration → 2. AI providers & model roles**.

1. Set **Active provider** to `openai_compatible` (unless pinned).
2. Enter the Open WebUI `/v1` **Base URL**.
3. Paste the **API key** (stored as a secret reference; the page shows Configured / Not configured, never the raw key).
4. **Test Connection**, then **Discover models**.
5. Pick models from the discovered list (or type an id) for default chat plus the six roles: orchestrator, triage, coding/extraction, QC, synthesis, embeddings.
6. **Validate & preview draft** → reason → **Confirm and apply**.

**Test Connection** and discovery send a synthetic ping only. Matter documents are never attached.

Linux Docker: `api`/`worker` use `extra_hosts: host.docker.internal:host-gateway`. Prefer `http://host.docker.internal:<port>/v1`. Fallback: `http://172.17.0.1:<port>/v1`. `localhost` inside those containers is not the host.

Prompt bodies are versioned. Editing a prompt creates a new version; columns may pin `prompt_key` + `prompt_version`.
