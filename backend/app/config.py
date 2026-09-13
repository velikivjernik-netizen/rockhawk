from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    app_name: str = "RockHawk Review Tables"
    secret_key: str = "dev-only-insecure-secret"
    algorithm: str = "HS256"
    access_token_minutes: int = 12 * 60

    database_url: str = "sqlite:///./rockhawk.db"
    redis_url: str = ""
    storage_dir: str = "./data/storage"

    ai_provider: str = "mock"
    openai_compatible_base_url: str = "http://localhost:8080/v1"
    openai_compatible_api_key: str = ""
    openai_compatible_model: str = "llama3.1"

    seed_demo: bool = True
    admin_email: str = "admin@rockhawk.local"
    admin_password: str = "ChangeMeNow!"

    oidc_issuer: str = ""
    oidc_client_id: str = ""
    oidc_client_secret: str = ""
    oidc_redirect_uri: str = "http://localhost:8080/api/auth/oidc/callback"

    cors_origins: str = "http://localhost:8080,http://localhost:5173,http://127.0.0.1:8080"
    log_level: str = "INFO"
    max_upload_bytes: int = 50 * 1024 * 1024

    @property
    def cors_origin_list(self) -> list[str]:
        return [item.strip() for item in self.cors_origins.split(",") if item.strip()]

    @property
    def oidc_enabled(self) -> bool:
        return bool(self.oidc_issuer and self.oidc_client_id)

    @property
    def is_sqlite(self) -> bool:
        return self.database_url.startswith("sqlite")


@lru_cache
def get_settings() -> Settings:
    return Settings()
