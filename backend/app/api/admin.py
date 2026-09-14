from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.access import require_admin
from app.ai.admin_ops import discover_models, test_connection
from app.config_registry import CATEGORIES, MODEL_ROLES, REGISTRY, ROLE_LABELS
from app.config_service import (
    active_revision,
    all_effective,
    apply_draft,
    create_draft,
    create_prompt_version,
    ensure_baseline,
    export_bundle,
    import_dry_run,
    list_revisions,
    preview_draft,
    public_secret_ref,
    rollback_to,
    validate_draft,
)
from app.db import get_db
from app.deps import get_current_user
from app.models import (
    ConfigurationApproval,
    ConfigurationDraft,
    FeatureFlag,
    PromptVersion,
    SecretReference,
    User,
)
from app.schemas import (
    AdminApplyIn,
    AdminApprovalIn,
    AdminDraftIn,
    AdminImportIn,
    AdminRollbackIn,
    AiProbeIn,
    PromptVersionIn,
)

router = APIRouter(prefix="/admin", tags=["admin"])


def _admin(user: User = Depends(get_current_user)) -> User:
    require_admin(user)
    return user


@router.get("/registry")
def registry(_: User = Depends(_admin)) -> dict:
    return {
        "categories": CATEGORIES,
        "settings": [item.to_dict() for item in REGISTRY.values()],
    }


