from pydantic import BaseModel
from typing import Optional
from datetime import datetime


# --- Provider type definitions with known models ---
PROVIDER_CATALOG = {
    "openai": {
        "label": "OpenAI",
        "supports_llm": True,
        "supports_embedding": True,
        "llm_models": [
            "gpt-5.4", "gpt-5.4-mini",
            "gpt-4.1", "gpt-4.1-mini", "gpt-4.1-nano",
            "gpt-4o", "gpt-4o-mini",
            "o3", "o3-mini", "o4-mini",
            "gpt-4-turbo", "gpt-4", "gpt-3.5-turbo",
        ],
        "embedding_models": [
            "text-embedding-3-small", "text-embedding-3-large",
            "text-embedding-ada-002",
        ],
        "requires_api_key": True,
        "supports_base_url": False,
    },
    "anthropic": {
        "label": "Anthropic",
        "supports_llm": True,
        "supports_embedding": False,
        "llm_models": [
            "claude-opus-4-20250514", "claude-sonnet-4-20250514",
            "claude-3-5-haiku-20241022", "claude-3-opus-20240229",
        ],
        "embedding_models": [],
        "requires_api_key": True,
        "supports_base_url": False,
    },
    "google": {
        "label": "Google AI (Gemini)",
        "supports_llm": True,
        "supports_embedding": True,
        "llm_models": [
            "gemini-2.5-pro", "gemini-2.5-flash",
            "gemini-2.0-flash", "gemini-2.0-flash-lite",
            "gemini-1.5-pro", "gemini-1.5-flash",
        ],
        "embedding_models": [
            "gemini-embedding-001", "text-embedding-004",
        ],
        "requires_api_key": True,
        "supports_base_url": False,
    },
    "cohere": {
        "label": "Cohere",
        "supports_llm": True,
        "supports_embedding": True,
        "llm_models": ["command-r-plus", "command-r", "command"],
        "embedding_models": [
            "embed-english-v3.0", "embed-multilingual-v3.0",
            "embed-english-light-v3.0", "embed-multilingual-light-v3.0",
        ],
        "requires_api_key": True,
        "supports_base_url": False,
    },
    "ollama": {
        "label": "Ollama (Local)",
        "supports_llm": True,
        "supports_embedding": True,
        "llm_models": [
            "llama3.1", "llama3.1:70b", "mistral", "mixtral",
            "phi3", "qwen2", "gemma2", "codellama",
        ],
        "embedding_models": [
            "nomic-embed-text", "mxbai-embed-large",
            "all-minilm", "snowflake-arctic-embed",
        ],
        "requires_api_key": False,
        "supports_base_url": True,
        "default_base_url": "http://localhost:11434",
    },
    "azure_openai": {
        "label": "Azure OpenAI",
        "supports_llm": True,
        "supports_embedding": True,
        "llm_models": ["gpt-4o", "gpt-4o-mini", "gpt-4", "gpt-35-turbo"],
        "embedding_models": [
            "text-embedding-3-small", "text-embedding-3-large",
            "text-embedding-ada-002",
        ],
        "requires_api_key": True,
        "supports_base_url": True,
    },
    "huggingface": {
        "label": "HuggingFace",
        "supports_llm": True,
        "supports_embedding": True,
        "llm_models": [
            "meta-llama/Llama-3.1-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
            "microsoft/Phi-3-mini-4k-instruct",
        ],
        "embedding_models": [
            "sentence-transformers/all-MiniLM-L6-v2",
            "BAAI/bge-small-en-v1.5",
            "BAAI/bge-large-en-v1.5",
            "intfloat/e5-large-v2",
        ],
        "requires_api_key": True,
        "supports_base_url": False,
    },
    "claude_code": {
        "label": "Claude Code (CLI)",
        "supports_llm": True,
        "supports_embedding": False,
        "llm_models": ["claude-code"],
        "embedding_models": [],
        "requires_api_key": False,
        "supports_base_url": False,
    },
    "custom": {
        "label": "Custom (OpenAI-compatible)",
        "supports_llm": True,
        "supports_embedding": True,
        "llm_models": [],
        "embedding_models": [],
        "requires_api_key": False,
        "supports_base_url": True,
    },
}


# --- Embedding model dimension capabilities ---
EMBEDDING_DIMENSIONS = {
    # OpenAI - text-embedding-3 supports custom dimensions
    "text-embedding-3-small": {"default": 1536, "supports_custom": True, "supported": [512, 1024, 1536]},
    "text-embedding-3-large": {"default": 3072, "supports_custom": True, "supported": [256, 1024, 3072]},
    "text-embedding-ada-002": {"default": 1536, "supports_custom": False, "supported": [1536]},
    # Google
    # gemini-embedding-001 uses Matryoshka Representation Learning so the
    # vector can be truncated to 768/1536/3072 without re-embedding.
    "gemini-embedding-001": {"default": 3072, "supports_custom": True, "supported": [768, 1536, 3072]},
    "text-embedding-004": {"default": 768, "supports_custom": False, "supported": [768]},
    # Cohere
    "embed-english-v3.0": {"default": 1024, "supports_custom": False, "supported": [1024]},
    "embed-multilingual-v3.0": {"default": 1024, "supports_custom": False, "supported": [1024]},
    "embed-english-light-v3.0": {"default": 384, "supports_custom": False, "supported": [384]},
    "embed-multilingual-light-v3.0": {"default": 384, "supports_custom": False, "supported": [384]},
    # Ollama
    "nomic-embed-text": {"default": 768, "supports_custom": False, "supported": [768]},
    "mxbai-embed-large": {"default": 1024, "supports_custom": False, "supported": [1024]},
    "all-minilm": {"default": 384, "supports_custom": False, "supported": [384]},
    "snowflake-arctic-embed": {"default": 1024, "supports_custom": False, "supported": [1024]},
    # HuggingFace
    "sentence-transformers/all-MiniLM-L6-v2": {"default": 384, "supports_custom": False, "supported": [384]},
    "BAAI/bge-small-en-v1.5": {"default": 384, "supports_custom": False, "supported": [384]},
    "BAAI/bge-large-en-v1.5": {"default": 1024, "supports_custom": False, "supported": [1024]},
    "intfloat/e5-large-v2": {"default": 1024, "supports_custom": False, "supported": [1024]},
}


class ProviderCreate(BaseModel):
    name: str
    provider_type: str
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: bool = True
    supports_llm: bool = True
    supports_embedding: bool = False
    llm_models: list[str] = []
    embedding_models: list[str] = []
    default_llm_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    extra_config: dict = {}


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None
    supports_llm: Optional[bool] = None
    supports_embedding: Optional[bool] = None
    llm_models: Optional[list[str]] = None
    embedding_models: Optional[list[str]] = None
    default_llm_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    extra_config: Optional[dict] = None


class ProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    base_url: Optional[str] = None
    is_active: bool
    supports_llm: bool
    supports_embedding: bool
    llm_models: list[str] = []
    embedding_models: list[str] = []
    default_llm_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    extra_config: dict = {}
    has_api_key: bool = False  # never expose actual key
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ProviderTestResult(BaseModel):
    success: bool
    message: str
    llm_ok: Optional[bool] = None
    embedding_ok: Optional[bool] = None


class AvailableModelsResponse(BaseModel):
    llm_models: list[dict]  # [{"provider_id": 1, "provider_name": "OpenAI", "model": "gpt-4o"}, ...]
    embedding_models: list[dict]
