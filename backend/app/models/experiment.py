from sqlalchemy import Column, Integer, String, DateTime, Text, Float, JSON, ForeignKey, UniqueConstraint, func
from sqlalchemy.orm import relationship
from app.core.database import Base


class Experiment(Base):
    __tablename__ = "experiments"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(255), nullable=False)
    description = Column(Text)
    dataset_id = Column(Integer, ForeignKey("datasets.id"), nullable=False)
    status = Column(String(50), default="pending")  # pending, proposing, configured, running, completed, failed, stopped
    vectorstore_type = Column(String(50), default="chromadb")
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())
    combinations = relationship("ExperimentCombination", back_populates="experiment", cascade="all, delete-orphan")


class ExperimentCombination(Base):
    __tablename__ = "experiment_combinations"

    id = Column(Integer, primary_key=True, index=True)
    experiment_id = Column(Integer, ForeignKey("experiments.id"), nullable=False)
    params = Column(JSON, nullable=False)
    status = Column(String(50), default="pending")  # pending, running, completed, failed, stopped
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
    # Token usage aggregates
    total_tokens = Column(Integer, default=0)
    total_cost = Column(Float, default=0.0)
    # Latency aggregates (issue #112) — milliseconds per Q&A pair
    avg_latency_ms = Column(Float)
    p95_latency_ms = Column(Float)
    avg_retrieval_ms = Column(Float)
    avg_generation_ms = Column(Float)
    # Failure categorization summary (issue #117) — {category: count}
    failure_summary = Column(JSON)
    created_at = Column(DateTime, server_default=func.now())
    completed_at = Column(DateTime)
    experiment = relationship("Experiment", back_populates="combinations")
    human_ratings = relationship(
        "HumanRating",
        back_populates="combination",
        cascade="all, delete-orphan",
    )


class HumanRating(Base):
    """A human rating for a single Q&A pair inside an experiment combination.

    Ratings reference a combination + the index of the question inside that
    combination's ``detailed_results`` JSON list. We don't FK to dataset_items
    because RAGAS' detailed_results don't carry a stable dataset_item_id —
    the rating is about a specific *generated answer*, not the abstract
    question. Question text is denormalised for traceability.
    """

    __tablename__ = "human_ratings"

    id = Column(Integer, primary_key=True, index=True)
    combination_id = Column(
        Integer,
        ForeignKey("experiment_combinations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    question_index = Column(Integer, nullable=False)
    # "correct" | "incorrect" | "partial"
    rating = Column(String(20), nullable=False)
    notes = Column(Text)
    question_text = Column(Text)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    combination = relationship("ExperimentCombination", back_populates="human_ratings")

    __table_args__ = (
        UniqueConstraint(
            "combination_id", "question_index", name="uq_human_rating_combo_question"
        ),
    )
