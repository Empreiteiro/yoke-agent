from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, func
from sqlalchemy.types import JSON
from app.core.database import Base


class Provider(Base):
    __tablename__ = "providers"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    provider_type = Column(String(50), nullable=False)  # openai, anthropic, google, cohere, huggingface, ollama, azure_openai, custom, typesafe, systemone, classifier
    api_key = Column(Text, nullable=True)  # encrypted in production
    base_url = Column(String(500), nullable=True)  # for custom/ollama endpoints
    is_active = Column(Boolean, default=True)

    # Supported capabilities
    supports_llm = Column(Boolean, default=False)
    supports_embedding = Column(Boolean, default=False)
    # Decision models (TypeSafe Jev and other System One-style APIs) return a
    # typed choice from a fixed option set instead of generated text. Text
    # classifier providers reuse the same flag and model list.
    supports_decision = Column(Boolean, default=False)

    # Available models (stored as JSON arrays)
    llm_models = Column(JSON, default=list)  # ["gpt-4o", "gpt-4o-mini", ...]
    embedding_models = Column(JSON, default=list)  # ["text-embedding-3-small", ...]
    decision_models = Column(JSON, default=list)  # ["jev-latest", ...]

    # Default models for this provider
    default_llm_model = Column(String(100), nullable=True)
    default_embedding_model = Column(String(100), nullable=True)
    default_decision_model = Column(String(100), nullable=True)

    # Extra config (e.g., api_version for Azure, org_id for OpenAI)
    extra_config = Column(JSON, default=dict)

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
