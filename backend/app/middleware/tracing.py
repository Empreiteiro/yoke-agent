"""FastAPI middleware that wraps each HTTP request in a root trace (issue #179).

Skips health-check and documentation endpoints. The trace captures method,
path, status_code, duration, and (when available) the authenticated user_id.
"""

import time
from datetime import datetime, timezone

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

SKIP_PREFIXES = ("/api/health", "/docs", "/openapi.json", "/redoc")


class TracingMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next):
        from app.services.tracing import _is_enabled

        if not _is_enabled():
            return await call_next(request)

        path = request.url.path
        if any(path.startswith(p) for p in SKIP_PREFIXES):
            return await call_next(request)

        # Import here to avoid circular imports at startup
        from app.services.tracing import Tracer

        method = request.method
        user_id = getattr(request.state, "user_id", None)

        with Tracer(
            f"{method} {path}",
            source="http_request",
            user_id=user_id,
            metadata={"http.method": method, "http.path": path},
        ) as trace:
            with trace.span("handle_request", kind="server", attributes={
                "http.method": method,
                "http.url": str(request.url),
            }):
                response = await call_next(request)
                trace.add_span_attributes({
                    "http.status_code": response.status_code,
                })

        return response
