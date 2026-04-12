"""Trace browsing API (issue #179)."""

from datetime import datetime, timedelta, timezone
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.core.database import get_db
from app.models.trace import Trace, TraceSpan
from app.schemas.trace import (
    TraceListItem,
    TraceDetailResponse,
    SpanResponse,
    TraceSummaryResponse,
)

router = APIRouter()


@router.get("/", response_model=list[TraceListItem])
def list_traces(
    source: Optional[str] = None,
    status: Optional[str] = None,
    experiment_id: Optional[int] = None,
    agent_experiment_id: Optional[int] = None,
    days: int = Query(7, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    q = db.query(Trace).filter(Trace.start_time >= cutoff)
    if source:
        q = q.filter(Trace.source == source)
    if status:
        q = q.filter(Trace.status == status)
    if experiment_id is not None:
        q = q.filter(Trace.experiment_id == experiment_id)
    if agent_experiment_id is not None:
        q = q.filter(Trace.agent_experiment_id == agent_experiment_id)
    return q.order_by(Trace.start_time.desc()).offset(offset).limit(limit).all()


@router.get("/summary", response_model=TraceSummaryResponse)
def traces_summary(
    days: int = Query(7, ge=1, le=365),
    db: Session = Depends(get_db),
):
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    base = db.query(Trace).filter(Trace.start_time >= cutoff)

    total = base.count()
    avg_dur = base.with_entities(sqlfunc.avg(Trace.duration_ms)).scalar()

    by_source: dict[str, int] = {}
    for row in base.with_entities(Trace.source, sqlfunc.count()).group_by(Trace.source).all():
        by_source[row[0] or "unknown"] = row[1]

    by_status: dict[str, int] = {}
    for row in base.with_entities(Trace.status, sqlfunc.count()).group_by(Trace.status).all():
        by_status[row[0] or "unset"] = row[1]

    return TraceSummaryResponse(
        total_traces=total,
        by_source=by_source,
        by_status=by_status,
        avg_duration_ms=round(avg_dur, 2) if avg_dur else None,
    )


@router.get("/{trace_id}", response_model=TraceDetailResponse)
def get_trace(trace_id: str, db: Session = Depends(get_db)):
    trace = db.query(Trace).filter(Trace.id == trace_id).first()
    if not trace:
        raise HTTPException(404, "Trace not found")

    spans = (
        db.query(TraceSpan)
        .filter(TraceSpan.trace_id == trace_id)
        .order_by(TraceSpan.start_time)
        .all()
    )

    # Build tree
    span_map: dict[str, SpanResponse] = {}
    roots: list[SpanResponse] = []
    for s in spans:
        node = SpanResponse(
            id=s.id,
            trace_id=s.trace_id,
            parent_span_id=s.parent_span_id,
            name=s.name,
            kind=s.kind or "internal",
            status=s.status or "unset",
            start_time=s.start_time,
            end_time=s.end_time,
            duration_ms=s.duration_ms,
            attributes=s.attributes,
            events=s.events,
            error_message=s.error_message,
            children=[],
        )
        span_map[s.id] = node

    for node in span_map.values():
        if node.parent_span_id and node.parent_span_id in span_map:
            span_map[node.parent_span_id].children.append(node)
        else:
            roots.append(node)

    return TraceDetailResponse(
        id=trace.id,
        name=trace.name,
        status=trace.status,
        start_time=trace.start_time,
        end_time=trace.end_time,
        duration_ms=trace.duration_ms,
        source=trace.source,
        experiment_id=trace.experiment_id,
        combination_id=trace.combination_id,
        agent_experiment_id=trace.agent_experiment_id,
        user_id=trace.user_id,
        metadata=trace.metadata_,
        total_spans=trace.total_spans,
        error_message=trace.error_message,
        spans=roots,
    )


@router.delete("/{trace_id}")
def delete_trace(trace_id: str, db: Session = Depends(get_db)):
    trace = db.query(Trace).filter(Trace.id == trace_id).first()
    if not trace:
        raise HTTPException(404, "Trace not found")
    db.query(TraceSpan).filter(TraceSpan.trace_id == trace_id).delete()
    db.delete(trace)
    db.commit()
    return {"detail": "Trace deleted"}
