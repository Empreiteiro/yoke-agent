"""Token usage tracking model for LLM and embedding operations."""

from sqlalchemy import Column, Integer, String, DateTime, Float, JSON, ForeignKey, func
from app.core.database import Base


class TokenUsageLog(Base):
    __tablename__ = "token_usage_logs"

    id = Column(Integer, primary_key=True, index=True)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    # Operation context
    operation = Column(String(50), nullable=False, index=True)  # dataset_generation, rag_pipeline, ragas_evaluation, provider_test
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True, index=True)
    combination_id = Column(Integer, ForeignKey("experiment_combinations.id", ondelete="SET NULL"), nullable=True)

    # Model info
    provider_name = Column(String(100), nullable=False)
    model_name = Column(String(100), nullable=False)
    model_type = Column(String(20), nullable=False)  # llm, embedding

    # Token counts
    prompt_tokens = Column(Integer, default=0)
    completion_tokens = Column(Integer, default=0)
    total_tokens = Column(Integer, default=0)

    # Cost estimation
    estimated_cost = Column(Float, nullable=True)

    # Extra context
    extra_metadata = Column(JSON, nullable=True)
