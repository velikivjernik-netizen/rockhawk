# Admin guide

RockHawk is intended for a firm-controlled host (a laptop or an internal Ubuntu VM). It is not a multi-tenant SaaS.

## First boot

1. `cp .env.example .env`
2. Set a long random `SECRET_KEY`
3. Change `ADMIN_PASSWORD` **before** the first `docker compose up` if this host is shared
4. `docker compose up --build`
5. Sign in, then **Load demo matter** (or create a real matter and upload files)

If you already booted with `ChangeMeNow!`, use **Change password** (`POST /api/auth/change-password`) immediately.

## Users and roles

| Role | Capability |
| --- | --- |
| `admin` | All matters (except those behind an ethical wall on that user), users, walls, seed |
| `attorney` | Create matters, manage members, run columns, edit/verify |
| `reviewer` | Edit, verify, flag, comment, assign, run columns on assigned matters |
| `viewer` | Read-only |

Create users with `POST /api/users` (admin). New users are flagged `must_change_password`.

## Ethical walls

`POST /api/matters/{id}/walls` (admin) hides a matter from a user even if they are otherwise an attorney or admin. The demo seeds a wall for `walled@rockhawk.local`.

Walls are a control, not a substitute for firm conflict-checking procedures.

## Persistence and backup

Compose volumes:

- `postgres_data` — matters, tables, cells, audit
- `storage_data` — original files
- `redis_data` — job queue only (safe to lose)

Back up the two data volumes together. Restarting compose does not wipe them.

## Jobs

`POST /api/tables/{id}/run` enqueues work on Redis. The `worker` service pops jobs. `POST /api/tables/{id}/run-sync` exists for tests and air-gapped laptops without Redis.

## Open WebUI

1. Run Open WebUI (or Ollama) with an OpenAI-compatible `/v1` endpoint
2. Set `AI_PROVIDER=openai_compatible` and `OPENAI_COMPATIBLE_BASE_URL`
3. Restart `api` and `worker`

Keep `AI_PROVIDER=mock` unless you have reviewed the remote model's data-handling policy. Mock mode never leaves the host.

## Document types and OCR

The API/worker image installs **Tesseract** (`tesseract-ocr`, English trained data) so JPG/PNG uploads can produce searchable text. Rebuild Compose after pulling this change (`docker compose up --build`).

If you run the backend on the host without Tesseract, images still ingest; extraction falls back to filename/EXIF and the audit payload records `confidence=low`.

Allowed extensions: PDF, DOCX, TXT, MD, CSV, XLSX, XLS, HTM/HTML, XML, PPTX, PPT, JPG/JPEG, PNG, VCF, RTF, EML, MSG. Other types (for example `.exe`, `.gif`, `.zip`) are rejected per file and do not fail the rest of a folder batch.

## Audit

`GET /api/audit?matter_id=` is append-only. There is no update or delete API for `audit_events`.
