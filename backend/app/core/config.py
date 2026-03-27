from pydantic_settings import BaseSettings
from typing import List


class Settings(BaseSettings):
    app_name: str = "RAG Optimization Pipeline"
    database_url: str = "sqlite:///./rag_pipeline.db"
    upload_dir: str = "./uploads"
    cors_origins: List[str] = ["http://localhost:3000"]
    openai_api_key: str = ""
    default_llm_model: str = "gpt-4o-mini"
    default_embedding_model: str = "text-embedding-3-small"
    max_upload_size_mb: int = 50

    class Config:
        env_file = ".env"


settings = Settings()
