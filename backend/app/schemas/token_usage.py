"""Schemas for token usage log API."""

from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class TokenUsageResponse(BaseModel):
    id: int
    created_at: datetime
    operation: str
    experiment_id: Optional[int] = None
    combination_id: Optional[int] = None
    provider_name: str
    model_name: str
    model_type: str
    prompt_tokens: int
    completion_tokens: int
    total_tokens: int
    estimated_cost: Optional[float] = None
    metadata: Optional[dict] = None

    class Config:
        from_attributes = True


class TokenUsageSummary(BaseModel):
    total_prompt_tokens: int = 0
    total_completion_tokens: int = 0
    total_tokens: int = 0
    total_estimated_cost: float = 0.0
    total_llm_tokens: int = 0
    total_embedding_tokens: int = 0
    by_model: list[dict] = []
    by_operation: list[dict] = []
    by_day: list[dict] = []
