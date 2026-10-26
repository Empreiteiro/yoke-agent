"""Token usage tracking utility for LLM and embedding operations."""

from datetime import date
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

from app.models.token_usage import TokenUsageLog


# Approximate pricing per 1M tokens (USD) for common models.
# Keep the keys canonical (model slug as reported by the API); the
# `estimate_cost` helper also does a case-insensitive partial match so
# variants like "gpt-4o-2024-08-06" still resolve to the base price.
# Standard tier, short-context band: long-prompt surcharges (OpenAI
# >272K, Gemini Pro >200K, Claude Haiku 5.5 >100K) are not modelled.
# Deprecated / retired models stay listed so older usage is still priced.
MODEL_PRICING = {
    # ── OpenAI (developers.openai.com/api/docs/pricing, Oct 2026) ─────
    "gpt-6-astra": {"prompt": 10.00, "completion": 50.00},
    "gpt-6.1-sol": {"prompt": 2.00, "completion": 10.00},
    "gpt-6-luna": {"prompt": 0.10, "completion": 0.50},
    # Promotional $4/$20 through Nov 20, 2026 — see PRICE_CHANGES.
    "gpt-5.6-sol": {"prompt": 4.00, "completion": 20.00},
    "gpt-5.6-terra": {"prompt": 2.00, "completion": 12.00},
    "gpt-5.5": {"prompt": 5.00, "completion": 30.00},
    "gpt-5.4": {"prompt": 2.50, "completion": 15.00},
    "gpt-5.4-mini": {"prompt": 0.75, "completion": 4.50},
    "gpt-5.4-nano": {"prompt": 0.20, "completion": 1.25},
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
    # ── Anthropic (platform.claude.com pricing, Oct 2026) ─────────────
    "claude-fable-5-1": {"prompt": 10.00, "completion": 50.00},
    "claude-fable-5": {"prompt": 10.00, "completion": 50.00},
    "claude-opus-5-5": {"prompt": 4.00, "completion": 20.00},
    "claude-opus-5": {"prompt": 5.00, "completion": 25.00},
    "claude-opus-4-8": {"prompt": 5.00, "completion": 25.00},
    "claude-opus-4-7": {"prompt": 5.00, "completion": 25.00},
    "claude-opus-4-6": {"prompt": 5.00, "completion": 25.00},
    "claude-sonnet-5-5": {"prompt": 2.00, "completion": 10.00},
    "claude-sonnet-5": {"prompt": 2.00, "completion": 10.00},
    "claude-sonnet-4-6": {"prompt": 3.00, "completion": 15.00},
    "claude-haiku-5-5": {"prompt": 0.10, "completion": 0.50},
    "claude-haiku-4-5": {"prompt": 1.00, "completion": 5.00},
    "claude-3-5-sonnet": {"prompt": 3.00, "completion": 15.00},
    "claude-sonnet-4": {"prompt": 3.00, "completion": 15.00},
    "claude-opus-4": {"prompt": 15.00, "completion": 75.00},
    "claude-3-opus": {"prompt": 15.00, "completion": 75.00},
    "claude-3-5-haiku": {"prompt": 0.80, "completion": 4.00},
    "claude-3-haiku": {"prompt": 0.25, "completion": 1.25},
    # ── Google Gemini ─────────────────────────────────────────────────
    # Source: https://ai.google.dev/gemini-api/docs/pricing (paid tier).
    # Pro models have tiered pricing; we use the ≤200k-token band.
    # Gemini 4 Argon and 3.8 Flash are on introductory prices — the
    # scheduled increases are in PRICE_CHANGES.
    "gemini-4-argon": {"prompt": 2.00, "completion": 10.00},
    "gemini-3.8-flash": {"prompt": 0.75, "completion": 3.75},
    "gemini-3.6-flash": {"prompt": 1.50, "completion": 7.50},
    "gemini-3.5-flash-lite": {"prompt": 0.30, "completion": 2.50},
    "gemini-3.1-pro-preview": {"prompt": 2.00, "completion": 12.00},
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
}


# Decision-model prices (Model Comparison), keyed by provider type and then
# model. Kept apart from MODEL_PRICING because OpenAI's Decisions API reuses
# an LLM model id (gpt-6-luna) at a different price. Both bill input tokens
# only; output is free.
DECISION_MODEL_PRICING: Dict[str, Dict[str, Dict[str, float]]] = {
    # TypeSafe Jev — vendor-published early-access pricing, Sept 2026.
    "typesafe": {"jev": {"prompt": 0.042, "completion": 0.0}},
    # OpenAI Decisions API (GA Oct 22, 2026) — gpt-6-luna only.
    "openai": {"gpt-6-luna": {"prompt": 0.10, "completion": 0.0}},
}


# Announced list-price changes: model key -> [(effective date, new
# pricing)], oldest first. `lookup_pricing` applies every change whose
# date has passed, so costs stay right without another code change.
PRICE_CHANGES: Dict[str, list] = {
    "gpt-5.6-sol": [(date(2026, 11, 21), {"prompt": 5.00, "completion": 30.00})],
    "gemini-4-argon": [(date(2026, 12, 1), {"prompt": 4.00, "completion": 20.00})],
    "gemini-3.8-flash": [(date(2027, 1, 1), {"prompt": 1.50, "completion": 7.50})],
}


# Flex service-tier discount multiplier applied to prompt and
# completion prices. Both OpenAI and Google publish flex as roughly
# 50% of standard on-demand pricing for the models that support it
# (OpenAI: o3*, gpt-5*, gpt-6*; Google: gemini-2.5-* and gemini-3.x).
FLEX_DISCOUNT = 0.5


def _pricing_key(model_name: str) -> Optional[str]:
    """Resolve a model name to its MODEL_PRICING key.

    Exact match first; then the *longest* key contained in the name, so
    ``gpt-4o-mini-2024-07-18`` resolves to ``gpt-4o-mini`` rather than
    ``gpt-4o``; then a key that contains the name, only when exactly one
    does (``gpt-6`` alone is ambiguous and stays unpriced).
    """
    if model_name in MODEL_PRICING:
        return model_name
    lowered = model_name.lower()
    contained = [key for key in MODEL_PRICING if key in lowered]
    if contained:
        return max(contained, key=len)
    containing = [key for key in MODEL_PRICING if lowered in key]
    if len(containing) == 1:
        return containing[0]
    return None


def lookup_pricing(model_name: str, on: Optional[date] = None) -> Optional[Dict[str, float]]:
    """Return ``{"prompt": usd_per_1m, "completion": usd_per_1m}`` for a
    model on date ``on`` (default: today), or None when the price is
    unknown. Matches by name as described in :func:`_pricing_key`."""
    if not model_name:
        return None
    key = _pricing_key(model_name)
    if key is None:
        return None
    pricing = MODEL_PRICING[key]
    today = on or date.today()
    for effective, changed in PRICE_CHANGES.get(key, []):
        if today >= effective:
            pricing = changed
    return pricing


def lookup_decision_pricing(provider_type: str, model_name: str) -> Optional[Dict[str, float]]:
    """Price of a decision model, matched like :func:`_pricing_key` but only
    within the provider's own table (``jev-latest`` → ``jev``), or None."""
    table = DECISION_MODEL_PRICING.get(provider_type) or {}
    if not model_name:
        return None
    if model_name in table:
        return table[model_name]
    lowered = model_name.lower()
    contained = [key for key in table if key in lowered]
    return table[max(contained, key=len)] if contained else None


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