@router.get("/effective")
def effective(db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    ensure_baseline(db, user.id)
    db.commit()
    revision = active_revision(db)
    return {
        "active_revision_id": revision.id if revision else None,
        "active_revision_number": revision.number if revision else None,
        "values": [item.to_dict() for item in all_effective(db)],
    }


@router.post("/drafts", status_code=201)
def open_draft(payload: AdminDraftIn, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    draft = create_draft(db, payload.changes, user, payload.expected_revision_id)
    db.commit()
    db.refresh(draft)
    return _draft_out(draft)


@router.get("/drafts/{draft_id}")
def get_draft(draft_id: str, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    return _draft_out(_draft(db, draft_id))


@router.post("/drafts/{draft_id}/validate")
def validate(draft_id: str, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    draft = _draft(db, draft_id)
    result = validate_draft(db, draft)
    db.commit()
    return {"draft": _draft_out(draft), "validation": result}


@router.post("/drafts/{draft_id}/preview")
def preview(draft_id: str, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    draft = _draft(db, draft_id)
    preview_payload = preview_draft(db, draft)
    db.commit()
    return {"draft": _draft_out(draft), "preview": preview_payload}


@router.post("/drafts/{draft_id}/approve")
def approve(draft_id: str, payload: AdminApprovalIn, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    draft = _draft(db, draft_id)
    db.add(ConfigurationApproval(draft_id=draft.id, approver_id=user.id, decision=payload.decision))
    db.commit()
    return {"ok": True, "decision": payload.decision}


@router.post("/drafts/{draft_id}/apply")
def apply(draft_id: str, payload: AdminApplyIn, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    draft = _draft(db, draft_id)
    try:
        revision = apply_draft(
            db,
            draft,
            user,
            reason=payload.reason,
            confirm=payload.confirm,
            expected_revision_id=payload.expected_revision_id,
        )
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    return {
        "revision_id": revision.id,
        "number": revision.number,
        "reason": revision.reason,
        "active": True,
    }


@router.get("/revisions")
def revisions(db: Session = Depends(get_db), user: User = Depends(_admin)) -> list[dict]:
    ensure_baseline(db, user.id)
    db.commit()
    return [
        {
            "id": row.id,
            "number": row.number,
            "status": row.status,
            "reason": row.reason,
            "note": row.note,
            "parent_id": row.parent_id,
            "created_at": row.created_at.isoformat() if row.created_at else None,
            "created_by_id": row.created_by_id,
        }
        for row in list_revisions(db)
    ]


@router.post("/revisions/{revision_id}/rollback")
def rollback(revision_id: str, payload: AdminRollbackIn, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    try:
        revision = rollback_to(db, revision_id, user, payload.reason)
        db.commit()
    except HTTPException:
        db.rollback()
        raise
    return {"revision_id": revision.id, "number": revision.number, "reason": revision.reason}


@router.get("/export")
def export_config(db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    ensure_baseline(db, user.id)
    bundle = export_bundle(db)
    _assert_no_secrets(bundle)
    return bundle


@router.post("/import")
def import_config(payload: AdminImportIn, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    if not payload.dry_run:
        raise HTTPException(status_code=400, detail="Only dry-run import is supported. Apply accepted keys through a draft.")
    result = import_dry_run(db, payload.bundle)
    db.rollback()
    return result


@router.post("/ai/test-connection")
def ai_test(
    payload: AiProbeIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_admin),
) -> dict:
    ensure_baseline(db, user.id)
    body = payload or AiProbeIn()
    result = test_connection(db, target=body.target, base_url=body.base_url, api_key=body.api_key)
    return _strip_probe_secrets(result)


@router.get("/ai/models")
def ai_models(db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    ensure_baseline(db, user.id)
    return _strip_probe_secrets(discover_models(db))


@router.post("/ai/models")
def ai_models_probe(
    payload: AiProbeIn | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(_admin),
) -> dict:
    ensure_baseline(db, user.id)
    body = payload or AiProbeIn()
    return _strip_probe_secrets(
        discover_models(db, target=body.target or "openai_compatible", base_url=body.base_url, api_key=body.api_key)
    )


@router.get("/ai/roles")
def ai_roles(db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    ensure_baseline(db, user.id)
    from app.ai.admin_ops import resolve_role_model

    return {
        "roles": [
            {
                "role": role,
                "label": ROLE_LABELS[role],
                "model": resolve_role_model(db, role),
                "key": f"ai.role.{role}",
            }
            for role in MODEL_ROLES
        ]
    }


@router.get("/prompts")
def list_prompts(db: Session = Depends(get_db), user: User = Depends(_admin)) -> list[dict]:
    ensure_baseline(db, user.id)
    db.commit()
    rows = list(db.scalars(select(PromptVersion).order_by(PromptVersion.prompt_key, PromptVersion.created_at)).all())
    return [_prompt_out(row) for row in rows]


@router.post("/prompts", status_code=201)
def add_prompt(payload: PromptVersionIn, db: Session = Depends(get_db), user: User = Depends(_admin)) -> dict:
    version = create_prompt_version(db, payload.prompt_key, payload.body, payload.note, user)
    db.commit()
    db.refresh(version)
    return _prompt_out(version)


@router.get("/feature-flags")
def flags(db: Session = Depends(get_db), user: User = Depends(_admin)) -> list[dict]:
    ensure_baseline(db, user.id)
    db.commit()
    rows = list(db.scalars(select(FeatureFlag).order_by(FeatureFlag.key)).all())
    return [{"id": row.id, "key": row.key, "enabled": row.enabled, "description": row.description} for row in rows]


@router.get("/secrets")
def secrets(db: Session = Depends(get_db), user: User = Depends(_admin)) -> list[dict]:
    rows = list(db.scalars(select(SecretReference).order_by(SecretReference.created_at.desc())).all())
    return [public_secret_ref(row) for row in rows]


def _draft(db: Session, draft_id: str) -> ConfigurationDraft:
    draft = db.get(ConfigurationDraft, draft_id)
    if draft is None:
        raise HTTPException(status_code=404, detail="Draft not found")
    return draft


def _draft_out(draft: ConfigurationDraft) -> dict:
    return {
        "id": draft.id,
        "status": draft.status,
        "proposed": _redact_proposed(draft.proposed_json or {}),
        "validation": draft.validation_json,
        "preview": draft.preview_json,
        "expected_revision_id": draft.expected_revision_id,
        "created_at": draft.created_at.isoformat() if draft.created_at else None,
    }


def _redact_proposed(proposed: dict) -> dict:
    clean = {}
    for key, value in proposed.items():
        definition = REGISTRY.get(key)
        if definition and definition.secret:
            clean[key] = {"configured": True, "redacted": True}
        else:
            clean[key] = value
    return clean


def _strip_probe_secrets(payload: dict) -> dict:
    clean = dict(payload)
    clean.pop("api_key", None)
    if "key_configured" not in clean:
        clean["key_configured"] = False
    return clean


def _prompt_out(row: PromptVersion) -> dict:
    return {
        "id": row.id,
        "prompt_key": row.prompt_key,
        "version": row.version,
        "body": row.body,
        "note": row.note,
        "parent_version": row.parent_version,
        "created_at": row.created_at.isoformat() if row.created_at else None,
    }


def _assert_no_secrets(payload: object) -> None:
    text = str(payload).lower()
    if "sk-" in text or "begin rsa" in text:
        raise HTTPException(status_code=500, detail="Export blocked: secret-shaped value")
