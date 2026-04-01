from sqlalchemy import Column, Integer, String, DateTime, Text, ForeignKey, JSON, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    status = Column(String(50), default="draft")  # draft, generating, generated, error, approved
    error_message = Column(Text, nullable=True)
    document_ids = Column(JSON)
    sampled_pages = Column(JSON, nullable=True)  # Pages sent to LLM in partial reading mode
    is_benchmark = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    items = relationship("DatasetItem", back_populates="dataset", cascade="all, delete-orphan")


class DatasetItem(Base):
    __tablename__ = "dataset_items"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    question = Column(Text, nullable=False)
    ground_truth = Column(Text, nullable=False)
    context = Column(Text)
    source_document = Column(String(255))
    is_manual = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    dataset = relationship("Dataset", back_populates="items")
