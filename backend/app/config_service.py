"""Immutable configuration revisions and effective-value resolution."""

from __future__ import annotations

import copy
import os
from dataclasses import dataclass
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.audit import log_event
from app.config_registry import REGISTRY, SettingDef, get_definition
from app.models import (
    ConfigurationApplyEvent,
    ConfigurationApproval,
    ConfigurationDraft,
    ConfigurationPointer,
    ConfigurationRevision,
    ConfigurationValue,
    FeatureFlag,
    PromptVersion,
    SecretReference,
    User,
    new_id,
    utcnow,
)
from app.secrets_crypto import decrypt_secret, encrypt_secret, secret_hint

POINTER_ID = "global"
CONFIRM_PHRASE = "APPLY"
SECRET_PLACEHOLDER = {"redacted": True}


@dataclass
class EffectiveValue:
    key: str
    value: Any
    source: str
    overridden: bool
    restart_required: bool
    secret: bool
    editability: str
    risk: str

    def public_value(self) -> Any:
        if self.secret:
            return _public_secret(self.value)
        return self.value

    def to_dict(self) -> dict[str, Any]:
        return {
            "key": self.key,
            "value": self.public_value(),
            "source": self.source,
            "overridden": self.overridden,
            "restart_required": self.restart_required,
            "secret": self.secret,
            "editability": self.editability,
            "risk": self.risk,
        }


def ensure_baseline(db: Session, actor_id: str | None = None) -> ConfigurationRevision:
    pointer = db.get(ConfigurationPointer, POINTER_ID)
    if pointer and pointer.active_revision_id:
        revision = db.get(ConfigurationRevision, pointer.active_revision_id)
        if revision:
            _ensure_default_prompts(db, actor_id)
            _ensure_feature_flags(db)
            return revision
    revision = ConfigurationRevision(
        number=1,
        status="applied",
        reason="Baseline revision (registry defaults)",
        note="Seeded empty override set. Effective values come from env or defaults.",
        created_by_id=actor_id,
    )
    db.add(revision)
    db.flush()
    if pointer is None:
        pointer = ConfigurationPointer(id=POINTER_ID, active_revision_id=revision.id)
        db.add(pointer)
    else:
        pointer.active_revision_id = revision.id
        pointer.updated_at = utcnow()
    log_event(
        db,
        action="config.revision.baseline",
        entity_type="configuration_revision",
        entity_id=revision.id,
        actor_id=actor_id,
        payload={"number": 1},
    )
    _ensure_default_prompts(db, actor_id)
    _ensure_feature_flags(db)
    return revision


def active_revision(db: Session) -> ConfigurationRevision | None:
    pointer = db.get(ConfigurationPointer, POINTER_ID)
    if pointer is None or not pointer.active_revision_id:
        return None
    return db.scalar(
        select(ConfigurationRevision)
        .options(selectinload(ConfigurationRevision.values))
        .where(ConfigurationRevision.id == pointer.active_revision_id)
    )


def _revision_map(revision: ConfigurationRevision | None) -> dict[str, Any]:
    if revision is None:
        return {}
    return {row.key: row.value_json for row in revision.values}


def _ai_settings_pinned() -> bool:
    return os.environ.get("ROCKHAWK_PIN_AI_SETTINGS", "").strip().lower() in {"1", "true", "yes", "on"}


def _env_present(definition: SettingDef) -> tuple[bool, Any]:
    if not definition.env_key or definition.env_key not in os.environ:
        return False, None
    raw = os.environ[definition.env_key]
    if definition.secret and not str(raw).strip():
        return False, None
    return True, _coerce(definition, raw)


def _env_is_pinned(definition: SettingDef) -> bool:
    has_env, _ = _env_present(definition)
    if not has_env:
        return False
    mode = getattr(definition, "env_mode", "pin")
    if mode == "fallback":
        return _ai_settings_pinned()
    return True


def _env_override(definition: SettingDef) -> tuple[bool, Any]:
    """True when environment should win over an admin revision (bootstrap pin)."""
    if not _env_is_pinned(definition):
        return False, None
    return _env_present(definition)


