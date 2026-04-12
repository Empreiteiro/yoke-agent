"""Lightweight OTEL-compatible tracing for Yoke Agent (issue #179).

Provides a ``Tracer`` context manager and ``@traced`` decorator that
instrument functions as hierarchical spans. Spans are persisted to
SQLite and optionally exported to any OTLP-compatible collector.

The system is async-safe (uses ``contextvars``) and has a noop mode
with zero overhead when ``settings.tracing_enabled`` is ``False``.

Usage::

    from app.services.tracing import Tracer

    async def run_pipeline():
        with Tracer("rag_pipeline", source="rag_pipeline", experiment_id=42) as trace:
            with trace.span("chunk_documents", attributes={"chunk_size": 512}):
                chunks = chunk_documents(...)
            with trace.span("llm_generate", kind="client"):
                response = await llm.ainvoke(prompt)
                trace.add_span_attributes({"tokens": 150})
"""

from __future__ import annotations

import contextvars
import functools
import logging
import os
import time
from contextlib import contextmanager
from datetime import datetime, timezone
from typing import Any, Callable, Optional

logger = logging.getLogger(__name__)

# ── Lazy config check ───────────────────────────────────────────────────

_enabled: Optional[bool] = None


def _is_enabled() -> bool:
    global _enabled
    if _enabled is None:
        try:
            from app.core.config import settings
            _enabled = settings.tracing_enabled
        except Exception:
            _enabled = False
    return _enabled


# ── ID generation ───────────────────────────────────────────────────────

def _hex_id(n_bytes: int = 16) -> str:
    return os.urandom(n_bytes).hex()


# ── Context variable for async-safe trace propagation ───────────────────

class _TraceContext:
    __slots__ = ("trace_id", "spans", "source", "experiment_id",
                 "combination_id", "agent_experiment_id", "user_id",
                 "_span_stack", "_db_session")

    def __init__(
        self,
        trace_id: str,
        source: str,
        experiment_id: Optional[int] = None,
        combination_id: Optional[int] = None,
        agent_experiment_id: Optional[int] = None,
        user_id: Optional[int] = None,
    ):
        self.trace_id = trace_id
        self.source = source
        self.experiment_id = experiment_id
        self.combination_id = combination_id
        self.agent_experiment_id = agent_experiment_id
        self.user_id = user_id
        self.spans: list[dict] = []
        self._span_stack: list[str] = []  # stack of span_ids
        self._db_session = None


_trace_ctx: contextvars.ContextVar[Optional[_TraceContext]] = contextvars.ContextVar(
    "yoke_trace_ctx", default=None,
)


def get_current_trace_id() -> Optional[str]:
    ctx = _trace_ctx.get()
    return ctx.trace_id if ctx else None


def get_current_span_id() -> Optional[str]:
    ctx = _trace_ctx.get()
    if ctx and ctx._span_stack:
        return ctx._span_stack[-1]
    return None


# ── Noop implementation ─────────────────────────────────────────────────

class _NoopSpan:
    def __enter__(self): return self
    def __exit__(self, *_): pass


class _NoopTracer:
    def __enter__(self): return self
    def __exit__(self, *_): pass
    def span(self, name: str = "", **kw): return _NoopSpan()
    def add_span_attributes(self, attrs: dict): pass
    def add_span_event(self, name: str, attributes: dict | None = None): pass


_NOOP = _NoopTracer()


# ── Real Tracer ─────────────────────────────────────────────────────────

