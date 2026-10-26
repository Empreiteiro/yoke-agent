"""Pydantic schemas for the Model Comparison workbench."""

import re
from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator, model_validator

ModelKind = Literal["decision", "llm", "classifier", "rules"]
Sampling = Literal["stratified", "random", "first", "all"]
FailurePolicy = Literal["open", "closed", "exclude"]


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


class RuleSpec(BaseModel):
    """Regex patterns that assign ``label`` when any of them matches."""
    label: str = Field(..., min_length=1, max_length=200)
    patterns: list[str] = Field(default_factory=list, max_length=200)


class DeploymentInfo(BaseModel):
    """Where and how a model ran — latency is only comparable with this."""
    hardware: Optional[str] = Field(None, max_length=120)  # "CPU — MacBook Pro M1", "1× L40S"
    parameters: Optional[str] = Field(None, max_length=40)  # "184M", "35B"
    serving: Optional[str] = Field(None, max_length=80)  # "vLLM", "TEI", "managed API"
    region: Optional[str] = Field(None, max_length=80)


class ModelSpec(BaseModel):
    kind: ModelKind
    # Required for every kind except ``rules`` (which runs in-process).
    provider_id: Optional[int] = None
    model: str = Field(..., min_length=1, max_length=200)
    display_name: Optional[str] = Field(None, max_length=255)
    # USD per 1M tokens. Leave empty to use the built-in price table.
    input_price_per_million: Optional[float] = Field(None, ge=0)
    output_price_per_million: Optional[float] = Field(None, ge=0)
    # USD per hour of the hardware serving a self-hosted model.
    infra_cost_per_hour: Optional[float] = Field(None, ge=0)
    # LLMs: send requests on the flex service tier (OpenAI o3 / gpt-5* /
    # gpt-6*, Gemini 2.5 / 3.x) — about half the price, slower and
    # best-effort. None = the provider's setting; ignored elsewhere.
    flex: Optional[bool] = None
    deployment: Optional[DeploymentInfo] = None

    # A short name for this configuration, e.g. "default policy" or
    # "tuned policy". The same model may appear several times with
    # different variants to measure prompt/policy sensitivity.
    variant: Optional[str] = Field(None, max_length=100)
    # Policy overrides: the question and the label definitions this model
    # sees instead of the dataset's.
    task: Optional[str] = Field(None, max_length=20_000)
    label_descriptions: Optional[dict[str, str]] = None
    # LLM prompt templates. Placeholders: {task}, {labels}, {label_names},
    # {text}. Empty = the built-in classification prompt.
    system_prompt: Optional[str] = Field(None, max_length=20_000)
    user_prompt: Optional[str] = Field(None, max_length=20_000)
    # Raw answers or classifier-native labels → dataset labels, e.g.
    # {"INJECTION": "prompt_injection", "unsafe": "jailbreak"}.
    label_map: Optional[dict[str, str]] = None
    # Classifiers: when the best mapped score is below ``threshold`` the
    # model answers ``fallback_label`` (also used when a detector finds
    # nothing).
    threshold: Optional[float] = Field(None, ge=0, le=1)
    fallback_label: Optional[str] = Field(None, max_length=200)
    # Rule baselines: first rule with a matching pattern wins, otherwise
    # ``default_label``.
    rules: Optional[list[RuleSpec]] = Field(None, max_length=100)
    default_label: Optional[str] = Field(None, max_length=200)
    case_sensitive: bool = False

    @model_validator(mode="after")
    def _check_kind(self) -> "ModelSpec":
        if self.kind == "rules":
            if not self.rules or not any(r.patterns for r in self.rules):
                raise ValueError("A rules baseline needs at least one pattern")
            if not self.default_label:
                raise ValueError("A rules baseline needs a default label (used when no pattern matches)")
            for rule in self.rules:
                for pattern in rule.patterns:
                    try:
                        re.compile(pattern)
                    except re.error as e:
                        raise ValueError(f"Invalid regex {pattern!r} for label '{rule.label}': {e}")
        elif self.provider_id is None:
            raise ValueError(f"Model '{self.model}' needs a provider")
        if self.threshold is not None and not self.fallback_label:
            raise ValueError("A threshold needs a fallback label to answer below it")
        return self

    def referenced_labels(self) -> set[str]:
        """Dataset labels this spec mentions — validated against the dataset."""
        labels = set((self.label_descriptions or {}).keys()) | set((self.label_map or {}).values())
        labels |= {l for l in (self.fallback_label, self.default_label) if l}
        labels |= {r.label for r in self.rules or []}
        return labels

    def snapshot(self) -> dict:
        """Settings stored with the result (everything except identity and price)."""
        return self.model_dump(
            exclude={"kind", "provider_id", "model", "display_name", "input_price_per_million",
                     "output_price_per_million", "infra_cost_per_hour"},
            exclude_none=True,
        )


class AnalysisSettings(BaseModel):
    """How the guardrail (binary) view reads a comparison."""
    # Labels that mean "block". None = auto-detect (everything except
    # labels named like "safe" / "benign").
    positive_labels: Optional[list[str]] = None
    # What a failed request means: let it through, block it, or drop it.
    failure_policy: FailurePolicy = "open"
    # Share of positive traffic expected in production; None = the sample's.
    prevalence: Optional[float] = Field(None, gt=0, lt=1)
    # Relative cost of a missed positive vs. a false alarm.
    fn_cost: float = Field(1.0, ge=0)
    fp_cost: float = Field(1.0, ge=0)


class ComparisonCreate(BaseModel):
    name: Optional[str] = Field(None, max_length=255)
    dataset_id: int
    models: list[ModelSpec] = Field(..., min_length=1, max_length=8)
    sample_size: Optional[int] = Field(None, ge=1)
    sampling: Sampling = "stratified"
    seed: int = 42
    concurrency: int = Field(8, ge=1, le=32)
    temperature: float = Field(0.0, ge=0.0, le=2.0)
    # Latency benchmark: one request at a time, models one after another,
    # after ``warmup`` discarded requests per model.
    latency_mode: bool = False
    warmup: int = Field(0, ge=0, le=20)
    analysis: Optional[AnalysisSettings] = None
    autostart: bool = True

    @field_validator("models")
    @classmethod
    def _unique_models(cls, models: list[ModelSpec]) -> list[ModelSpec]:
        seen = set()
        for m in models:
            key = m.model_dump_json(exclude={"display_name", "deployment"})
            if key in seen:
                label = f"{m.model} ({m.variant})" if m.variant else m.model
                raise ValueError(f"Model '{label}' was selected twice with the same settings")
            seen.add(key)
        return models


class EstimateRequest(BaseModel):
    dataset_id: int
    models: list[ModelSpec] = Field(..., min_length=1, max_length=8)
    sample_size: Optional[int] = Field(None, ge=1)
    sampling: Sampling = "stratified"
    seed: int = 42