def _public_secret(value: Any) -> dict[str, Any]:
    if isinstance(value, dict):
        if value.get("secret_ref") or value.get("configured") or value.get("hint") or value.get("source") == "env":
            hint = str(value.get("hint") or "••••")
            if hint in {"", "••••"} and not value.get("secret_ref") and not value.get("configured"):
                return {"configured": False, "hint": None}
            return {"configured": True, "hint": hint, "secret_ref": value.get("secret_ref")}
        return {"configured": False, "hint": None}
    if value in (None, ""):
        return {"configured": False, "hint": None}
    return {"configured": True, "hint": "••••"}


def _coerce(definition: SettingDef, raw: Any) -> Any:
    if definition.secret and isinstance(raw, dict) and "secret_ref" in raw:
        return raw
    if definition.value_type == "boolean":
        if isinstance(raw, bool):
            return raw
        return str(raw).strip().lower() in {"1", "true", "yes", "on"}
    if definition.value_type == "integer":
        return int(raw)
    if definition.value_type == "number":
        return float(raw)
    if definition.secret:
        return str(raw) if raw is not None else ""
    return raw


def get_effective(db: Session, key: str) -> EffectiveValue:
    definition = get_definition(key)
    pinned, pin_value = _env_override(definition)
    has_env, env_value = _env_present(definition)
    revision = active_revision(db)
    stored = _revision_map(revision)
    if pinned:
        value = pin_value
        if definition.secret:
            value = {"configured": True, "hint": secret_hint(str(pin_value)), "source": "env"} if pin_value else {
                "configured": False,
                "hint": None,
            }
        return EffectiveValue(
            key=key,
            value=value,
            source="bootstrap",
            overridden=True,
            restart_required=definition.restart_required,
            secret=definition.secret,
            editability="bootstrap",
            risk=definition.risk,
        )
    if key in stored:
        return EffectiveValue(
            key=key,
            value=stored[key],
            source="global_admin",
            overridden=stored[key] != definition.default,
            restart_required=definition.restart_required,
            secret=definition.secret,
            editability=definition.editability,
            risk=definition.risk,
        )
    if has_env:
        value = env_value
        if definition.secret:
            value = {"configured": True, "hint": secret_hint(str(env_value)), "source": "env"} if env_value else {
                "configured": False,
                "hint": None,
            }
        return EffectiveValue(
            key=key,
            value=value,
            source="env",
            overridden=True,
            restart_required=definition.restart_required,
            secret=definition.secret,
            editability=definition.editability,
            risk=definition.risk,
        )
    return EffectiveValue(
        key=key,
        value=definition.default,
        source="default",
        overridden=False,
        restart_required=definition.restart_required,
        secret=definition.secret,
        editability=definition.editability,
        risk=definition.risk,
    )


def all_effective(db: Session) -> list[EffectiveValue]:
    return [get_effective(db, key) for key in REGISTRY]


def effective_bool(db: Session, key: str) -> bool:
    value = get_effective(db, key).value
    if isinstance(value, bool):
        return value
    return str(value).strip().lower() in {"1", "true", "yes", "on"}


def effective_raw(db: Session, key: str) -> Any:
    """Runtime value including decrypted secrets. Never return this from an API."""
    definition = get_definition(key)
    pinned, pin_value = _env_override(definition)
    if pinned:
        return pin_value
    stored = _revision_map(active_revision(db))
    if key in stored:
        value = stored[key]
        if definition.secret and isinstance(value, dict) and value.get("secret_ref"):
            ref = db.get(SecretReference, value["secret_ref"])
            return decrypt_secret(ref.ciphertext) if ref else ""
        return value
    has_env, env_value = _env_present(definition)
    if has_env:
        return env_value
    return definition.default


def create_draft(db: Session, proposed: dict[str, Any], user: User, expected_revision_id: str | None) -> ConfigurationDraft:
    ensure_baseline(db, user.id)
    current = active_revision(db)
    draft = ConfigurationDraft(
        created_by_id=user.id,
        proposed_json=_sanitize_incoming(proposed),
        expected_revision_id=expected_revision_id or (current.id if current else None),
        status="open",
    )
    db.add(draft)
    db.flush()
    log_event(
        db,
        action="config.draft.created",
        entity_type="configuration_draft",
        entity_id=draft.id,
        actor_id=user.id,
        payload={"keys": sorted(draft.proposed_json.keys())},
    )
    return draft


