# Architecture

```
           ┌─────────────┐
           │  React UI   │  :8080 (nginx) / :5173 (Vite)
           └──────┬──────┘
                  │ /api
           ┌──────▼──────┐
           │   FastAPI   │  :8000   OpenAPI at /docs
           └─┬─────┬───┬─┘
             │     │   │
     ┌───────▼┐ ┌──▼──┐ ┌──────────▼─────────┐
     │Postgres│ │Redis│ │ Filesystem storage │
     │+pgvector│ │queue│ │  (MinIO-compatible │
     └────────┘ └─────┘ │   volume path)     │
                         └──────────▲─────────┘
                                    │
                              ┌─────┴─────┐
                              │  Worker   │
                              └───────────┘
```

## Monorepo

| Path | Role |
| --- | --- |
| `backend/` | FastAPI, SQLAlchemy 2, Alembic, Pytest |
| `frontend/` | React 18 + TypeScript, Vitest, Playwright |
| `docs/` | Operator and reviewer documentation |
| `docker-compose.yml` | Postgres, Redis, API, worker, nginx |

SQLite is a supported fallback when `DATABASE_URL` starts with `sqlite`. Embeddings are stored as JSON (toy vectors) so the same models run without `pgvector`. On Postgres you may enable a true `vector` column later; the API does not require it for the mock provider.

## Request path

1. JWT bearer token from `POST /api/auth/login`
2. Matter ACL: ethical wall first, then membership (admins bypass membership, not walls)
3. Mutations write an `audit_events` row in the same transaction
4. Column runs enqueue `rockhawk:jobs`; the worker loads page text and calls `app.ai.get_provider(db, role=…)`
5. `/admin` reads the configuration registry and applies immutable revisions (`config_service.get_effective`)

## AI contract

Providers implement `extract` and `answer`. Both must return `not_found=true` and the literal value `Not found` when the source pages do not support the column or question. The mock provider never calls the network. `openai_compatible` sends page text to a `/v1/chat/completions` endpoint and falls back to mock on transport errors.

## Front-end accessibility

Native labels, skip link, keyboard-operable cell drawer, `role="alert"` for errors, and table semantics (`th scope`). Contrast is slate + gold on charcoal, not a third-party legal-AI palette.
