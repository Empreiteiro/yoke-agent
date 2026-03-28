"""Saved vectorstore collections from winning experiment combinations."""

from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text
from sqlalchemy.sql import func

from app.core.database import Base


class SavedCollection(Base):
    __tablename__ = "saved_collections"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    experiment_id = Column(Integer, ForeignKey("experiments.id", ondelete="SET NULL"), nullable=True)
    combination_id = Column(Integer, nullable=True)
    collection_name = Column(String(255), nullable=False, unique=True)
    persist_path = Column(Text, nullable=False)

    # RAG params (flat for easy querying)
    embedding_model = Column(String(255), nullable=False)
    embedding_dimensions = Column(Integer, nullable=True)
    distance_metric = Column(String(50), default="cosine")
    chunk_size = Column(Integer, nullable=False)
    chunk_overlap = Column(Integer, nullable=False)
    top_k = Column(Integer, nullable=False)
    search_type = Column(String(50), nullable=False)

    overall_score = Column(Float, nullable=True)
    size_bytes = Column(Integer, default=0)

    created_at = Column(DateTime(timezone=True), server_default=func.now())
