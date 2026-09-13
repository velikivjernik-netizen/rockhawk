from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api import admin, ask, audit, auth, cells, documents, export, matters, tables, users
from app.config import get_settings
from app import db as dbmod
from app.db import Base
from app.seed import seed_if_needed


@asynccontextmanager
async def lifespan(_app: FastAPI):
    Base.metadata.create_all(bind=dbmod.engine)
    db = dbmod.SessionLocal()
    try:
        seed_if_needed(db)
    finally:
        db.close()
    yield


def create_app() -> FastAPI:
    settings = get_settings()
    app = FastAPI(
        title=settings.app_name,
        description=(
            "Locally hosted legal-document review tables. Attorney assistance only — "
            "RockHawk does not make autonomous legal decisions."
        ),
        version="1.0.0",
        lifespan=lifespan,
    )
    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.cors_origin_list,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.include_router(auth.router, prefix="/api")
    app.include_router(users.router, prefix="/api")
    app.include_router(matters.router, prefix="/api")
    app.include_router(documents.router, prefix="/api")
    app.include_router(tables.router, prefix="/api")
    app.include_router(cells.router, prefix="/api")
    app.include_router(ask.router, prefix="/api")
    app.include_router(export.router, prefix="/api")
    app.include_router(audit.router, prefix="/api")
    app.include_router(admin.router, prefix="/api")

    @app.get("/api/health")
    def health() -> dict:
        return {"status": "ok", "provider": settings.ai_provider}

    return app


app = create_app()
