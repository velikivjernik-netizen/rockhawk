from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.audit import log_event
from app.config import get_settings
from app.db import get_db
from app.deps import get_current_user
from app.models import User
from app.schemas import LoginIn, PasswordChange, TokenOut, UserOut
from app.security import create_access_token, hash_password, verify_password

router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/login", response_model=TokenOut)
def login(payload: LoginIn, db: Session = Depends(get_db)) -> TokenOut:
    user = db.scalar(select(User).where(User.email == payload.email.lower()))
    if user is None or not user.is_active or not verify_password(payload.password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password")
    log_event(db, action="auth.login", entity_type="user", entity_id=user.id, actor_id=user.id)
    db.commit()
    return TokenOut(access_token=create_access_token(user.id, user.role), must_change_password=user.must_change_password)


@router.get("/me", response_model=UserOut)
def me(user: User = Depends(get_current_user)) -> User:
    return user


@router.post("/change-password", response_model=UserOut)
def change_password(
    payload: PasswordChange,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
) -> User:
    if not verify_password(payload.current_password, user.hashed_password):
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail="Current password is incorrect")
    user.hashed_password = hash_password(payload.new_password)
    user.must_change_password = False
    log_event(db, action="auth.password_changed", entity_type="user", entity_id=user.id, actor_id=user.id)
    db.commit()
    db.refresh(user)
    return user


@router.get("/oidc/login")
def oidc_login() -> dict:
    settings = get_settings()
    if not settings.oidc_enabled:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail="OIDC is not configured. Set OIDC_ISSUER and OIDC_CLIENT_ID to enable the hook.",
        )
    return {
        "authorization_endpoint": f"{settings.oidc_issuer.rstrip('/')}/authorize",
        "client_id": settings.oidc_client_id,
        "redirect_uri": settings.oidc_redirect_uri,
        "response_type": "code",
        "scope": "openid email profile",
    }


@router.get("/oidc/callback")
def oidc_callback() -> dict:
    raise HTTPException(
        status_code=status.HTTP_501_NOT_IMPLEMENTED,
        detail="OIDC callback hook is reserved. Complete token exchange against your issuer to enable SSO.",
    )
