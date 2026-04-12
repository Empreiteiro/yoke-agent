"""Trace and span models for production tracing (issue #179)."""

from sqlalchemy import Column, String, Integer, Float, DateTime, Text, JSON, ForeignKey, Index, func
from app.core.database import Base


class Trace(Base):
    __tablename__ = "traces"

    id = Column(String(32), primary_key=True)  # hex trace_id
    name = Column(String(255), nullable=False)
    status = Column(String(20), default="unset")  # ok, error, unset
    start_time = Column(DateTime, nullable=False, index=True)
    end_time = Column(DateTime)
    duration_ms = Column(Float)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=True, index=True)
    combination_id = Column(Integer, ForeignKey("experiment_combinations.id"), nullable=True)
    agent_experiment_id = Column(Integer, ForeignKey("agent_experiments.id"), nullable=True)
    source = Column(String(50), index=True)  # rag_pipeline, agent_simulation, collection_query, http_request
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True)
    metadata_ = Column("metadata", JSON)
    total_spans = Column(Integer, default=0)
    error_message = Column(Text)


class TraceSpan(Base):
    __tablename__ = "trace_spans"

    id = Column(String(32), primary_key=True)  # hex span_id
    trace_id = Column(String(32), ForeignKey("traces.id", ondelete="CASCADE"), nullable=False, index=True)
    parent_span_id = Column(String(32), nullable=True)
    name = Column(String(255), nullable=False)
    kind = Column(String(20), default="internal")  # internal, client, server
    status = Column(String(20), default="unset")
    start_time = Column(DateTime, nullable=False)
    end_time = Column(DateTime)
    duration_ms = Column(Float)
    attributes = Column(JSON)
    events = Column(JSON)
    error_message = Column(Text)

    __table_args__ = (
        Index("ix_trace_spans_trace_start", "trace_id", "start_time"),
    )
