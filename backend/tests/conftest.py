import os
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

TEST_DIR = Path("/tmp/rockhawk-tests")
TEST_DIR.mkdir(parents=True, exist_ok=True)
os.environ.update(
    {
        "DATABASE_URL": f"sqlite:///{TEST_DIR}/test.db",
        "STORAGE_DIR": str(TEST_DIR / "storage"),
        "SECRET_KEY": "test-secret-key-not-for-production",
        "AI_PROVIDER": "mock",
        "SEED_DEMO": "true",
        "REDIS_URL": "",
        "ADMIN_EMAIL": "admin@rockhawk.local",
        "ADMIN_PASSWORD": "ChangeMeNow!",
    }
)

from app.config import get_settings  # noqa: E402

get_settings.cache_clear()

from app.db import Base, engine  # noqa: E402
from app.main import create_app  # noqa: E402


@pytest.fixture
def client(tmp_path: Path):
    db_path = tmp_path / "case.db"
    os.environ["DATABASE_URL"] = f"sqlite:///{db_path}"
    os.environ["STORAGE_DIR"] = str(tmp_path / "storage")
    get_settings.cache_clear()
    from app import db as dbmod
    from app.db import SessionLocal
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker

    test_engine = create_engine(os.environ["DATABASE_URL"], connect_args={"check_same_thread": False})
    TestingSession = sessionmaker(bind=test_engine, autoflush=False, autocommit=False)
    Base.metadata.drop_all(bind=test_engine)
    Base.metadata.create_all(bind=test_engine)
    dbmod.engine = test_engine
    dbmod.SessionLocal = TestingSession

    from app import jobs

    jobs.SessionLocal = TestingSession

    app = create_app()
    with TestClient(app) as test_client:
        yield test_client


@pytest.fixture
def admin_token(client: TestClient) -> str:
    response = client.post("/api/auth/login", json={"email": "admin@rockhawk.local", "password": "ChangeMeNow!"})
    assert response.status_code == 200, response.text
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(admin_token: str) -> dict[str, str]:
    return {"Authorization": f"Bearer {admin_token}"}
