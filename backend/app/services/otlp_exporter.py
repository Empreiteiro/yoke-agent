"""Optional OTLP HTTP exporter for shipping traces to Jaeger/Tempo (issue #179).

Activated only when ``OTEL_EXPORTER_OTLP_ENDPOINT`` (or the settings field
``otlp_endpoint``) is configured. Uses ``httpx`` (already a dependency) to
POST spans in OTLP JSON format. Export is best-effort — failures are logged
but never raise.
"""

import json
import logging
from datetime import datetime, timezone
from typing import Any

logger = logging.getLogger(__name__)

_endpoint: str | None = None


def _get_endpoint() -> str:
    global _endpoint
    if _endpoint is None:
        try:
            from app.core.config import settings
            _endpoint = settings.otlp_endpoint or ""
        except Exception:
            _endpoint = ""
    return _endpoint


def _get_service_name() -> str:
    try:
        from app.core.config import settings
        return settings.otlp_service_name or "yoke-agent"
    except Exception:
        return "yoke-agent"


def _dt_to_nano(dt: datetime | None) -> int:
    if dt is None:
        return 0
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return int(dt.timestamp() * 1_000_000_000)


def _to_otlp_value(v: Any) -> dict:
    if isinstance(v, bool):
        return {"boolValue": v}
    if isinstance(v, int):
        return {"intValue": str(v)}
    if isinstance(v, float):
        return {"doubleValue": v}
    return {"stringValue": str(v)}


def _to_otlp_attrs(attrs: dict | None) -> list:
    if not attrs:
        return []
    return [{"key": k, "value": _to_otlp_value(v)} for k, v in attrs.items() if v is not None]


def maybe_export(trace_id: str):
    """Export a trace if the OTLP endpoint is configured. Called from Tracer.__exit__."""
    endpoint = _get_endpoint()
    if not endpoint:
        return

    try:
        _export_trace(trace_id, endpoint)
    except Exception as e:
        logger.warning("OTLP export failed for trace %s: %s", trace_id, e)


def _export_trace(trace_id: str, endpoint: str):
    from app.core.database import SessionLocal
    from app.models.trace import Trace, TraceSpan

    db = SessionLocal()
    try:
        trace = db.query(Trace).filter(Trace.id == trace_id).first()
        if not trace:
            return
        spans = db.query(TraceSpan).filter(TraceSpan.trace_id == trace_id).all()
    finally:
        db.close()

    service_name = _get_service_name()

    otlp_spans = []
    for s in spans:
        otlp_span: dict[str, Any] = {
            "traceId": trace_id,
            "spanId": s.id,
            "name": s.name,
            "kind": {"internal": 1, "server": 2, "client": 3}.get(s.kind, 1),
            "startTimeUnixNano": str(_dt_to_nano(s.start_time)),
            "endTimeUnixNano": str(_dt_to_nano(s.end_time)),
            "attributes": _to_otlp_attrs(s.attributes),
            "status": {
                "code": {"ok": 1, "error": 2}.get(s.status, 0),
                "message": s.error_message or "",
            },
        }
        if s.parent_span_id:
            otlp_span["parentSpanId"] = s.parent_span_id
        if s.events:
            otlp_span["events"] = [
                {
                    "name": e.get("name", ""),
                    "timeUnixNano": str(_dt_to_nano(
                        datetime.fromisoformat(e["timestamp"]) if isinstance(e.get("timestamp"), str) else e.get("timestamp")
                    )) if e.get("timestamp") else "0",
                    "attributes": _to_otlp_attrs(e.get("attributes")),
                }
                for e in s.events
            ]
        otlp_spans.append(otlp_span)

    payload = {
        "resourceSpans": [
            {
                "resource": {
                    "attributes": _to_otlp_attrs({"service.name": service_name}),
                },
                "scopeSpans": [
                    {
                        "scope": {"name": "yoke-agent-tracer", "version": "0.1.0"},
                        "spans": otlp_spans,
                    }
                ],
            }
        ]
    }

    import httpx
    url = endpoint.rstrip("/")
    if not url.endswith("/v1/traces"):
        url += "/v1/traces"
    resp = httpx.post(url, json=payload, timeout=10)
    if resp.status_code >= 400:
        logger.warning("OTLP export returned %d: %s", resp.status_code, resp.text[:200])
