"""
Factory for creating LLM and Embedding instances from provider configurations.
Supports: OpenAI, Anthropic, Google, Cohere, Ollama, Azure OpenAI, HuggingFace, Custom.
"""
from typing import Optional
from sqlalchemy.orm import Session
from app.models.provider import Provider


def get_llm(
    db: Session,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
    temperature: float = 0.0,
):
    """Create a LangChain LLM instance from a provider configuration."""
    provider = _resolve_provider(db, provider_id, capability="llm")
    model_name = model or provider.default_llm_model or (provider.llm_models[0] if provider.llm_models else None)

    if not model_name:
        raise ValueError(f"No LLM model specified for provider '{provider.name}'")

    ptype = provider.provider_type

    if ptype == "openai":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=provider.api_key,
            temperature=temperature,
        )

    elif ptype == "anthropic":
        from langchain_anthropic import ChatAnthropic
        return ChatAnthropic(
            model=model_name,
            api_key=provider.api_key,
            temperature=temperature,
        )

    elif ptype == "google":
        from langchain_google_genai import ChatGoogleGenerativeAI
        return ChatGoogleGenerativeAI(
            model=model_name,
            google_api_key=provider.api_key,
            temperature=temperature,
        )

    elif ptype == "cohere":
        from langchain_cohere import ChatCohere
        return ChatCohere(
            model=model_name,
            cohere_api_key=provider.api_key,
            temperature=temperature,
        )

    elif ptype == "ollama":
        from langchain_ollama import ChatOllama
        base_url = provider.base_url or "http://localhost:11434"
        return ChatOllama(
            model=model_name,
            base_url=base_url,
            temperature=temperature,
        )

    elif ptype == "azure_openai":
        from langchain_openai import AzureChatOpenAI
        extra = provider.extra_config or {}
        return AzureChatOpenAI(
            azure_deployment=model_name,
            api_key=provider.api_key,
            azure_endpoint=provider.base_url,
            api_version=extra.get("api_version", "2024-02-01"),
            temperature=temperature,
        )

    elif ptype == "huggingface":
        from langchain_huggingface import ChatHuggingFace, HuggingFaceEndpoint
        llm = HuggingFaceEndpoint(
            repo_id=model_name,
            huggingfacehub_api_token=provider.api_key,
            temperature=temperature,
        )
        return ChatHuggingFace(llm=llm)

    elif ptype == "custom":
        from langchain_openai import ChatOpenAI
        return ChatOpenAI(
            model=model_name,
            api_key=provider.api_key or "not-needed",
            base_url=provider.base_url,
            temperature=temperature,
        )

    else:
        raise ValueError(f"Unsupported provider type: {ptype}")


def get_embeddings(
    db: Session,
    provider_id: Optional[int] = None,
    model: Optional[str] = None,
):
    """Create a LangChain Embeddings instance from a provider configuration."""
    provider = _resolve_provider(db, provider_id, capability="embedding")
    model_name = model or provider.default_embedding_model or (provider.embedding_models[0] if provider.embedding_models else None)

    if not model_name:
        raise ValueError(f"No embedding model specified for provider '{provider.name}'")

    ptype = provider.provider_type

    if ptype == "openai":
        from langchain_openai import OpenAIEmbeddings
        return OpenAIEmbeddings(model=model_name, api_key=provider.api_key)

    elif ptype == "google":
        from langchain_google_genai import GoogleGenerativeAIEmbeddings
        return GoogleGenerativeAIEmbeddings(
            model=model_name,
            google_api_key=provider.api_key,
        )

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
        return AzureOpenAIEmbeddings(
            azure_deployment=model_name,
            api_key=provider.api_key,
            azure_endpoint=provider.base_url,
            api_version=extra.get("api_version", "2024-02-01"),
        )

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


def _resolve_provider(
    db: Session,
    provider_id: Optional[int],
    capability: str = "llm",
) -> Provider:
    """Find the right provider: by ID, or fall back to the first active one."""
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

    provider = query.first()
    if not provider:
        raise ValueError(
            f"No active {capability} provider configured. "
            "Please add a provider in Settings → Providers."
        )
    return provider
