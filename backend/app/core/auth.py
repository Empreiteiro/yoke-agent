"""API Key authentication middleware."""

import hashlib
import logging
import time
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from app.core.database import SessionLocal
from app.models.api_key import ApiKey

logger = logging.getLogger(__name__)

EXEMPT_PREFIXES = ("/api/health", "/api/auth/", "/docs", "/openapi.json", "/redoc")

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


def _verify_key(key: str) -> bool:
    key_hash = hashlib.sha256(key.encode()).hexdigest()
    db = SessionLocal()
    try:
        return (
            db.query(ApiKey)
            .filter(ApiKey.key_hash == key_hash, ApiKey.is_active == True)  # noqa: E712
            .first()
            is not None
        )
    finally:
        db.close()


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Exempt paths
        if any(path.startswith(p) for p in EXEMPT_PREFIXES):
            return await call_next(request)

        # Bootstrap mode: no keys exist → allow all
        if not _has_active_keys():
            return await call_next(request)

        # Extract API key from headers
        api_key = request.headers.get("X-API-Key") or ""
        if not api_key:
            auth = request.headers.get("Authorization") or ""
            if auth.startswith("Bearer "):
                api_key = auth[7:]

        if not api_key:
            return JSONResponse(
                status_code=401,
                content={"detail": "API key required. Pass via X-API-Key header."},
            )

        if not _verify_key(api_key):
            return JSONResponse(
                status_code=401,
                content={"detail": "Invalid API key."},
            )

        return await call_next(request)