def validate_draft(db: Session, draft: ConfigurationDraft) -> dict[str, Any]:
    errors: list[str] = []
    warnings: list[str] = []
    for key, raw in draft.proposed_json.items():
        if key not in REGISTRY:
            errors.append(f"Unknown setting: {key}")
            continue
        definition = REGISTRY[key]
        if definition.editability in {"readonly", "bootstrap"}:
            errors.append(f"{key} is {definition.editability} and cannot be changed here")
            continue
        if _env_is_pinned(definition):
            errors.append(f"{key} is pinned by environment {definition.env_key}")
            continue
        try:
            value = _coerce(definition, raw) if not (definition.secret and _is_secret_payload(raw)) else raw
        except (TypeError, ValueError):
            errors.append(f"{key} has an invalid {definition.value_type} value")
            continue
        if definition.enum_options and not definition.secret and value not in definition.enum_options:
            errors.append(f"{key} must be one of {list(definition.enum_options)}")
        if definition.floor is True and value is False:
            errors.append(f"{key} is a floor and cannot be weakened")
        if definition.floor is False and value is True:
            errors.append(f"{key} is a floor and cannot be weakened")
        if definition.risk in {"high", "bootstrap"}:
            warnings.append(f"{key} is {definition.risk}-risk and requires confirm + reason")
        if definition.restart_required:
            warnings.append(f"{key} requires a process restart after apply")
    result = {"ok": not errors, "errors": errors, "warnings": warnings}
    draft.validation_json = result
    draft.status = "validated" if result["ok"] else "invalid"
    draft.updated_at = utcnow()
    return result


def preview_draft(db: Session, draft: ConfigurationDraft) -> dict[str, Any]:
    if not draft.validation_json or not draft.validation_json.get("ok"):
        raise HTTPException(status_code=400, detail="Validate the draft before preview")
    current = {item.key: item.public_value() for item in all_effective(db)}
    diffs: list[dict[str, Any]] = []
    impact: list[str] = []
    for key, raw in draft.proposed_json.items():
        definition = REGISTRY[key]
        before = current.get(key)
        after = _public_proposed(db, definition, raw)
        diffs.append({"key": key, "before": before, "after": after, "risk": definition.risk})
        impact.extend(_impact_lines(definition))
    preview = {
        "diffs": diffs,
        "impact": sorted(set(impact)),
        "restart_required": any(REGISTRY[k].restart_required for k in draft.proposed_json),
        "high_risk": any(REGISTRY[k].risk in {"high", "bootstrap"} for k in draft.proposed_json),
    }
    draft.preview_json = preview
    draft.status = "previewed"
    draft.updated_at = utcnow()
    return preview


