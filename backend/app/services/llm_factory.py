"""
Factory for creating LLM and Embedding instances from provider configurations.
Supports: OpenAI, Anthropic, Google, OpenRouter, NVIDIA NIM, Cohere, Ollama,
Azure OpenAI, HuggingFace, Custom.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.provider import Provider

OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
NVIDIA_NIM_BASE_URL = "https://integrate.api.nvidia.com/v1"


def provider_error_hint(provider_type: str, message: str) -> Optional[str]:
    """What to do about an upstream error whose text doesn't say, or None.

    build.nvidia.com answers ``404 Function '<id>': Not found for account
    '<id>'`` when it knows the model but hasn't enabled its hosted endpoint
    for the key's account — an NVIDIA-side entitlement (often per model),
    not a wrong model id or key.
    """
    if provider_type == "nvidia" and "not found for account" in (message or "").lower():
        return (
            "build.nvidia.com hasn't enabled this model's hosted endpoint for your account "
            "(an NVIDIA entitlement, not a wrong model id or key). Try another model; if none "
            "works, ask NVIDIA to enable \"Public API Endpoints\" for your account."
        )
    return None


# Models that accept the "flex" service tier. Used to pre-flight test
# calls so we don't issue a flex request against a model the upstream
# API will reject (non-flex models return either "service_tier 'flex'
# is not supported for this model" or the more generic "Invalid
# service_tier argument" rather than silently downgrading).
#
# OpenAI flex: o3, o4-mini, and the gpt-5 / gpt-6 families (Batch and
# Flex are both billed at 50% of standard). gpt-4.1 was once listed in
# early previews but the GA flex SKU does NOT cover it — using flex
# against gpt-4.1 returns "Invalid service_tier argument".
# Source: https://developers.openai.com/api/docs/pricing
#
# Google flex: gemini-2.5-* family and the gemini-3.x lineage.
# Source: https://ai.google.dev/gemini-api/docs/flex-processing
_OPENAI_FLEX_PREFIXES = ("o3", "o4-mini", "gpt-5", "gpt-6")
_GOOGLE_FLEX_PREFIXES = ("gemini-2.5", "gemini-3")

# OpenAI reasoning models reject any custom ``temperature`` (and
# ``top_p``, ``presence_penalty``, …) — only the default value of 1
# is accepted. The API returns:
#   "Unsupported value: 'temperature' does not support 0.0 with this
#    model. Only the default (1) value is supported."
# The o-series and the GPT-5 / GPT-6 families are all reasoning models
# (they take ``reasoning.effort`` instead). Detected by model-name
# prefix so we can simply omit the kwarg from the ChatOpenAI
# constructor and let the SDK use the default.
_OPENAI_REASONING_PREFIXES = ("o1", "o3", "o4-mini", "o4", "gpt-5", "gpt-6")

# Claude models that still accept a custom ``temperature``. Claude Opus
# 4.7+, Sonnet 5+, Haiku 5.5 and the Fable line removed sampling
# parameters (any non-default value returns a 400), so anything not
# listed here — including future models — gets the API default.
_ANTHROPIC_SAMPLING_PREFIXES = (
    "claude-3",
    "claude-opus-4-0", "claude-opus-4-1", "claude-opus-4-5", "claude-opus-4-6",
    "claude-opus-4-2025",
    "claude-sonnet-4-0", "claude-sonnet-4-5", "claude-sonnet-4-6",
    "claude-sonnet-4-2025",
    "claude-haiku-4-5",
)


def is_openai_reasoning_model(model_name: str) -> bool:
    """Return True for OpenAI reasoning models (o-series, GPT-5, GPT-6)
    that don't accept a custom ``temperature``."""
    if not model_name:
        return False
    name = model_name.lower()
    return any(name.startswith(p) for p in _OPENAI_REASONING_PREFIXES)


def anthropic_accepts_temperature(model_name: str) -> bool:
    """Return True for Claude models that still accept a custom
    ``temperature`` (Opus 4.6 / Sonnet 4.6 / Haiku 4.5 and older)."""
    if not model_name:
        return False
    name = model_name.lower()
    return any(name.startswith(p) for p in _ANTHROPIC_SAMPLING_PREFIXES)


