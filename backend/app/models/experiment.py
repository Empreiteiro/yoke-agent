from sqlalchemy import Column, Integer, String, DateTime, Text, Float, JSON, ForeignKey, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, proposing, configured, running, completed, failed
    vectorstore_type = Column(String(50), default="chromadb")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    combinations = relationship("ExperimentCombination", back_populates="experiment", cascade="all, delete-orphan")


class ExperimentCombination(Base):
    __tablename__ = "experiment_combinations"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    params = Column(JSON, nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed
    # RAGAS metrics - fixed
    faithfulness = Column(Float)
    answer_relevancy = Column(Float)
    context_precision = Column(Float)
    context_recall = Column(Float)
    # Optional metrics
    answer_similarity = Column(Float)
    answer_correctness = Column(Float)
    # Aggregate
    overall_score = Column(Float)
    detailed_results = Column(JSON)
    error_message = Column(Text)
    duration_seconds = Column(Float)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)
    experiment = relationship("Experiment", back_populates="combinations")
