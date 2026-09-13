"""Admin-only AI provider probes. Never attach matter documents."""

from __future__ import annotations

from typing import Any

import httpx
from sqlalchemy.orm import Session

from app.config_service import effective_raw

PING_USER = "Reply with the single word pong. Do not mention any documents."


def resolve_provider_name(db: Session) -> str:
    return str(effective_raw(db, "ai.provider") or "mock").lower().strip()


def resolve_base_url(db: Session) -> str:
    return str(effective_raw(db, "ai.openai_compatible.base_url") or "").rstrip("/")


def resolve_api_key(db: Session) -> str:
    return str(effective_raw(db, "ai.openai_compatible.api_key") or "")


def resolve_default_model(db: Session) -> str:
    return str(effective_raw(db, "ai.openai_compatible.model") or "llama3.1")


def resolve_role_model(db: Session, role: str) -> str:
    assigned = str(effective_raw(db, f"ai.role.{role}") or "").strip()
    return assigned or resolve_default_model(db)


def test_connection(db: Session) -> dict[str, Any]:
    provider = resolve_provider_name(db)
    if provider in {"mock", ""}:
        return {
            "ok": True,
            "provider": "mock",
            "detail": "Mock provider is local. No network call was made and no client documents were sent.",
            "models": ["mock-extractor", "mock-embed"],
        }
    base = resolve_base_url(db)
    if not base:
        return {"ok": False, "provider": provider, "detail": "Base URL is empty"}
    headers = {"Content-Type": "application/json"}
    key = resolve_api_key(db)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        with httpx.Client(timeout=12.0) as client:
            models_resp = client.get(f"{base}/models", headers=headers)
            if models_resp.status_code >= 400:
                ping = client.post(
                    f"{base}/chat/completions",
                    headers=headers,
                    json={
                        "model": resolve_default_model(db),
                        "temperature": 0,
                        "max_tokens": 8,
                        "messages": [{"role": "user", "content": PING_USER}],
                    },
                )
                ping.raise_for_status()
                return {
                    "ok": True,
                    "provider": provider,
                    "detail": "Chat ping succeeded. No client documents were sent.",
                    "models": [],
                }
            names = _model_ids(models_resp.json())
            return {
                "ok": True,
                "provider": provider,
                "detail": "Model catalog reachable. No client documents were sent.",
                "models": names,
            }
    except Exception as exc:
        return {"ok": False, "provider": provider, "detail": f"Connection failed: {exc.__class__.__name__}", "models": []}


def discover_models(db: Session) -> dict[str, Any]:
    provider = resolve_provider_name(db)
    if provider in {"mock", ""}:
        return {"provider": "mock", "models": ["mock-extractor", "mock-embed"]}
    base = resolve_base_url(db)
    headers = {"Content-Type": "application/json"}
    key = resolve_api_key(db)
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        with httpx.Client(timeout=12.0) as client:
            response = client.get(f"{base}/models", headers=headers)
            response.raise_for_status()
            return {"provider": provider, "models": _model_ids(response.json())}
    except Exception as exc:
        return {"provider": provider, "models": [], "detail": f"Discovery failed: {exc.__class__.__name__}"}


def _model_ids(payload: Any) -> list[str]:
    data = payload.get("data") if isinstance(payload, dict) else payload
    if not isinstance(data, list):
        return []
    names: list[str] = []
    for item in data:
        if isinstance(item, str):
            names.append(item)
        elif isinstance(item, dict) and item.get("id"):
            names.append(str(item["id"]))
    return names