def apply_draft(
    db: Session,
    draft: ConfigurationDraft,
    user: User,
    *,
    reason: str,
    confirm: bool,
    expected_revision_id: str | None,
) -> ConfigurationRevision:
    if not confirm:
        raise HTTPException(status_code=400, detail="Consequential settings require confirm=true")
    if len((reason or "").strip()) < 8:
        raise HTTPException(status_code=400, detail="Provide a reason of at least 8 characters")
    if draft.status not in {"previewed", "validated"}:
        raise HTTPException(status_code=400, detail="Draft must be validated and previewed before apply")
    validation = draft.validation_json or validate_draft(db, draft)
    if not validation.get("ok"):
        raise HTTPException(status_code=400, detail=validation)
    if draft.preview_json is None:
        preview_draft(db, draft)

    current = active_revision(db)
    expected = expected_revision_id or draft.expected_revision_id
    if current and expected and current.id != expected:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="Active revision changed. Reload effective values and retry.",
        )
    high_risk = any(REGISTRY[k].risk in {"high", "bootstrap"} for k in draft.proposed_json)
    if high_risk:
        _require_high_risk_ok(db, draft, user)

    apply_event = ConfigurationApplyEvent(
        draft_id=draft.id,
        actor_id=user.id,
        status="started",
        detail_json={"keys": sorted(draft.proposed_json.keys())},
    )
    db.add(apply_event)
    db.flush()

    try:
        parent_map = _revision_map(current)
        merged = copy.deepcopy(parent_map)
        for key, raw in draft.proposed_json.items():
            merged[key] = _persist_value(db, key, raw, user.id)
        revision = ConfigurationRevision(
            number=(current.number + 1) if current else 1,
            status="applied",
            parent_id=current.id if current else None,
            created_by_id=user.id,
            reason=reason.strip(),
            note="Applied from draft",
        )
        db.add(revision)
        db.flush()
        for key, value in merged.items():
            db.add(ConfigurationValue(revision_id=revision.id, key=key, value_json=value))
        pointer = db.get(ConfigurationPointer, POINTER_ID)
        if pointer is None:
            pointer = ConfigurationPointer(id=POINTER_ID, active_revision_id=revision.id)
            db.add(pointer)
        else:
            pointer.active_revision_id = revision.id
            pointer.updated_at = utcnow()
        if current:
            current.status = "superseded"
        draft.status = "applied"
        draft.updated_at = utcnow()
        _sync_feature_flags(db, merged)
        db.flush()
        verify = _verify_apply(db, draft.proposed_json)
        if not verify["ok"]:
            raise RuntimeError(verify["errors"])
        apply_event.revision_id = revision.id
        apply_event.status = "verified"
        apply_event.detail_json = {"keys": sorted(draft.proposed_json.keys()), "verify": verify}
        log_event(
            db,
            action="config.revision.applied",
            entity_type="configuration_revision",
            entity_id=revision.id,
            actor_id=user.id,
            payload={
                "number": revision.number,
                "reason": reason.strip(),
                "keys": sorted(draft.proposed_json.keys()),
                "diffs": _audit_diffs(draft),
            },
        )
        return revision
    except Exception as exc:
        apply_event.status = "failed"
        apply_event.detail_json = {"error": str(exc)}
        log_event(
            db,
            action="config.apply.failed",
            entity_type="configuration_draft",
            entity_id=draft.id,
            actor_id=user.id,
            payload={"error": str(exc)},
        )
        raise HTTPException(status_code=500, detail="Apply failed; prior revision remains active") from exc


def rollback_to(db: Session, revision_id: str, user: User, reason: str) -> ConfigurationRevision:
    target = db.scalar(
        select(ConfigurationRevision).options(selectinload(ConfigurationRevision.values)).where(
            ConfigurationRevision.id == revision_id
        )
    )
    if target is None:
        raise HTTPException(status_code=404, detail="Revision not found")
    if len((reason or "").strip()) < 8:
        raise HTTPException(status_code=400, detail="Provide a rollback reason of at least 8 characters")
    current = active_revision(db)
    copied = {row.key: row.value_json for row in target.values}
    revision = ConfigurationRevision(
        number=(current.number + 1) if current else target.number + 1,
        status="applied",
        parent_id=current.id if current else target.id,
        created_by_id=user.id,
        reason=reason.strip(),
        note=f"Rollback to revision {target.number}",
    )
    db.add(revision)
    db.flush()
    for key, value in copied.items():
        db.add(ConfigurationValue(revision_id=revision.id, key=key, value_json=value))
    pointer = db.get(ConfigurationPointer, POINTER_ID)
    if pointer is None:
        db.add(ConfigurationPointer(id=POINTER_ID, active_revision_id=revision.id))
    else:
        pointer.active_revision_id = revision.id
        pointer.updated_at = utcnow()
    if current:
        current.status = "superseded"
    _sync_feature_flags(db, copied)
    log_event(
        db,
        action="config.revision.rollback",
        entity_type="configuration_revision",
        entity_id=revision.id,
        actor_id=user.id,
        payload={"from": current.id if current else None, "to": target.id, "reason": reason.strip()},
    )
    db.add(
        ConfigurationApplyEvent(
            revision_id=revision.id,
            actor_id=user.id,
            status="verified",
            detail_json={"rollback_of": target.id},
        )
    )
    return revision


def export_bundle(db: Session) -> dict[str, Any]:
    revision = active_revision(db)
    values = {}
    for item in all_effective(db):
        if item.secret:
            values[item.key] = item.public_value()
        elif item.source == "global_admin":
            values[item.key] = item.value
    return {
        "format": "rockhawk-config-v1",
        "active_revision": revision.number if revision else None,
        "values": values,
    }


