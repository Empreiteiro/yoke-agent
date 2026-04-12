"""Helpers for filtering SQLAlchemy queries by the current user (issue #123).

Endpoints that care about ownership call these helpers instead of querying
the model directly. The helpers honour three modes:

1. **No user attached** (bootstrap mode or frontend trusted origin): return
   the query unchanged. Back-compat with single-user installs.
2. **Admin user**: return the query unchanged — admins see everything.
3. **Regular user / viewer**: add a WHERE clause that restricts to rows
   owned by that user OR rows with ``user_id IS NULL`` (pre-existing data
   created before multi-tenancy was enabled; we treat it as shared).
"""

from typing import Optional

from fastapi import Request
from sqlalchemy import or_
from sqlalchemy.orm import Query

from app.models.user import ROLE_ADMIN


def current_user_id(request: Request) -> Optional[int]:
    return getattr(request.state, "user_id", None)


def current_user_role(request: Request) -> Optional[str]:
    return getattr(request.state, "user_role", None)


def scope_query(request: Request, query: Query, model) -> Query:
    """Restrict ``query`` to rows owned by the current user (or unowned)."""
    user_id = current_user_id(request)
    role = current_user_role(request)
    if user_id is None or role == ROLE_ADMIN:
        return query
    return query.filter(or_(model.user_id == user_id, model.user_id.is_(None)))


def assert_can_access(request: Request, row) -> None:
    """Raise 403 if ``row`` is owned by a different non-null user and the
    caller is not an admin. Rows with ``user_id is None`` are treated as
    shared (bootstrap data)."""
    from fastapi import HTTPException

    user_id = current_user_id(request)
    role = current_user_role(request)
    if user_id is None or role == ROLE_ADMIN:
        return
    owner = getattr(row, "user_id", None)
    if owner is None:
        return
    if owner != user_id:
        raise HTTPException(status_code=403, detail="You don't have access to this resource")