def flex_supported_for(provider_type: str, model_name: str) -> bool:
    """Return True if ``model_name`` supports the flex service tier for
    the given provider. Conservative: unknown providers/models → False."""
    if not model_name:
        return False
    name = model_name.lower()
    if provider_type == "openai":
        return any(name.startswith(p) for p in _OPENAI_FLEX_PREFIXES)
    if provider_type == "google":
        return any(name.startswith(p) for p in _GOOGLE_FLEX_PREFIXES)
    return False


def uses_flex(provider: Provider, model_name: str, flex: Optional[bool] = None) -> bool:
    """Whether a call to ``model_name`` goes out on the flex tier.

    ``flex`` overrides the provider's ``extra_config.flex_tier`` setting
    (None = follow it); models without flex always run on the standard tier.
    """
    wanted = (provider.extra_config or {}).get("flex_tier") if flex is None else flex
    return bool(wanted) and flex_supported_for(provider.provider_type, model_name)


def pick_flex_model(provider: Provider) -> Optional[str]:
    """Pick the first flex-compatible model from a provider's model list,
    preferring the configured default. For OpenAI, non-reasoning models
    are preferred over reasoning ones because the latter ignore a custom
    ``temperature`` (``get_llm`` omits it for them). Returns None if none
    are compatible."""
    candidates: list[str] = []
    if provider.default_llm_model:
        candidates.append(provider.default_llm_model)
    for m in (provider.llm_models or []):
        if m not in candidates:
            candidates.append(m)

    eligible = [
        m for m in candidates
        if flex_supported_for(provider.provider_type, m)
    ]
    if not eligible:
        return None

    # Stable-sort: non-reasoning OpenAI models first, then reasoning.
    # Order within each bucket is preserved (default model still wins
    # the tie if it's flex-eligible and non-reasoning).
    if provider.provider_type == "openai":
        eligible.sort(key=lambda m: 1 if is_openai_reasoning_model(m) else 0)
    return eligible[0]


