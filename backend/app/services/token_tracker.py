"""Token usage tracking utility for LLM and embedding operations."""

from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.token_usage import TokenUsageLog


# Approximate pricing per 1M tokens (USD) for common models.
# Keep the keys canonical (model slug as reported by the API); the
# `estimate_cost` helper also does a case-insensitive partial match so
# variants like "gpt-4o-2024-08-06" still resolve to the base price.
MODEL_PRICING = {
    # ── OpenAI ────────────────────────────────────────────────────────
    "gpt-4o": {"prompt": 2.50, "completion": 10.00},
    "gpt-4o-mini": {"prompt": 0.15, "completion": 0.60},
    "gpt-4.1": {"prompt": 2.00, "completion": 8.00},
    "gpt-4.1-mini": {"prompt": 0.40, "completion": 1.60},
    "gpt-4.1-nano": {"prompt": 0.10, "completion": 0.40},
    "gpt-4-turbo": {"prompt": 10.00, "completion": 30.00},
    "gpt-4": {"prompt": 30.00, "completion": 60.00},
    "gpt-3.5-turbo": {"prompt": 0.50, "completion": 1.50},
    "o3": {"prompt": 2.00, "completion": 8.00},
    "o3-mini": {"prompt": 1.10, "completion": 4.40},
    "o4-mini": {"prompt": 1.10, "completion": 4.40},
    "text-embedding-3-small": {"prompt": 0.02, "completion": 0.0},
    "text-embedding-3-large": {"prompt": 0.13, "completion": 0.0},
    "text-embedding-ada-002": {"prompt": 0.10, "completion": 0.0},
    # ── Anthropic ─────────────────────────────────────────────────────
    "claude-3-5-sonnet": {"prompt": 3.00, "completion": 15.00},
    "claude-sonnet-4": {"prompt": 3.00, "completion": 15.00},
    "claude-opus-4": {"prompt": 15.00, "completion": 75.00},
    "claude-3-opus": {"prompt": 15.00, "completion": 75.00},
    "claude-3-5-haiku": {"prompt": 0.80, "completion": 4.00},
    "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
    # ── Google Gemini ─────────────────────────────────────────────────
    # Source: https://ai.google.dev/pricing (paid tier, ≤128k context).
    # Gemini 2.5 Pro has tiered pricing; we use the ≤200k-token band.
    "gemini-2.5-pro": {"prompt": 1.25, "completion": 10.00},
    "gemini-2.5-flash": {"prompt": 0.30, "completion": 2.50},
    "gemini-2.0-flash": {"prompt": 0.10, "completion": 0.40},
    "gemini-2.0-flash-lite": {"prompt": 0.075, "completion": 0.30},
    "gemini-1.5-pro": {"prompt": 1.25, "completion": 5.00},
    "gemini-1.5-flash": {"prompt": 0.075, "completion": 0.30},
    # Gemini embeddings (input only; no completion cost).
    "gemini-embedding-001": {"prompt": 0.15, "completion": 0.0},
    "gemini-embedding-2-preview": {"prompt": 0.15, "completion": 0.0},
    # ── Cohere ────────────────────────────────────────────────────────
    "command-r-plus": {"prompt": 2.50, "completion": 10.00},
    "command-r": {"prompt": 0.15, "completion": 0.60},
    "embed-english-v3.0": {"prompt": 0.10, "completion": 0.0},
    "embed-multilingual-v3.0": {"prompt": 0.10, "completion": 0.0},
    # ── Claude Code CLI (local — no direct API cost) ─────────────────
    "claude-code": {"prompt": 0.0, "completion": 0.0},
    # ── TypeSafe decision models ──────────────────────────────────────
    # Jev bills input tokens only ($0.042 per 1M); output is free
    # (vendor-published early-access pricing, Sept 2026).
    "jev": {"prompt": 0.042, "completion": 0.0},
}


# Flex service-tier discount multiplier applied to prompt and
# completion prices. Both OpenAI and Google publish flex as roughly
# 50% of standard on-demand pricing for the models that support it
# (OpenAI: o3*, o4-mini, gpt-4.1*, gpt-5*; Google: gemini-2.5-* and
# gemini-3.x preview).
FLEX_DISCOUNT = 0.5


def lookup_pricing(model_name: str) -> Optional[Dict[str, float]]:
    """Return ``{"prompt": usd_per_1m, "completion": usd_per_1m}`` for a
    model, or None when the price is unknown. Exact match first, then a
    case-insensitive partial match (``gpt-4o-2024-08-06`` → ``gpt-4o``)."""
    if not model_name:
        return None
    pricing = MODEL_PRICING.get(model_name)
    if pricing:
        return pricing
    lowered = model_name.lower()
    for key, val in MODEL_PRICING.items():
        if key in lowered or lowered in key:
            return val
    return None


