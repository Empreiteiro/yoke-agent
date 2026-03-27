"""Token usage log API routes."""

from datetime import datetime, timedelta
from typing import Optional
from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, case
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.token_usage import TokenUsageLog
from app.schemas.token_usage import TokenUsageResponse, TokenUsageSummary

router = APIRouter()


@router.get("/", response_model=list[TokenUsageResponse])
def list_token_usage(
    operation: Optional[str] = Query(None),
    model_type: Optional[str] = Query(None),
    model_name: Optional[str] = Query(None),
    experiment_id: Optional[int] = Query(None),
    days: int = Query(30, ge=1, le=365),
    limit: int = Query(100, ge=1, le=1000),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db),
):
    """List token usage logs with optional filters."""
    since = datetime.utcnow() - timedelta(days=days)
    query = db.query(TokenUsageLog).filter(TokenUsageLog.created_at >= since)

    if operation:
        query = query.filter(TokenUsageLog.operation == operation)
    if model_type:
        query = query.filter(TokenUsageLog.model_type == model_type)
    if model_name:
        query = query.filter(TokenUsageLog.model_name.contains(model_name))
    if experiment_id:
        query = query.filter(TokenUsageLog.experiment_id == experiment_id)

    return query.order_by(TokenUsageLog.created_at.desc()).offset(offset).limit(limit).all()


@router.get("/summary", response_model=TokenUsageSummary)
def get_token_usage_summary(
    days: int = Query(30, ge=1, le=365),
    experiment_id: Optional[int] = Query(None),
    db: Session = Depends(get_db),
):
    """Get aggregated token usage summary."""
    since = datetime.utcnow() - timedelta(days=days)
    base_query = db.query(TokenUsageLog).filter(TokenUsageLog.created_at >= since)

    if experiment_id:
        base_query = base_query.filter(TokenUsageLog.experiment_id == experiment_id)

    # Totals
    totals = base_query.with_entities(
        func.coalesce(func.sum(TokenUsageLog.prompt_tokens), 0).label("prompt"),
        func.coalesce(func.sum(TokenUsageLog.completion_tokens), 0).label("completion"),
        func.coalesce(func.sum(TokenUsageLog.total_tokens), 0).label("total"),
        func.coalesce(func.sum(TokenUsageLog.estimated_cost), 0.0).label("cost"),
        func.coalesce(func.sum(
            case((TokenUsageLog.model_type == "llm", TokenUsageLog.total_tokens), else_=0)
        ), 0).label("llm_tokens"),
        func.coalesce(func.sum(
            case((TokenUsageLog.model_type == "embedding", TokenUsageLog.total_tokens), else_=0)
        ), 0).label("embedding_tokens"),
    ).first()

    # By model
    by_model = (
        base_query.with_entities(
            TokenUsageLog.model_name,
            TokenUsageLog.model_type,
            func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
            func.sum(TokenUsageLog.estimated_cost).label("estimated_cost"),
            func.count().label("call_count"),
        )
        .group_by(TokenUsageLog.model_name, TokenUsageLog.model_type)
        .order_by(func.sum(TokenUsageLog.total_tokens).desc())
        .all()
    )

    # By operation
    by_operation = (
        base_query.with_entities(
            TokenUsageLog.operation,
            func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
            func.sum(TokenUsageLog.estimated_cost).label("estimated_cost"),
            func.count().label("call_count"),
        )
        .group_by(TokenUsageLog.operation)
        .order_by(func.sum(TokenUsageLog.total_tokens).desc())
        .all()
    )

    # By day
    by_day = (
        base_query.with_entities(
            func.date(TokenUsageLog.created_at).label("date"),
            func.sum(TokenUsageLog.total_tokens).label("total_tokens"),
            func.sum(TokenUsageLog.estimated_cost).label("estimated_cost"),
            func.count().label("call_count"),
        )
        .group_by(func.date(TokenUsageLog.created_at))
        .order_by(func.date(TokenUsageLog.created_at).asc())
        .all()
    )

    return TokenUsageSummary(
        total_prompt_tokens=totals.prompt,
        total_completion_tokens=totals.completion,
        total_tokens=totals.total,
        total_estimated_cost=round(totals.cost, 4),
        total_llm_tokens=totals.llm_tokens,
        total_embedding_tokens=totals.embedding_tokens,
        by_model=[
            {
                "model_name": r.model_name,
                "model_type": r.model_type,
                "total_tokens": r.total_tokens,
                "estimated_cost": round(r.estimated_cost or 0, 4),
                "call_count": r.call_count,
            }
            for r in by_model
        ],
        by_operation=[
            {
                "operation": r.operation,
                "total_tokens": r.total_tokens,
                "estimated_cost": round(r.estimated_cost or 0, 4),
                "call_count": r.call_count,
            }
            for r in by_operation
        ],
        by_day=[
            {
                "date": str(r.date),
                "total_tokens": r.total_tokens,
                "estimated_cost": round(r.estimated_cost or 0, 4),
                "call_count": r.call_count,
            }
            for r in by_day
        ],
    )
