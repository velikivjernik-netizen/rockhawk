"""Envelope helpers for secret references. Ciphertext is never returned by APIs."""

from __future__ import annotations

import base64
import hashlib
import hmac

from app.config import get_settings

_PREFIX = "rh1"


def encrypt_secret(plain: str) -> str:
    raw = plain.encode("utf-8")
    key = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    mixed = bytes(b ^ key[i % len(key)] for i, b in enumerate(raw))
    mac = hmac.new(key, mixed, hashlib.sha256).digest()
    return _PREFIX + ":" + base64.urlsafe_b64encode(mac + mixed).decode("ascii")


def decrypt_secret(token: str) -> str:
    if not token or not token.startswith(_PREFIX + ":"):
        return ""
    blob = base64.urlsafe_b64decode(token.split(":", 1)[1].encode("ascii"))
    mac, mixed = blob[:32], blob[32:]
    key = hashlib.sha256(get_settings().secret_key.encode("utf-8")).digest()
    if not hmac.compare_digest(mac, hmac.new(key, mixed, hashlib.sha256).digest()):
        return ""
    raw = bytes(b ^ key[i % len(key)] for i, b in enumerate(mixed))
    return raw.decode("utf-8")


def secret_hint(plain: str) -> str:
    trimmed = (plain or "").strip()
    if len(trimmed) >= 4:
        return f"••••{trimmed[-4:]}"
    return "••••"


def looks_like_secret(value: object) -> bool:
    if isinstance(value, dict) and "secret_ref" in value:
        return True
    if isinstance(value, str) and value.startswith(_PREFIX + ":"):
        return True
    return False
