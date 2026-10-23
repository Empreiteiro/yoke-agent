"""Pydantic schemas for the Model Comparison workbench."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator

ModelKind = Literal["decision", "llm"]
Sampling = Literal["stratified", "random", "first", "all"]


class DecisionLabel(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)
    description: str = ""


class DecisionDatasetResponse(BaseModel):
    id: int
    slug: Optional[str] = None
    name: str
    description: Optional[str] = None
    language: Optional[str] = None
    task: str
    labels: list[DecisionLabel] = []
    is_builtin: bool = False
    item_count: int = 0
    source_filename: Optional[str] = None
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class DecisionDatasetDetail(DecisionDatasetResponse):
    label_counts: dict[str, int] = {}
    difficulty_counts: dict[str, int] = {}


class DecisionDatasetUpdate(BaseModel):
    name: Optional[str] = Field(None, min_length=1, max_length=255)
    description: Optional[str] = None
    task: Optional[str] = Field(None, min_length=1)
    # Descriptions can change; the set of label names must stay the same
    # because rows reference them.
    labels: Optional[list[DecisionLabel]] = None


class DecisionItemResponse(BaseModel):
    id: int
    text: str
    expected_label: str
    difficulty: Optional[str] = None

    class Config:
        from_attributes = True


class ModelSpec(BaseModel):
    kind: ModelKind
    provider_id: int
    model: str = Field(..., min_length=1, max_length=200)
    display_name: Optional[str] = Field(None, max_length=255)
    # USD per 1M tokens. Leave empty to use the built-in price table.
    input_price_per_million: Optional[float] = Field(None, ge=0)
    output_price_per_million: Optional[float] = Field(None, ge=0)


class ComparisonCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    dataset_id: int
    models: list[ModelSpec] = Field(..., min_length=1, max_length=8)
    sample_size: Optional[int] = Field(None, ge=1)
    sampling: Sampling = "stratified"
    seed: int = 42
    concurrency: int = Field(8, ge=1, le=32)
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    autostart: bool = True

    @field_validator("models")
    @classmethod
    def _unique_models(cls, models: list[ModelSpec]) -> list[ModelSpec]:
        seen = set()
        for m in models:
            key = (m.kind, m.provider_id, m.model, m.input_price_per_million, m.output_price_per_million)
            if key in seen:
                raise ValueError(f"Model '{m.model}' was selected twice")
            seen.add(key)
        return models


class EstimateRequest(BaseModel):
    dataset_id: int
    models: list[ModelSpec] = Field(..., min_length=1, max_length=8)
    sample_size: Optional[int] = Field(None, ge=1)
    sampling: Sampling = "stratified"
    seed: int = 42