class Tracer:
    """Create and manage a trace with nested spans.

    When tracing is disabled this returns a lightweight noop proxy.
    """

    def __new__(cls, *args, **kwargs):
        if not _is_enabled():
            return _NOOP
        return super().__new__(cls)

    def __init__(
        self,
        name: str,
        *,
        source: str = "unknown",
        experiment_id: Optional[int] = None,
        combination_id: Optional[int] = None,
        agent_experiment_id: Optional[int] = None,
        user_id: Optional[int] = None,
        metadata: Optional[dict] = None,
    ):
        self._name = name
        self._source = source
        self._experiment_id = experiment_id
        self._combination_id = combination_id
        self._agent_experiment_id = agent_experiment_id
        self._user_id = user_id
        self._metadata = metadata or {}
        self._trace_id = _hex_id(16)
        self._start = datetime.now(timezone.utc)
        self._start_mono = time.monotonic()
        self._ctx: Optional[_TraceContext] = None
        self._token: Optional[contextvars.Token] = None

    def __enter__(self):
        self._ctx = _TraceContext(
            trace_id=self._trace_id,
            source=self._source,
            experiment_id=self._experiment_id,
            combination_id=self._combination_id,
            agent_experiment_id=self._agent_experiment_id,
            user_id=self._user_id,
        )
        self._token = _trace_ctx.set(self._ctx)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        elapsed = (time.monotonic() - self._start_mono) * 1000
        status = "error" if exc_type else "ok"
        error_msg = str(exc_val) if exc_val else None

        # Persist trace + spans
        try:
            self._persist(elapsed, status, error_msg)
        except Exception as e:
            logger.warning("Failed to persist trace %s: %s", self._trace_id, e)

        # Restore context
        if self._token is not None:
            _trace_ctx.reset(self._token)

        # Optional OTLP export
        try:
            from app.services.otlp_exporter import maybe_export
            maybe_export(self._trace_id)
        except Exception:
            pass

        return False  # don't suppress exceptions

    @contextmanager
    def span(
        self,
        name: str,
        *,
        kind: str = "internal",
        attributes: Optional[dict] = None,
    ):
        """Create a child span within the current trace."""
        ctx = _trace_ctx.get()
        if ctx is None:
            yield
            return

        span_id = _hex_id(8)
        parent_id = ctx._span_stack[-1] if ctx._span_stack else None
        start = datetime.now(timezone.utc)
        mono_start = time.monotonic()
        span_attrs = dict(attributes or {})
        span_events: list[dict] = []

        ctx._span_stack.append(span_id)
        # Store refs for add_span_attributes / add_span_event
        self._current_span_attrs = span_attrs
        self._current_span_events = span_events

        try:
            yield
            span_status = "ok"
            span_error = None
        except Exception as e:
            span_status = "error"
            span_error = str(e)
            span_events.append({
                "name": "exception",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attributes": {"exception.message": str(e), "exception.type": type(e).__name__},
            })
            raise
        finally:
            elapsed = (time.monotonic() - mono_start) * 1000
            ctx._span_stack.pop()
            ctx.spans.append({
                "id": span_id,
                "trace_id": ctx.trace_id,
                "parent_span_id": parent_id,
                "name": name,
                "kind": kind,
                "status": span_status,
                "start_time": start,
                "end_time": datetime.now(timezone.utc),
                "duration_ms": elapsed,
                "attributes": span_attrs if span_attrs else None,
                "events": span_events if span_events else None,
                "error_message": span_error,
            })

    def add_span_attributes(self, attrs: dict):
        """Merge attributes into the currently open span."""
        if hasattr(self, "_current_span_attrs"):
            self._current_span_attrs.update(attrs)

    def add_span_event(self, name: str, attributes: Optional[dict] = None):
        if hasattr(self, "_current_span_events"):
            self._current_span_events.append({
                "name": name,
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "attributes": attributes or {},
            })

    # ── Persistence ─────────────────────────────────────────────────────

    def _persist(self, duration_ms: float, status: str, error_message: Optional[str]):
        from app.core.database import SessionLocal
        from app.models.trace import Trace, TraceSpan

        db = SessionLocal()
        try:
            trace = Trace(
                id=self._trace_id,
                name=self._name,
                status=status,
                start_time=self._start,
                end_time=datetime.now(timezone.utc),
                duration_ms=duration_ms,
                experiment_id=self._experiment_id,
                combination_id=self._combination_id,
                agent_experiment_id=self._agent_experiment_id,
                source=self._source,
                user_id=self._user_id,
                metadata_=self._metadata,
                total_spans=len(self._ctx.spans) if self._ctx else 0,
                error_message=error_message,
            )
            db.add(trace)

            if self._ctx:
                for s in self._ctx.spans:
                    db.add(TraceSpan(
                        id=s["id"],
                        trace_id=s["trace_id"],
                        parent_span_id=s["parent_span_id"],
                        name=s["name"],
                        kind=s["kind"],
                        status=s["status"],
                        start_time=s["start_time"],
                        end_time=s["end_time"],
                        duration_ms=s["duration_ms"],
                        attributes=s["attributes"],
                        events=s["events"],
                        error_message=s["error_message"],
                    ))

            db.commit()
        except Exception as e:
            logger.warning("Trace persistence failed: %s", e)
            db.rollback()
        finally:
            db.close()


# ── Decorator ───────────────────────────────────────────────────────────

def traced(name: str, *, kind: str = "internal"):
    """Decorator that wraps a function call in a span within the current trace.

    If no trace is active (or tracing is disabled) the function runs unmodified.
    """
    def decorator(fn: Callable):
        if not _is_enabled():
            return fn

        @functools.wraps(fn)
        def wrapper(*args, **kwargs):
            ctx = _trace_ctx.get()
            if ctx is None:
                return fn(*args, **kwargs)
            # Find the active Tracer — we create a lightweight span proxy.
            span_id = _hex_id(8)
            parent_id = ctx._span_stack[-1] if ctx._span_stack else None
            start = datetime.now(timezone.utc)
            mono_start = time.monotonic()
            ctx._span_stack.append(span_id)
            try:
                result = fn(*args, **kwargs)
                span_status = "ok"
                span_error = None
                return result
            except Exception as e:
                span_status = "error"
                span_error = str(e)
                raise
            finally:
                elapsed = (time.monotonic() - mono_start) * 1000
                ctx._span_stack.pop()
                ctx.spans.append({
                    "id": span_id,
                    "trace_id": ctx.trace_id,
                    "parent_span_id": parent_id,
                    "name": name,
                    "kind": kind,
                    "status": span_status,
                    "start_time": start,
                    "end_time": datetime.now(timezone.utc),
                    "duration_ms": elapsed,
                    "attributes": None,
                    "events": None,
                    "error_message": span_error,
                })
        return wrapper
    return decorator
