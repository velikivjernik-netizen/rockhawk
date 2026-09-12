from app.ai.base import AIProvider
from app.ai.mock import MockProvider
from app.ai.openai_compatible import OpenAICompatibleProvider
from app.config import get_settings


def get_provider() -> AIProvider:
    name = get_settings().ai_provider.lower().strip()
    if name in {"openai_compatible", "openai", "open_webui", "ollama"}:
        return OpenAICompatibleProvider()
    return MockProvider()
