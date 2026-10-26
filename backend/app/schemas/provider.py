from pydantic import BaseModel, field_validator
from typing import Optional
from datetime import datetime


# --- Provider type definitions with known models ---
PROVIDER_CATALOG = {
    "openai": {
        "label": "OpenAI",
        "supports_llm": True,
        "supports_embedding": True,
        # Current API models as of Oct 2026. GPT-4o / GPT-4.1 (and their
        # minis) are deprecated with a Jan 14, 2027 shutdown; o4-mini,
        # o3-mini and gpt-4.1-nano shut down Oct 23, 2026. Older ids can
        # still be added by hand in Settings → Providers. In every list the
        # first entry is preselected as the provider's default model.
        "llm_models": [
            "gpt-6.1-sol", "gpt-6-astra", "gpt-6-luna",
            "gpt-5.6-sol", "gpt-5.6-terra",
            "gpt-5.5", "gpt-5.4", "gpt-5.4-mini",
        ],
        "embedding_models": [
            "text-embedding-3-small", "text-embedding-3-large",
            "text-embedding-ada-002",
        ],
        # Decisions API (POST /v1/decisions, GA Oct 22, 2026) — runs on
        # gpt-6-luna only. Same id as the LLM, but answers a typed choice
        # question instead of generating text.
        "supports_decision": True,
        "decision_models": ["gpt-6-luna"],
        "requires_api_key": True,
        "supports_base_url": False,
    },
    "anthropic": {
        "label": "Anthropic",
        "supports_llm": True,
        "supports_embedding": False,
        # Current Claude models as of Oct 2026 (aliases — no date suffix).
        # Claude Opus 4 / Sonnet 4 are deprecated and the Claude 3.x models
        # are retired.
        "llm_models": [
            "claude-opus-5-5", "claude-sonnet-5-5", "claude-haiku-5-5",
            "claude-fable-5-1",
            "claude-opus-5", "claude-sonnet-5",
            "claude-opus-4-8", "claude-opus-4-7", "claude-opus-4-6",
            "claude-sonnet-4-6", "claude-haiku-4-5",
        ],
        "embedding_models": [],
        "requires_api_key": True,
        "supports_base_url": False,
    },
    "google": {
        "label": "Google AI (Gemini)",
        "supports_llm": True,
        "supports_embedding": True,
        # Current Gemini API models as of Oct 2026. Gemini 2.0 shut down
        # June 1, 2026, 1.5 is retired, and 2.5 is limited to existing
        # users; gemini-3.5-flash is deprecated (routed to 3.6 Flash).
        "llm_models": [
            "gemini-3.8-flash", "gemini-4-argon",
            "gemini-3.6-flash", "gemini-3.5-flash-lite",
            "gemini-3.1-pro-preview",
        ],
        "embedding_models": [
            "gemini-embedding-001", "gemini-embedding-2-preview",
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
    # ── Decision models ──────────────────────────────────────────────
    # Decision models answer a typed question about a piece of state with
    # a calibrated choice (plus per-option probabilities) instead of
    # generated text. Used by the Model Comparison workbench. OpenAI
    # (above) serves them next to its LLMs; these providers serve only
    # decision models.
    "typesafe": {
        "label": "TypeSafe (Jev)",
        "supports_llm": False,
        "supports_embedding": False,
        "supports_decision": True,
        "llm_models": [],
        "embedding_models": [],
        "decision_models": ["jev-latest"],
        "requires_api_key": True,
        "supports_base_url": True,
        "default_base_url": "https://api.typesafe.ai",
    },
    "systemone": {
        "label": "System One-compatible",
        "supports_llm": False,
        "supports_embedding": False,
        "supports_decision": True,
        "llm_models": [],
        "embedding_models": [],
        "decision_models": [],
        "requires_api_key": False,
        "supports_base_url": True,
    },
    # Pre-trained text classifiers (the "traditional guardrails" decision
    # models are benchmarked against). Their models are listed under
    # decision_models; Model Comparison runs them as kind "classifier".
    # extra_config: {"api_format": "hf" | "detector", "path", "parameters",
    # "detector_params", "headers"} — see services/text_classifiers.py.
    "classifier": {
        "label": "Text classifier (HF / TEI / detector)",
        "supports_llm": False,
        "supports_embedding": False,
        "supports_decision": True,
        "llm_models": [],
        "embedding_models": [],
        "decision_models": [
            "protectai/deberta-v3-base-prompt-injection-v2",
            "ibm-granite/granite-guardian-hap-125m",
        ],
        "requires_api_key": False,
        "supports_base_url": True,
    },
}

# Catalog entries default to no decision support.
for _entry in PROVIDER_CATALOG.values():
    _entry.setdefault("supports_decision", False)
    _entry.setdefault("decision_models", [])


# --- Embedding model dimension capabilities ---
EMBEDDING_DIMENSIONS = {
    # OpenAI - text-embedding-3 supports custom dimensions
    "text-embedding-3-small": {"default": 1536, "supports_custom": True, "supported": [512, 1024, 1536]},
    "text-embedding-3-large": {"default": 3072, "supports_custom": True, "supported": [256, 1024, 3072]},
    "text-embedding-ada-002": {"default": 1536, "supports_custom": False, "supported": [1536]},
    # Google — both current GA/preview models use Matryoshka Representation
    # Learning, so the vector can be truncated at call time without
    # re-embedding. Google recommends 768, 1536, or 3072 dims.
    "gemini-embedding-001":      {"default": 3072, "supports_custom": True, "supported": [768, 1536, 3072]},
    "gemini-embedding-2-preview":{"default": 3072, "supports_custom": True, "supported": [768, 1536, 3072]},
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
    supports_decision: bool = False
    llm_models: list[str] = []
    embedding_models: list[str] = []
    decision_models: list[str] = []
    default_llm_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    default_decision_model: Optional[str] = None
    extra_config: dict = {}


class ProviderUpdate(BaseModel):
    name: Optional[str] = None
    api_key: Optional[str] = None
    base_url: Optional[str] = None
    is_active: Optional[bool] = None
    supports_llm: Optional[bool] = None
    supports_embedding: Optional[bool] = None
    supports_decision: Optional[bool] = None
    llm_models: Optional[list[str]] = None
    embedding_models: Optional[list[str]] = None
    decision_models: Optional[list[str]] = None
    default_llm_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    default_decision_model: Optional[str] = None
    extra_config: Optional[dict] = None


class ProviderResponse(BaseModel):
    id: int
    name: str
    provider_type: str
    base_url: Optional[str] = None
    is_active: bool
    supports_llm: bool
    supports_embedding: bool
    supports_decision: bool = False
    llm_models: list[str] = []
    embedding_models: list[str] = []
    decision_models: list[str] = []
    default_llm_model: Optional[str] = None
    default_embedding_model: Optional[str] = None
    default_decision_model: Optional[str] = None
    extra_config: dict = {}
    has_api_key: bool = False  # never expose actual key
    created_at: datetime
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True

    # Rows created before decision-model support have NULL in these columns.
    @field_validator("llm_models", "embedding_models", "decision_models", mode="before")
    @classmethod
    def _none_to_empty_list(cls, value):
        return [] if value is None else value

    @field_validator("supports_decision", mode="before")
    @classmethod
    def _none_to_false(cls, value):
        return bool(value)


class ProviderTestResult(BaseModel):
    success: bool
    message: str
    llm_ok: Optional[bool] = None
    embedding_ok: Optional[bool] = None
    decision_ok: Optional[bool] = None


class AvailableModelsResponse(BaseModel):
    llm_models: list[dict]  # [{"provider_id": 1, "provider_name": "OpenAI", "model": "gpt-4o"}, ...]
    embedding_models: list[dict]
    decision_models: list[dict] = []