def estimate_cost(
    model_name: str,
    prompt_tokens: int,
    completion_tokens: int,
    flex: bool = False,
) -> Optional[float]:
    """Estimate cost based on known model pricing.

    Set ``flex=True`` to apply the flex service-tier discount
    (~50% off standard pricing). Applies to both OpenAI and Google
    flex-eligible models — callers should only set the flag when the
    model actually supports it (see ``llm_factory.flex_supported_for``).
    """
    pricing = lookup_pricing(model_name)
    if not pricing:
        return None

    prompt_price = pricing["prompt"]
    completion_price = pricing["completion"]
    if flex:
        prompt_price *= FLEX_DISCOUNT
        completion_price *= FLEX_DISCOUNT

    cost = (prompt_tokens * prompt_price + completion_tokens * completion_price) / 1_000_000
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


def detect_flex_tier(response) -> bool:
    """Return True if the LLM response was served via OpenAI's flex tier.

    OpenAI echoes back ``service_tier`` on the completion response when
    the request was submitted with ``service_tier=flex``. LangChain
    surfaces this under ``response_metadata``.
    """
    meta = getattr(response, "response_metadata", None) or {}
    tier = meta.get("service_tier") or meta.get("serviceTier")
    return isinstance(tier, str) and tier.lower() == "flex"


def estimate_embedding_tokens(texts: list[str]) -> int:
    """Estimate token count for embedding texts (approx 1 token per 4 chars)."""
    total_chars = sum(len(t) for t in texts)
    return total_chars // 4


def _estimate_chat_tokens(prompt_text: str, completion_text: str) -> Dict[str, int]:
    """Rough char/4 token estimate, used as a fallback for providers
    that don't surface usage metadata (Claude Code CLI, some HF
    endpoints). Not exact but good enough for rough accounting."""
    prompt_tokens = max(0, len(prompt_text or "") // 4)
    completion_tokens = max(0, len(completion_text or "") // 4)
    return {
        "prompt_tokens": prompt_tokens,
        "completion_tokens": completion_tokens,
        "total_tokens": prompt_tokens + completion_tokens,
    }


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
    flex: bool = False,
) -> TokenUsageLog:
    """Save a token usage log entry to the database."""
    if total_tokens == 0:
        total_tokens = prompt_tokens + completion_tokens

    cost = estimate_cost(model_name, prompt_tokens, completion_tokens, flex=flex)

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
    prompt_text: Optional[str] = None,
    flex_hint: bool = False,
) -> TokenUsageLog:
    """Extract token usage from an LLM response and log it.

    If the LLM response carries no usage metadata (e.g. Claude Code CLI,
    which returns a plain subprocess stdout string), and ``prompt_text``
    is provided, fall back to a rough char/4 estimate so the log entry
    still reflects the call.

    ``flex_hint`` lets the caller force the flex discount on cost
    estimation when the upstream API doesn't echo ``service_tier`` in
    the response (Gemini doesn't, OpenAI does). Pass ``True`` when the
    provider's ``extra_config.flex_tier`` is enabled — the helper will
    union it with what was actually detected on the response so cost
    estimates stay accurate either way.
    """
    tokens = extract_llm_token_usage(response)
    flex = detect_flex_tier(response) or flex_hint
    # If neither the response nor the caller hinted at flex, fall back
    # to looking up the provider's saved opt-in. Gemini doesn't echo
    # service_tier on responses, so without this lookup every Gemini
    # call would be priced at standard rates even when the provider
    # is configured for flex.
    if not flex:
        try:
            from app.models.provider import Provider
            prov = (
                db.query(Provider)
                .filter(Provider.name == provider_name)
                .first()
            )
            if prov and (prov.extra_config or {}).get("flex_tier"):
                flex = True
        except Exception:
            pass
    if flex:
        metadata = {**(metadata or {}), "service_tier": "flex"}

    # Fallback estimation for providers that don't surface usage metadata.
    if tokens["total_tokens"] == 0 and prompt_text is not None:
        response_text = getattr(response, "content", "") or str(response)
        estimated = _estimate_chat_tokens(prompt_text, response_text)
        tokens = estimated
        metadata = {**(metadata or {}), "tokens_estimated": True}

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
        flex=flex,
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