def import_dry_run(db: Session, bundle: dict[str, Any]) -> dict[str, Any]:
    values = bundle.get("values") if isinstance(bundle, dict) else None
    if not isinstance(values, dict):
        raise HTTPException(status_code=400, detail="Bundle must include a values object")
    draft_like = ConfigurationDraft(proposed_json=_sanitize_incoming(values), status="open")
    validation = validate_draft(db, draft_like)
    diffs = []
    current = {item.key: item.public_value() for item in all_effective(db)}
    for key, raw in draft_like.proposed_json.items():
        if key not in REGISTRY:
            continue
        diffs.append({"key": key, "before": current.get(key), "after": _public_proposed(db, REGISTRY[key], raw)})
    return {"dry_run": True, "validation": validation, "diffs": diffs, "count": len(draft_like.proposed_json)}


def list_revisions(db: Session) -> list[ConfigurationRevision]:
    return list(db.scalars(select(ConfigurationRevision).order_by(ConfigurationRevision.number.desc())).all())


def _sanitize_incoming(proposed: dict[str, Any]) -> dict[str, Any]:
    clean: dict[str, Any] = {}
    for key, value in proposed.items():
        if key not in REGISTRY:
            clean[key] = value
            continue
        definition = REGISTRY[key]
        if definition.secret:
            if _is_secret_payload(value) or value in ("", None):
                if value not in ("", None):
                    clean[key] = {"secret_ref": value.get("secret_ref")} if isinstance(value, dict) else value
                continue
            clean[key] = {"__plain": str(value)}
        else:
            clean[key] = value
    return clean


def _persist_value(db: Session, key: str, raw: Any, user_id: str) -> Any:
    definition = REGISTRY[key]
    if definition.secret:
        if isinstance(raw, dict) and raw.get("secret_ref") and not raw.get("__plain"):
            return {"secret_ref": raw["secret_ref"], "hint": raw.get("hint", "••••")}
        plain = str(raw.get("__plain") if isinstance(raw, dict) and "__plain" in raw else raw)
        ref = SecretReference(
            name=key,
            ciphertext=encrypt_secret(plain),
            hint=secret_hint(plain),
            created_by_id=user_id,
        )
        db.add(ref)
        db.flush()
        return {"secret_ref": ref.id, "hint": ref.hint}
    return _coerce(definition, raw)


def _public_proposed(db: Session, definition: SettingDef, raw: Any) -> Any:
    if definition.secret:
        if isinstance(raw, dict) and raw.get("secret_ref"):
            ref = db.get(SecretReference, raw["secret_ref"])
            return {"configured": True, "hint": ref.hint if ref else "••••"}
        if isinstance(raw, dict) and "__plain" in raw:
            return {"configured": True, "hint": secret_hint(str(raw["__plain"]))}
        if raw in ("", None):
            return {"configured": False, "hint": None}
        return {"configured": True, "hint": secret_hint(str(raw))}
    try:
        return _coerce(definition, raw)
    except (TypeError, ValueError):
        return raw


def _is_secret_payload(raw: Any) -> bool:
    return isinstance(raw, dict) and ("secret_ref" in raw or "__plain" in raw)


def _impact_lines(definition: SettingDef) -> list[str]:
    lines = [f"{definition.label} ({definition.key}) will change for all workspaces."]
    if definition.tags and "floor" in definition.tags:
        lines.append("Floor settings cannot be weakened.")
    if definition.category == "ai":
        lines.append("New AI calls use the updated provider/role after apply. In-flight jobs keep their current provider.")
    if definition.category == "review":
        lines.append("Review-table consumers re-read effective values on the next request.")
    if definition.restart_required:
        lines.append("A process restart is required before this value is fully live.")
    return lines


def _audit_diffs(draft: ConfigurationDraft) -> list[dict[str, Any]]:
    diffs = []
    for item in (draft.preview_json or {}).get("diffs", []):
        key = item["key"]
        definition = REGISTRY.get(key)
        if definition and definition.secret:
            diffs.append({"key": key, "before": SECRET_PLACEHOLDER, "after": SECRET_PLACEHOLDER})
        else:
            diffs.append({"key": key, "before": item.get("before"), "after": item.get("after")})
    return diffs


