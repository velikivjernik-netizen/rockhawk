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


def test_connection(
    db: Session,
    *,
    target: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    provider = resolve_provider_name(db)
    wants_remote = (target or "").lower() in {"openai_compatible", "open_webui", "remote"}
    if not wants_remote and provider in {"mock", ""} and not (base_url or "").strip():
        return {
            "ok": True,
            "provider": "mock",
            "detail": (
                "Active provider is mock (on-box). No client documents were sent. "
                "Probe Open WebUI with target=openai_compatible to test the configured /v1 endpoint."
            ),
            "models": ["mock-extractor", "mock-embed"],
            "key_configured": bool(resolve_api_key(db) or api_key),
        }
    return _probe_remote(db, base_url=base_url, api_key=api_key, discover=True)


def discover_models(
    db: Session,
    *,
    target: str | None = None,
    base_url: str | None = None,
    api_key: str | None = None,
) -> dict[str, Any]:
    provider = resolve_provider_name(db)
    wants_remote = (target or "").lower() in {"openai_compatible", "open_webui", "remote"}
    if not wants_remote and provider in {"mock", ""} and not (base_url or "").strip():
        return {"provider": "mock", "models": ["mock-extractor", "mock-embed"]}
    result = _probe_remote(db, base_url=base_url, api_key=api_key, discover=True)
    return {
        "provider": "openai_compatible",
        "models": result.get("models") or [],
        "detail": result.get("detail"),
        "ok": result.get("ok"),
    }


def _probe_remote(
    db: Session,
    *,
    base_url: str | None,
    api_key: str | None,
    discover: bool,
) -> dict[str, Any]:
    url = (base_url or resolve_base_url(db) or "").strip().rstrip("/")
    if not url:
        return {
            "ok": False,
            "provider": "openai_compatible",
            "detail": "Base URL is empty. Set the Open WebUI /v1 URL first.",
            "models": [],
            "key_configured": False,
        }
    key = api_key if api_key is not None else resolve_api_key(db)
    headers = {"Content-Type": "application/json"}
    if key:
        headers["Authorization"] = f"Bearer {key}"
    try:
        with httpx.Client(timeout=12.0) as client:
            models_resp = client.get(f"{url}/models", headers=headers)
            if models_resp.status_code < 400:
                names = _model_ids(models_resp.json())
                return {
                    "ok": True,
                    "provider": "openai_compatible",
                    "detail": "Model catalog reachable. No client documents were sent.",
                    "models": names if discover else [],
                    "key_configured": bool(key),
                    "base_url": url,
                }
            ping = client.post(
                f"{url}/chat/completions",
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
                "provider": "openai_compatible",
                "detail": "Chat ping succeeded. No client documents were sent.",
                "models": [],
                "key_configured": bool(key),
                "base_url": url,
            }
    except Exception as exc:
        return {
            "ok": False,
            "provider": "openai_compatible",
            "detail": (
                f"Connection failed ({exc.__class__.__name__}). "
                "From Compose on Linux use http://host.docker.internal:<port>/v1 "
                "(extra_hosts host-gateway) or http://172.17.0.1:<port>/v1 — not localhost."
            ),
            "models": [],
            "key_configured": bool(key),
            "base_url": url,
        }


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
