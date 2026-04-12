"""Pydantic schemas for the traces API (issue #179)."""

from datetime import datetime
from typing import Any, Optional
from pydantic import BaseModel


class SpanResponse(BaseModel):
    id: str
    trace_id: str
    parent_span_id: Optional[str] = None
    name: str
    kind: str = "internal"
    status: str = "unset"
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    attributes: Optional[dict] = None
    events: Optional[list] = None
    error_message: Optional[str] = None
    children: list["SpanResponse"] = []

    class Config:
        from_attributes = True


class TraceListItem(BaseModel):
    id: str
    name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    source: Optional[str] = None
    experiment_id: Optional[int] = None
    combination_id: Optional[int] = None
    agent_experiment_id: Optional[int] = None
    total_spans: int = 0
    error_message: Optional[str] = None

    class Config:
        from_attributes = True


class TraceDetailResponse(BaseModel):
    id: str
    name: str
    status: str
    start_time: datetime
    end_time: Optional[datetime] = None
    duration_ms: Optional[float] = None
    source: Optional[str] = None
    experiment_id: Optional[int] = None
    combination_id: Optional[int] = None
    agent_experiment_id: Optional[int] = None
    user_id: Optional[int] = None
    metadata: Optional[dict] = None
    total_spans: int = 0
    error_message: Optional[str] = None
    spans: list[SpanResponse] = []

    class Config:
        from_attributes = True


class TraceSummaryResponse(BaseModel):
    total_traces: int = 0
    by_source: dict[str, int] = {}
    by_status: dict[str, int] = {}
    avg_duration_ms: Optional[float] = None
