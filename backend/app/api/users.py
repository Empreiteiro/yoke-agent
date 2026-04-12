"""User, session, and audit-log endpoints (issue #123).

Endpoints:

- ``POST /users/register`` — create a new account. The first account
  automatically becomes an ``admin`` so a fresh install has a way in.
- ``POST /users/login`` — exchange email + password for a JWT.
- ``GET /users/me`` — return the current user.
- ``GET /users`` — admin only; list users.
- ``PATCH /users/{user_id}/role`` — admin only; change a user's role.
- ``GET /users/audit-logs`` — admin only; paginated audit log.
"""

import json
import logging
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.security import (
    create_access_token,
    hash_password,
    verify_password,
)
from app.models.user import (
    AuditLog,
    ROLE_ADMIN,
    ROLE_USER,
    ROLE_VIEWER,
    User,
    VALID_ROLES,
)
from app.schemas.user import (
    AuditLogResponse,
    TokenResponse,
    UserLogin,
    UserRegister,
    UserResponse,
    UserRoleUpdate,
)

logger = logging.getLogger(__name__)

router = APIRouter()


# ── Dependencies ────────────────────────────────────────────────────────


def get_current_user(request: Request, db: Session = Depends(get_db)) -> User:
    """Resolve the current user from ``request.state.user_id`` (set by the
    auth middleware). Raises 401 if no user is attached."""
    user_id = getattr(request.state, "user_id", None)
    if not user_id:
        raise HTTPException(status_code=401, detail="Authentication required")
    user = db.query(User).filter(User.id == user_id, User.is_active == True).first()  # noqa: E712
    if not user:
        raise HTTPException(status_code=401, detail="User not found or inactive")
    return user


def require_admin(current: User = Depends(get_current_user)) -> User:
    if current.role != ROLE_ADMIN:
        raise HTTPException(status_code=403, detail="Admin role required")
    return current


def require_non_viewer(current: User = Depends(get_current_user)) -> User:
    if current.role == ROLE_VIEWER:
        raise HTTPException(status_code=403, detail="Viewers cannot perform this action")
    return current


# ── Auth endpoints ─────────────────────────────────────────────────────


@router.post("/register", response_model=TokenResponse)
def register(payload: UserRegister, db: Session = Depends(get_db)):
    existing = db.query(User).filter(User.email == payload.email.lower()).first()
    if existing:
        raise HTTPException(status_code=400, detail="Email already registered")

    # First registered user becomes admin so the install is bootstrappable.
    is_first = db.query(User).count() == 0
    role = ROLE_ADMIN if is_first else ROLE_USER

    user = User(
        email=payload.email.lower(),
        password_hash=hash_password(payload.password),
        role=role,
    )
    db.add(user)
    db.commit()
    db.refresh(user)

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.post("/login", response_model=TokenResponse)
def login(payload: UserLogin, db: Session = Depends(get_db)):
    user = db.query(User).filter(User.email == payload.email.lower()).first()
    if not user or not user.is_active or not verify_password(payload.password, user.password_hash):
        raise HTTPException(status_code=401, detail="Invalid email or password")

    token = create_access_token(user_id=user.id, email=user.email, role=user.role)
    return TokenResponse(access_token=token, user=UserResponse.model_validate(user))


@router.get("/me", response_model=UserResponse)
def read_me(current: User = Depends(get_current_user)):
    return current


# ── Admin endpoints ────────────────────────────────────────────────────


@router.get("/", response_model=list[UserResponse])
def list_users(
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    return db.query(User).order_by(User.created_at.desc()).all()


@router.patch("/{user_id}/role", response_model=UserResponse)
def update_user_role(
    user_id: int,
    payload: UserRoleUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    if payload.role not in VALID_ROLES:
        raise HTTPException(status_code=400, detail="Invalid role")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    user.role = payload.role
    db.commit()
    db.refresh(user)
    return user


@router.get("/audit-logs", response_model=list[AuditLogResponse])
def read_audit_logs(
    limit: int = 200,
    offset: int = 0,
    user_id: Optional[int] = None,
    db: Session = Depends(get_db),
    _: User = Depends(require_admin),
):
    q = db.query(AuditLog).order_by(AuditLog.created_at.desc())
    if user_id is not None:
        q = q.filter(AuditLog.user_id == user_id)
    return q.offset(offset).limit(min(limit, 1000)).all()
