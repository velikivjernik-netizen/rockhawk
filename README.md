# RockHawk Review Tables

Locally hosted **attorney-assistance** workspace for matter-scoped document review. RockHawk extracts typed columns from PDF, DOCX, and TXT files, cites the page it used, and leaves every legal determination to a human. It does **not** make autonomous legal decisions.

This is an original RockHawk design. It is not affiliated with Harvey or any other commercial legal-AI product.

The Origin reference repository (`shawn-b/tmp-5f51db903b23bb52`) was not readable from the environment that published this GitHub copy, so the application was re-implemented against the same acceptance criteria.

## Quick start (Ubuntu + Docker Compose)

```bash
git clone https://github.com/velikivjernik-netizen/rockhawk.git
cd rockhawk
cp .env.example .env
docker compose up --build
```

Then:

1. Open the UI at [http://localhost:8080](http://localhost:8080)
2. Sign in with the development admin account
3. Click **Load demo matter**
4. Open **Northwind Procurement v. Contoso Logistics — MSA diligence**
5. Open **MSA diligence grid** and click **Run AI columns**

OpenAPI / Swagger UI: [http://localhost:8000/docs](http://localhost:8000/docs)

| Service | Port |
| --- | --- |
| Web UI | **8080** |
| FastAPI / OpenAPI | **8000** |
| PostgreSQL | 5432 |
| Redis | 6379 |

Volumes persist Postgres, Redis, and uploaded files. `docker compose down` and `docker compose up` keep data.

## Development admin (must change)

| Field | Value |
| --- | --- |
| Email | `admin@rockhawk.local` |
| Password | `ChangeMeNow!` |

**Treat this password as compromised.** It is published so a first clone can boot. Change it (UI is flagged; `POST /api/auth/change-password`) before any shared or networked use. The seeded admin account has `must_change_password=true`.

Other fictional demo accounts (same warning):

| Role | Email | Password |
| --- | --- | --- |
| Reviewer | `reviewer@rockhawk.local` | `ReviewerDemo1!` |
| Viewer (read-only) | `viewer@rockhawk.local` | `ViewerDemo1!` |
| Walled attorney | `walled@rockhawk.local` | `WalledDemo1!` |

`walled@rockhawk.local` is ethically walled from the demo matter and must see nothing.

## What works

- Upload PDF, DOCX, TXT with page-level citations
- Seven typed AI columns (text, date, boolean, money, enum, plus a conditional text column)
- Async column runs (`POST /api/tables/{id}/run` via Redis). Verified cells survive bulk reruns unless you opt in
- Edit, verify, flag, comment, assign
- Conditional columns (termination notice period runs only when termination-for-convenience is true)
- Hot Review queue
- Ask RockHawk over table outputs + cited pages
- CSV and XLSX export
- RBAC (admin / attorney / reviewer / viewer) and ethical walls
- Immutable append-only audit trail
- Mock AI by default (`AI_PROVIDER=mock`) — returns **Not found** instead of fabricating
- Optional Open WebUI / OpenAI-compatible provider (`AI_PROVIDER=openai_compatible`)
- Local JWT auth plus an OIDC hook (`/api/auth/oidc/login`)

## AI providers

```env
AI_PROVIDER=mock
```

Mock extraction reads only uploaded page text. If the page does not support the column, the cell is `Not found`.

```env
AI_PROVIDER=openai_compatible
OPENAI_COMPATIBLE_BASE_URL=http://host.docker.internal:8080/v1
OPENAI_COMPATIBLE_API_KEY=
OPENAI_COMPATIBLE_MODEL=llama3.1
```

Point `OPENAI_COMPATIBLE_BASE_URL` at Open WebUI, vLLM, Ollama, or any `/v1/chat/completions` server. The prompt forbids invention; if the remote call fails, RockHawk falls back to the mock extractor.

## SQLite local demo (no Docker)

```bash
cd backend
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
export DATABASE_URL=sqlite:///./rockhawk.db STORAGE_DIR=./data/storage AI_PROVIDER=mock SEED_DEMO=true
uvicorn app.main:app --reload --port 8000
```

```bash
cd frontend
npm install
npm run dev
```

UI: [http://localhost:5173](http://localhost:5173) (Vite proxies `/api` to port 8000).

## Tests

```bash
make backend-test          # Pytest
cd frontend && npm test    # Vitest
cd frontend && npx playwright test   # optional, needs a running UI
```

## Docs

- [Admin guide](docs/admin-guide.md)
- [Reviewer guide](docs/reviewer-guide.md)
- [Architecture](docs/architecture.md)
- [Threat model](docs/threat-model.md)
- [Known limitations](docs/known-limitations.md)
- [OIDC hook](docs/oidc.md)

## License

MIT — see [LICENSE](LICENSE).
