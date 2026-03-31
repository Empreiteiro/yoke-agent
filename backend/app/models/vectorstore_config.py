from sqlalchemy import Column, Integer, String, DateTime, Text, Boolean, func
from sqlalchemy.types import JSON
from app.core.database import Base


class VectorStoreConfig(Base):
    __tablename__ = "vectorstore_configs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(100), nullable=False)
    vectorstore_type = Column(String(50), nullable=False)  # pinecone, qdrant, weaviate, pgvector
    is_active = Column(Boolean, default=True)
    api_key = Column(Text, nullable=True)
    config = Column(JSON, default=dict)  # type-specific: url, environment, index_name, connection_string, etc.

    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
