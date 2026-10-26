"""Models for the Model Comparison workbench.

A *decision dataset* is a labeled classification set (text → one label out
of a fixed list). A *comparison* runs the same sample of a dataset through
several models — decision models such as TypeSafe's Jev, pre-trained text
classifiers, regex rule baselines and regular LLMs prompted as classifiers —
and stores per-item predictions plus aggregated accuracy, cost and latency
per model.
"""

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text, JSON, func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class DecisionDataset(Base):
    __tablename__ = "decision_datasets"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    slug = Column(String(100), nullable=True, index=True)  # set for built-in datasets
    name = Column(String(255), nullable=False)
    description = Column(Text, nullable=True)
    language = Column(String(20), nullable=True)
    # The question every model answers about each row, e.g. "Which team
    # should handle this ticket?"
    task = Column(Text, nullable=False)
    labels = Column(JSON, nullable=False, default=list)  # [{"name", "description"}]
    is_builtin = Column(Boolean, default=False)
    source_filename = Column(String(255), nullable=True)
    item_count = Column(Integer, default=0)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    items = relationship(
        "DecisionDatasetItem", back_populates="dataset",
        cascade="all, delete-orphan", passive_deletes=True,
    )


class DecisionDatasetItem(Base):
    __tablename__ = "decision_dataset_items"

    id = Column(Integer, primary_key=True, index=True)
    dataset_id = Column(Integer, ForeignKey("decision_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    text = Column(Text, nullable=False)
    expected_label = Column(String(200), nullable=False, index=True)
    difficulty = Column(String(20), nullable=True)

    dataset = relationship("DecisionDataset", back_populates="items")


class DecisionComparison(Base):
    __tablename__ = "decision_comparisons"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    name = Column(String(255), nullable=False)
    dataset_id = Column(Integer, ForeignKey("decision_datasets.id", ondelete="CASCADE"), nullable=False, index=True)
    # Snapshot of the dataset question + labels at creation time so later
    # edits to the dataset don't silently change what was measured.
    dataset_name = Column(String(255), nullable=True)
    task = Column(Text, nullable=True)
    labels = Column(JSON, nullable=False, default=list)
    status = Column(String(20), default="pending")  # pending, running, stopping, stopped, completed, failed
    sampling = Column(String(20), default="stratified")  # stratified, random, first, all
    sample_size = Column(Integer, nullable=True)
    seed = Column(Integer, default=42)
    item_ids = Column(JSON, nullable=False, default=list)
    # {"concurrency": 8, "temperature": 0.0, "latency_mode": false,
    #  "warmup": 0, "analysis": {"positive_labels": [...], "prevalence": …}}
    config = Column(JSON, default=dict)
    error_message = Column(Text, nullable=True)
    created_at = Column(DateTime, server_default=func.now())
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    model_results = relationship(
        "DecisionModelResult", back_populates="comparison",
        cascade="all, delete-orphan", passive_deletes=True,
        order_by="DecisionModelResult.position",
    )


class DecisionModelResult(Base):
    __tablename__ = "decision_model_results"

    id = Column(Integer, primary_key=True, index=True)
    comparison_id = Column(Integer, ForeignKey("decision_comparisons.id", ondelete="CASCADE"), nullable=False, index=True)
    position = Column(Integer, default=0)
    kind = Column(String(20), nullable=False)  # decision | llm | classifier | rules
    provider_id = Column(Integer, nullable=True)  # None for rule baselines
    provider_name = Column(String(100), nullable=True)
    provider_type = Column(String(50), nullable=True)
    model_name = Column(String(200), nullable=False)
    display_name = Column(String(255), nullable=True)
    # USD per 1M tokens used for cost; None when the price is unknown.
    input_price_per_million = Column(Float, nullable=True)
    output_price_per_million = Column(Float, nullable=True)
    # USD per hour of the hardware serving a self-hosted model; charged for
    # the model's wall-clock time in the run.
    infra_cost_per_hour = Column(Float, nullable=True)
    # Snapshot of everything that shapes the model's answers (task and label
    # overrides, prompt templates, label aliases, classifier mapping, rules)
    # plus deployment metadata — see ModelSpec.
    config = Column(JSON, nullable=True)
    variant = Column(String(100), nullable=True)
    policy_hash = Column(String(16), nullable=True)

    status = Column(String(20), default="pending")  # pending, running, stopped, completed, failed
    error_message = Column(Text, nullable=True)

    total = Column(Integer, default=0)
    processed = Column(Integer, default=0)
    correct = Column(Integer, default=0)
    incorrect = Column(Integer, default=0)
    failed = Column(Integer, default=0)  # API error or answer outside the label set
    accuracy = Column(Float, nullable=True)
    macro_f1 = Column(Float, nullable=True)

    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    tokens_estimated = Column(Boolean, default=False)
    token_cost = Column(Float, nullable=True)
    infra_cost = Column(Float, nullable=True)
    total_cost = Column(Float, nullable=True)  # token_cost + infra_cost

    avg_latency_ms = Column(Float, nullable=True)
    p50_latency_ms = Column(Float, nullable=True)
    p90_latency_ms = Column(Float, nullable=True)
    p95_latency_ms = Column(Float, nullable=True)
    p99_latency_ms = Column(Float, nullable=True)
    latency_std_ms = Column(Float, nullable=True)
    wall_time_ms = Column(Float, nullable=True)
    avg_attempts = Column(Float, nullable=True)
    retried = Column(Integer, default=0)  # predictions that needed > 1 attempt
    avg_confidence = Column(Float, nullable=True)
    avg_confidence_correct = Column(Float, nullable=True)
    avg_confidence_incorrect = Column(Float, nullable=True)

    per_label = Column(JSON, nullable=True)  # {label: {support, correct, predicted, precision, recall, f1}}
    confusion = Column(JSON, nullable=True)  # {expected: {predicted: count}}

    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    comparison = relationship("DecisionComparison", back_populates="model_results")


class DecisionPrediction(Base):
    __tablename__ = "decision_predictions"

    id = Column(Integer, primary_key=True, index=True)
    comparison_id = Column(Integer, ForeignKey("decision_comparisons.id", ondelete="CASCADE"), nullable=False, index=True)
    model_result_id = Column(Integer, ForeignKey("decision_model_results.id", ondelete="CASCADE"), nullable=False, index=True)
    item_id = Column(Integer, nullable=False, index=True)
    expected_label = Column(String(200), nullable=False)
    predicted_label = Column(String(200), nullable=True)
    status = Column(String(20), default="ok")  # ok | invalid | error
    is_correct = Column(Boolean, default=False)
    confidence = Column(Float, nullable=True)
    # Score per dataset label when the model returns a distribution
    # (decision models, classifiers); used for ROC curves and calibration.
    probabilities = Column(JSON, nullable=True)
    # Latency of the successful attempt only; retries are counted here.
    latency_ms = Column(Float, nullable=True)
    attempts = Column(Integer, nullable=True)
    input_tokens = Column(Integer, default=0)
    output_tokens = Column(Integer, default=0)
    cost = Column(Float, nullable=True)
    error = Column(Text, nullable=True)
    raw_output = Column(Text, nullable=True)