def _require_high_risk_ok(db: Session, draft: ConfigurationDraft, user: User) -> None:
    approvals = list(
        db.scalars(
            select(ConfigurationApproval).where(
                ConfigurationApproval.draft_id == draft.id, ConfigurationApproval.decision == "approved"
            )
        ).all()
    )
    other = [row for row in approvals if row.approver_id != user.id]
    admin_count = db.scalar(select(func.count()).select_from(User).where(User.role == "admin", User.is_active.is_(True)))
    if admin_count and admin_count > 1 and not other:
        raise HTTPException(
            status_code=400,
            detail="High-risk change requires a second admin approval on this draft",
        )


def _verify_apply(db: Session, proposed: dict[str, Any]) -> dict[str, Any]:
    errors: list[str] = []
    for key, raw in proposed.items():
        definition = REGISTRY[key]
        effective = get_effective(db, key)
        if definition.secret:
            continue
        expected = _coerce(definition, raw) if not _is_secret_payload(raw) else raw
        if effective.source != "global_admin":
            errors.append(f"{key} source is {effective.source}, expected global_admin")
        elif effective.value != expected:
            errors.append(f"{key} did not match the applied value")
    return {"ok": not errors, "errors": errors}


def _ensure_default_prompts(db: Session, actor_id: str | None) -> None:
    defaults = {
        "column.extract": (
            "You are RockHawk, an attorney-assistance extractor. Use ONLY the provided page text. "
            "If the answer is not supported, return Not found. Never invent parties, dates, amounts, "
            "or legal conclusions. You do not make autonomous legal decisions."
        ),
        "ask.answer": (
            "Answer only from the supplied table cells and page snippets. Cite the cell or page. "
            "If unsupported, return Not found."
        ),
        "qc.check": (
            "Check that the extracted value is supported by the cited quote. If not, mark Not found."
        ),
    }
    for key, body in defaults.items():
        exists = db.scalar(select(PromptVersion).where(PromptVersion.prompt_key == key, PromptVersion.version == "1"))
        if exists:
            continue
        db.add(PromptVersion(prompt_key=key, version="1", body=body, note="Seeded lineage root", created_by_id=actor_id))


def _ensure_feature_flags(db: Session) -> None:
    for key, description in (
        ("feature.ask_rockhawk", "Ask RockHawk over table outputs"),
        ("feature.hot_queue", "Hot Review queue"),
        ("feature.column_suggest", "Natural-language column proposals"),
    ):
        if db.scalar(select(FeatureFlag).where(FeatureFlag.key == key)):
            continue
        db.add(FeatureFlag(key=key, enabled=True, description=description))


def _sync_feature_flags(db: Session, merged: dict[str, Any]) -> None:
    for key, value in merged.items():
        if not key.startswith("feature."):
            continue
        flag = db.scalar(select(FeatureFlag).where(FeatureFlag.key == key))
        enabled = bool(value)
        if flag is None:
            db.add(FeatureFlag(key=key, enabled=enabled, description=key))
        else:
            flag.enabled = enabled


def next_prompt_version(db: Session, prompt_key: str) -> str:
    versions = list(db.scalars(select(PromptVersion.version).where(PromptVersion.prompt_key == prompt_key)).all())
    numbers = []
    for item in versions:
        try:
            numbers.append(int(item))
        except ValueError:
            continue
    return str((max(numbers) if numbers else 0) + 1)


def create_prompt_version(db: Session, prompt_key: str, body: str, note: str, user: User) -> PromptVersion:
    latest = db.scalar(
        select(PromptVersion)
        .where(PromptVersion.prompt_key == prompt_key)
        .order_by(PromptVersion.created_at.desc())
    )
    version = PromptVersion(
        prompt_key=prompt_key,
        version=next_prompt_version(db, prompt_key),
        body=body,
        note=note,
        parent_version=latest.version if latest else None,
        created_by_id=user.id,
    )
    db.add(version)
    db.flush()
    log_event(
        db,
        action="prompt.version.created",
        entity_type="prompt_version",
        entity_id=version.id,
        actor_id=user.id,
        payload={"prompt_key": prompt_key, "version": version.version, "parent": version.parent_version},
    )
    return version


def public_secret_ref(ref: SecretReference) -> dict[str, str]:
    return {"id": ref.id, "name": ref.name, "hint": ref.hint}


def new_entity_id() -> str:
    return new_id()
