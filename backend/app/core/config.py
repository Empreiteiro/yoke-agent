from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    app_name: str = "Yoke Agent"
    database_url: str = "sqlite:///./rag_pipeline.db"
    upload_dir: str = "./uploads"
    cors_origins: List[str] = ["http://localhost:4000"]
    openai_api_key: str = ""
    default_llm_model: str = "gpt-4o-mini"
    default_embedding_model: str = "text-embedding-3-small"
    max_upload_size_mb: int = 50
    experiment_max_workers: int = 1
    # Tracing (issue #179)
    tracing_enabled: bool = False
    otlp_endpoint: str = ""  # e.g. http://localhost:4318/v1/traces
    otlp_service_name: str = "yoke-agent"

    class Config:
        env_file = ".env"


settings = Settings()