def get_llm(
    db: Session,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    temperature: Optional[float] = 0.0,
    format: Optional[str] = None,
    isolated: bool = False,
    flex: Optional[bool] = None,
):
    """Create a LangChain LLM instance from a provider configuration.

    ``temperature=None`` means "use the SDK default" — the kwarg is
    omitted from the constructor entirely. Useful for models that
    reject any custom temperature (OpenAI o-series reasoning models).
    ``flex`` turns the flex service tier on or off for this instance,
    overriding the provider's setting (None = use the provider's).
    """
    provider = _resolve_provider(db, provider_id, capability="llm", model=model)
    model_name = model or provider.default_llm_model or (provider.llm_models[0] if provider.llm_models else None)

    if not model_name:
        raise ValueError(f"No LLM model specified for provider '{provider.name}'")

    ptype = provider.provider_type

    if ptype == "openai":
        from langchain_openai import ChatOpenAI
        kwargs: dict = {
            "model": model_name,
            "api_key": provider.api_key,
        }
        # Reasoning models (o-series, gpt-5*, gpt-6*) only accept the
        # default temperature of 1; passing anything else returns 400. Just omit
        # the kwarg so the SDK uses the default. Same when the caller
        # explicitly passes temperature=None ("use SDK default").
        if temperature is not None and not is_openai_reasoning_model(model_name):
            kwargs["temperature"] = temperature
        # Opt-in OpenAI "flex" service tier (~50% cheaper, best-effort
        # latency). Stored on the provider via extra_config.flex_tier=True.
        # Only o3*, o4-mini* and the gpt-5 / gpt-6 lineage accept it —
        # issuing flex against any other model
        # returns a 400 from the API, so we silently skip the flag for
        # unsupported models instead of breaking the call.
        # ``langchain-openai >= 1.0`` exposes ``service_tier`` as an
        # explicit Pydantic field; using it directly avoids the
        # UserWarning from passing it through ``model_kwargs``.
        if uses_flex(provider, model_name, flex):
            kwargs["service_tier"] = "flex"
        return ChatOpenAI(**kwargs)

    elif ptype == "anthropic":
        from langchain_anthropic import ChatAnthropic
        kwargs = {"model": model_name, "api_key": provider.api_key}
        # Newer Claude models reject sampling parameters — omit the kwarg
        # so the API default applies (see _ANTHROPIC_SAMPLING_PREFIXES).
        if temperature is not None and anthropic_accepts_temperature(model_name):
            kwargs["temperature"] = temperature
        return ChatAnthropic(**kwargs)

    elif ptype == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        gkwargs: dict = {"model": model_name, "google_api_key": provider.api_key}
        if temperature is not None:
            gkwargs["temperature"] = temperature
        llm = ChatGoogleGenerativeAI(**gkwargs)
        # Opt-in Gemini "flex" service tier (~50% cheaper, best-effort
        # latency). Supported on gemini-2.5-* and the gemini-3.x preview
        # lineage. `ChatGoogleGenerativeAI.model_kwargs` is a Pydantic
        # catch-all that never reaches the underlying SDK, so we use
        # Runnable.bind() — those kwargs flow straight into
        # `_build_request_config` → `GenerateContentConfig(service_tier=...)`.
        # Requires google-genai >= 1.69.0. Skip for non-flex models so
        # the API doesn't reject the request outright.
        if uses_flex(provider, model_name, flex):
            llm = llm.bind(service_tier="flex")
        return llm

    elif ptype == "cohere":
        from langchain_cohere import ChatCohere
        ckwargs = {"model": model_name, "cohere_api_key": provider.api_key}
        if temperature is not None:
            ckwargs["temperature"] = temperature
        return ChatCohere(**ckwargs)

    elif ptype == "ollama":
        from langchain_ollama import ChatOllama
        base_url = provider.base_url or "http://localhost:11434"
        kwargs = dict(model=model_name, base_url=base_url)
        if temperature is not None:
            kwargs["temperature"] = temperature
        if format:
            kwargs["format"] = format
        return ChatOllama(**kwargs)

    elif ptype == "azure_openai":
        from langchain_openai import AzureChatOpenAI
        extra = provider.extra_config or {}
        akwargs: dict = {
            "azure_deployment": model_name,
            "api_key": provider.api_key,
            "azure_endpoint": provider.base_url,
            "api_version": extra.get("api_version", "2024-02-01"),
        }
        # Azure also exposes the o-series reasoning deployments — same
        # temperature restriction as the OpenAI API.
        if temperature is not None and not is_openai_reasoning_model(model_name):
            akwargs["temperature"] = temperature
        return AzureChatOpenAI(**akwargs)

    elif ptype == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        hkwargs: dict = {"repo_id": model_name, "huggingfacehub_api_token": provider.api_key}
        if temperature is not None:
            hkwargs["temperature"] = temperature
        llm = HuggingFaceEndpoint(**hkwargs)
        return ChatHuggingFace(llm=llm)

    elif ptype == "claude_code":
        from app.services.claude_code_llm import ChatClaudeCode
        return ChatClaudeCode(
            model_name=model_name,
            temperature=temperature,
            isolated=isolated,
        )

    elif ptype == "custom":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=provider.api_key or "not-needed",
            base_url=provider.base_url,
            temperature=temperature,
        )

    elif ptype == "openrouter":
        from langchain_openai import ChatOpenAI
        # OpenRouter drops sampling parameters a model doesn't support, so
        # temperature is safe to pass to reasoning models here. X-Title
        # attributes the traffic to Yoke in the OpenRouter dashboard.
        kwargs = {
            "model": model_name,
            "api_key": provider.api_key,
            "base_url": OPENROUTER_BASE_URL,
            "default_headers": {"X-Title": "Yoke Agent"},
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatOpenAI(**kwargs)

    elif ptype == "nvidia":
        from langchain_openai import ChatOpenAI
        kwargs = {
            "model": model_name,
            "api_key": provider.api_key or "not-needed",
            "base_url": provider.base_url or NVIDIA_NIM_BASE_URL,
        }
        if temperature is not None:
            kwargs["temperature"] = temperature
        return ChatOpenAI(**kwargs)

    else:
        raise ValueError(f"Unsupported provider type: {ptype}")


def get_embeddings(
    db: Session,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    dimensions: Optional[int] = None,
):
    """Create a LangChain Embeddings instance from a provider configuration."""
    provider = _resolve_provider(db, provider_id, capability="embedding", model=model)
    model_name = model or provider.default_embedding_model or (provider.embedding_models[0] if provider.embedding_models else None)

    if not model_name:
        raise ValueError(f"No embedding model specified for provider '{provider.name}'")

    ptype = provider.provider_type

    if ptype == "openai":
        from langchain_openai import OpenAIEmbeddings
        kwargs = {"model": model_name, "api_key": provider.api_key}
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        return OpenAIEmbeddings(**kwargs)

    elif ptype == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        # Back-compat: Google removed both legacy text embedding models from
        # the v1beta endpoint (embedding-001 first, then text-embedding-004
        # in early 2026). Any provider still saved with one of those names
        # 404s with "models/<name> is not found for API version v1beta".
        # Transparently remap them to the current GA model so existing
        # saved providers keep working without requiring the user to open
        # Settings and reconfigure.
        _GOOGLE_DEPRECATED_EMBEDDINGS = {"embedding-001", "text-embedding-004"}
        if model_name in _GOOGLE_DEPRECATED_EMBEDDINGS:
            import logging
            logging.getLogger(__name__).warning(
                "Google provider '%s' is configured with deprecated "
                "embedding model '%s'; remapping to gemini-embedding-001.",
                provider.name,
                model_name,
            )
            model_name = "gemini-embedding-001"
        # LangChain auto-prefixes "models/" when missing. Both
        # gemini-embedding-001 and gemini-embedding-2-preview use
        # Matryoshka Representation Learning, so `output_dimensionality`
        # is honoured for either model when the user picked a custom dim.
        kwargs: dict = {
            "model": model_name,
            "google_api_key": provider.api_key,
        }
        if dimensions is not None and model_name.startswith("gemini-embedding"):
            kwargs["output_dimensionality"] = dimensions
        return GoogleGenerativeAIEmbeddings(**kwargs)

    elif ptype == "cohere":
        from langchain_cohere import CohereEmbeddings
        return CohereEmbeddings(
            model=model_name,
            cohere_api_key=provider.api_key,
        )

    elif ptype == "ollama":
        from langchain_ollama import OllamaEmbeddings
        base_url = provider.base_url or "http://localhost:11434"
        return OllamaEmbeddings(model=model_name, base_url=base_url)

    elif ptype == "azure_openai":
        from langchain_openai import AzureOpenAIEmbeddings
        extra = provider.extra_config or {}
        kwargs = {
            "azure_deployment": model_name,
            "api_key": provider.api_key,
            "azure_endpoint": provider.base_url,
            "api_version": extra.get("api_version", "2024-02-01"),
        }
        if dimensions is not None:
            kwargs["dimensions"] = dimensions
        return AzureOpenAIEmbeddings(**kwargs)

    elif ptype == "huggingface":
        from langchain_huggingface import HuggingFaceEmbeddings
        return HuggingFaceEmbeddings(model_name=model_name)

    elif ptype == "custom":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(
            model=model_name,
            api_key=provider.api_key or "not-needed",
            base_url=provider.base_url,
        )

    else:
        raise ValueError(f"Unsupported embedding provider type: {ptype}")


# Public alias for consumers that need the resolved provider (e.g. token
# usage logging needs the provider name + model to write to TokenUsageLog).
def resolve_provider(
    db: Session,
    provider_id: Optional[int] = None,
    capability: str = "llm",
    model: Optional[str] = None,
) -> Provider:
    """Public wrapper around :func:`_resolve_provider`."""
    return _resolve_provider(db, provider_id, capability=capability, model=model)


def _resolve_provider(
    db: Session,
    provider_id: Optional[int],
    capability: str = "llm",
    model: Optional[str] = None,
) -> Provider:
    """Find the right provider: by ID, by model match, or fall back to the first active one."""
    if provider_id:
        provider = db.query(Provider).filter(
            Provider.id == provider_id,
            Provider.is_active == True,
        ).first()
        if not provider:
            raise ValueError(f"Provider {provider_id} not found or inactive")
        return provider

    # Auto-select: first active provider with the needed capability
    query = db.query(Provider).filter(Provider.is_active == True)
    if capability == "llm":
        query = query.filter(Provider.supports_llm == True)
    elif capability == "embedding":
        query = query.filter(Provider.supports_embedding == True)

    providers = query.all()
    if not providers:
        raise ValueError(
            f"No active {capability} provider configured. "
            "Please add a provider in Settings → Providers."
        )

    # If a model name is given, prefer the provider whose model list contains it
    if model:
        for p in providers:
            model_list = p.llm_models if capability == "llm" else p.embedding_models
            if model_list and model in model_list:
                return p

    return providers[0]
