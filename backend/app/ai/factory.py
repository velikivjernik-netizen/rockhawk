from sqlalchemy.orm import Session

from app.ai.base import AIProvider
from app.ai.mock import MockProvider
from app.ai.openai_compatible import OpenAICompatibleProvider
from app.config import get_settings


def get_provider(db: Session | None = None, role: str | None = None) -> AIProvider:
    name = get_settings().ai_provider.lower().strip()
    base_url = get_settings().openai_compatible_base_url
    api_key = get_settings().openai_compatible_api_key
    model = get_settings().openai_compatible_model
    if db is not None:
        from app.ai.admin_ops import resolve_api_key, resolve_base_url, resolve_provider_name, resolve_role_model

        name = resolve_provider_name(db)
        base_url = resolve_base_url(db)
        api_key = resolve_api_key(db)
        model = resolve_role_model(db, role or "extraction")
    if name in {"openai_compatible", "openai", "open_webui", "ollama"}:
        return OpenAICompatibleProvider(base_url=base_url, api_key=api_key, model=model)
    return MockProvider()
