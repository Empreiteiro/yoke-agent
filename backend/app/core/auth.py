"""API Key + JWT authentication middleware.

Frontend (trusted) requests are exempt — identified by Origin/Referer
matching configured CORS origins. External access uses one of:

- ``Authorization: Bearer <jwt>`` — user session issued by ``/api/users/login``.
- ``X-API-Key`` / ``Authorization: Bearer <api_key>`` — long-lived key for the
  MCP server and third-party integrations.

When a JWT is present and valid, ``request.state.user_id``,
``request.state.user_email`` and ``request.state.user_role`` are populated so
downstream endpoints can filter by ownership and enforce RBAC.
"""

import hashlib
import json
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.api_key import ApiKey
from app.models.user import AuditLog, User

logger = logging.getLogger(__name__)

EXEMPT_PREFIXES = (
    "/api/health",
    "/api/auth/",
    "/api/users/register",
    "/api/users/login",
    "/docs",
    "/openapi.json",
    "/redoc",
)

# Cache for bootstrap mode check (avoid DB query per request)
_cache = {"has_keys": False, "checked_at": 0.0}
_CACHE_TTL = 10  # seconds


def _has_active_keys() -> bool:
    now = time.time()
    if now - _cache["checked_at"] < _CACHE_TTL:
        return _cache["has_keys"]

    db = SessionLocal()
    try:
        count = db.query(ApiKey).filter(ApiKey.is_active == True).count()  # noqa: E712
        _cache["has_keys"] = count > 0
        _cache["checked_at"] = now
        return _cache["has_keys"]
    finally:
        db.close()


def invalidate_key_cache():
    """Call after creating/deleting keys to force recheck."""
    _cache["checked_at"] = 0.0


def _verify_key(key: str) -> tuple[bool, int | None]:
    """Return ``(is_valid, owning_user_id)`` for an API key."""
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    db = SessionLocal()
    try:
        row = (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True)  # noqa: E712
            .first()
        )
        if row is None:
            return False, None
        return True, row.user_id
    finally:
        db.close()


def _write_audit_log(
    *,
    user_id: int | None,
    user_email: str | None,
    action: str,
    resource: str,
    status_code: int,
    ip_address: str | None,
):
    """Best-effort append to the audit_logs table."""
    try:
        db = SessionLocal()
        try:
            db.add(
                AuditLog(
                    user_id=user_id,
                    user_email=user_email,
                    action=action,
                    resource=resource,
                    status_code=status_code,
                    ip_address=ip_address,
                )
            )
            db.commit()
        finally:
            db.close()
    except Exception as e:  # pragma: no cover — logging must never break a request
        logger.warning("Failed to write audit log: %s", e)


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Always initialise so downstream code can read without defaulting.
        request.state.user_id = None
        request.state.user_email = None
        request.state.user_role = None

        # Exempt paths (health, docs, auth endpoints)
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await self._dispatch_and_audit(request, call_next)

        # Extract credential headers up front — we try JWT before falling back
        # to the long-lived API key path so an authenticated user session takes
        # precedence over the shared studio key.
        jwt_token: str | None = None
        api_key: str | None = request.headers.get("X-API-Key") or None
        auth_header = request.headers.get("Authorization") or ""
        if auth_header.startswith("Bearer "):
            token = auth_header[7:]
            # Heuristic: JWTs have two dots; API keys start with "rag_".
            if token.count(".") == 2:
                jwt_token = token
            elif api_key is None:
                api_key = token

        if jwt_token:
            claims = decode_access_token(jwt_token)
            if claims:
                try:
                    request.state.user_id = int(claims.get("sub"))
                except (TypeError, ValueError):
                    request.state.user_id = None
                request.state.user_email = claims.get("email")
                request.state.user_role = claims.get("role")
                return await self._dispatch_and_audit(request, call_next)
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid or expired token."},
            )

        # Trust requests from the frontend (Origin/Referer matches CORS origins)
        origin = request.headers.get("origin", "")
        referer = request.headers.get("referer", "")
        frontend_trusted = False
        for allowed in settings.cors_origins:
            if origin == allowed or referer.startswith(allowed):
                frontend_trusted = True
                break
        if frontend_trusted:
            return await self._dispatch_and_audit(request, call_next)

        # Bootstrap mode: no keys AND no users → allow all
        if not _has_active_keys():
            return await self._dispatch_and_audit(request, call_next)

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "Authentication required."},
            )

        is_valid, owning_user_id = _verify_key(api_key)
        if not is_valid:
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key."},
            )

        if owning_user_id is not None:
            # Resolve the owning user so endpoints can filter by ownership.
            request.state.user_id = owning_user_id
            try:
                db = SessionLocal()
                try:
                    u = db.query(User).filter(User.id == owning_user_id).first()
                    if u:
                        request.state.user_email = u.email
                        request.state.user_role = u.role
                finally:
                    db.close()
            except Exception:  # pragma: no cover
                pass

        return await self._dispatch_and_audit(request, call_next)

    async def _dispatch_and_audit(self, request: Request, call_next):
        response = await call_next(request)
        try:
            path = request.url.path
            if not path.startswith("/api/health") and not path.startswith("/docs"):
                _write_audit_log(
                    user_id=getattr(request.state, "user_id", None),
                    user_email=getattr(request.state, "user_email", None),
                    action=request.method,
                    resource=path,
                    status_code=response.status_code,
                    ip_address=request.client.host if request.client else None,
                )
        except Exception:  # pragma: no cover
            pass
        return response
