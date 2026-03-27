"""Token usage tracking utility for LLM and embedding operations."""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.token_usage import TokenUsageLog


# Approximate pricing per 1M tokens (USD) for common models
MODEL_PRICING = {
    # OpenAI
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4-turbo": {"prompt": 10.00, "completion": 30.00},
    "gpt-4": {"prompt": 30.00, "completion": 60.00},
    "gpt-3.5-turbo": {"prompt": 0.50, "completion": 1.50},
    "text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
    "text-embedding-3-large": {"prompt": 0.13, "completion": 0.0},
    "text-embedding-ada-002": {"prompt": 0.10, "completion": 0.0},
    # Anthropic
    "claude-3-5-sonnet": {"prompt": 3.00, "completion": 15.00},
    "claude-3-opus": {"prompt": 15.00, "completion": 75.00},
    "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
    # Google
    "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
}


def estimate_cost(model_name: str, prompt_tokens: int, completion_tokens: int) -> Optional[float]:
    """Estimate cost based on known model pricing."""
    # Try exact match first, then partial match
    pricing = MODEL_PRICING.get(model_name)
    if not pricing:
        for key, val in MODEL_PRICING.items():
            if key in model_name.lower() or model_name.lower() in key:
                pricing = val
                break
    if not pricing:
        return None

    cost = (prompt_tokens * pricing["prompt"] + completion_tokens * pricing["completion"]) / 1_000_000
    return round(cost, 6)


def extract_llm_token_usage(response) -> Dict[str, int]:
    """Extract token usage from a LangChain LLM response."""
    tokens = {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0}

    # Try usage_metadata (newer LangChain)
    if hasattr(response, "usage_metadata") and response.usage_metadata:
        meta = response.usage_metadata
        tokens["prompt_tokens"] = meta.get("input_tokens", 0) or meta.get("prompt_tokens", 0)
        tokens["completion_tokens"] = meta.get("output_tokens", 0) or meta.get("completion_tokens", 0)
        tokens["total_tokens"] = meta.get("total_tokens", 0) or (tokens["prompt_tokens"] + tokens["completion_tokens"])
        return tokens

    # Try response_metadata (older LangChain / OpenAI style)
    if hasattr(response, "response_metadata") and response.response_metadata:
        meta = response.response_metadata
        usage = meta.get("usage", meta.get("token_usage", {}))
        if usage:
            tokens["prompt_tokens"] = usage.get("prompt_tokens", 0) or usage.get("input_tokens", 0)
            tokens["completion_tokens"] = usage.get("completion_tokens", 0) or usage.get("output_tokens", 0)
            tokens["total_tokens"] = usage.get("total_tokens", 0) or (tokens["prompt_tokens"] + tokens["completion_tokens"])
            return tokens

    return tokens


def estimate_embedding_tokens(texts: list[str]) -> int:
    """Estimate token count for embedding texts (approx 1 token per 4 chars)."""
    total_chars = sum(len(t) for t in texts)
    return total_chars // 4


def log_token_usage(
    db: Session,
    operation: str,
    provider_name: str,
    model_name: str,
    model_type: str,
    prompt_tokens: int = 0,
    completion_tokens: int = 0,
    total_tokens: int = 0,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TokenUsageLog:
    """Save a token usage log entry to the database."""
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    cost = estimate_cost(model_name, prompt_tokens, completion_tokens)

    log = TokenUsageLog(
        operation=operation,
        experiment_id=experiment_id,
        combination_id=combination_id,
        provider_name=provider_name,
        model_name=model_name,
        model_type=model_type,
        prompt_tokens=prompt_tokens,
        completion_tokens=completion_tokens,
        total_tokens=total_tokens,
        estimated_cost=cost,
        extra_metadata=metadata,
    )
    db.add(log)
    db.commit()
    return log


def log_llm_response(
    db: Session,
    response,
    operation: str,
    provider_name: str,
    model_name: str,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TokenUsageLog:
    """Extract token usage from an LLM response and log it."""
    tokens = extract_llm_token_usage(response)
    return log_token_usage(
        db=db,
        operation=operation,
        provider_name=provider_name,
        model_name=model_name,
        model_type="llm",
        prompt_tokens=tokens["prompt_tokens"],
        completion_tokens=tokens["completion_tokens"],
        total_tokens=tokens["total_tokens"],
        experiment_id=experiment_id,
        combination_id=combination_id,
        metadata=metadata,
    )


def log_embedding_usage(
    db: Session,
    texts: list[str],
    operation: str,
    provider_name: str,
    model_name: str,
    experiment_id: Optional[int] = None,
    combination_id: Optional[int] = None,
    metadata: Optional[Dict[str, Any]] = None,
) -> TokenUsageLog:
    """Estimate and log embedding token usage."""
    estimated_tokens = estimate_embedding_tokens(texts)
    return log_token_usage(
        db=db,
        operation=operation,
        provider_name=provider_name,
        model_name=model_name,
        model_type="embedding",
        prompt_tokens=estimated_tokens,
        completion_tokens=0,
        total_tokens=estimated_tokens,
        experiment_id=experiment_id,
        combination_id=combination_id,
        metadata=metadata or {"num_texts": len(texts)},
    )
