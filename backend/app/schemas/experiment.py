from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Optional


class RAGParams(BaseModel):
    chunk_size: int = Field(..., description="Size of text chunks in tokens")
    chunk_overlap: int = Field(..., description="Overlap between chunks as percentage")
    embedding_model: str = Field(..., description="Embedding model identifier")
    top_k: int = Field(..., description="Number of documents to retrieve")
    search_type: str = Field(..., description="Search type: vector, hybrid, mmr")
    embedding_dimensions: Optional[int] = Field(None, description="Embedding output dimensions (None = model default)")
    distance_metric: str = Field("cosine", description="Distance metric: cosine, l2, ip")


class ExperimentCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    dataset_id: int
    vectorstore_type: str = "chromadb"


class GridSearchConfig(BaseModel):
    chunk_sizes: list[int] = [256, 512, 1024]
    chunk_overlaps: list[int] = [10, 20, 30]
    embedding_models: list[str] = ["text-embedding-3-small"]
    top_k_values: list[int] = [3, 5, 10]
    search_types: list[str] = ["vector", "hybrid"]
    embedding_dimensions: list[int] = []  # Empty = use model defaults
    distance_metrics: list[str] = ["cosine"]  # cosine, l2, ip
    # Optional RAGAS metrics to include beyond the fixed ones
    optional_metrics: list[str] = []


class CombinationResponse(BaseModel):
    id: int
    params: dict
    status: str
    faithfulness: Optional[float] = None
    answer_relevancy: Optional[float] = None
    context_precision: Optional[float] = None
    context_recall: Optional[float] = None
    answer_similarity: Optional[float] = None
    answer_correctness: Optional[float] = None
    overall_score: Optional[float] = None
    duration_seconds: Optional[float] = None
    detailed_results: Optional[Any] = None
    error_message: Optional[str] = None
    created_at: datetime
    completed_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ExperimentResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    dataset_id: int
    dataset_name: Optional[str] = None
    dataset_questions: Optional[int] = None
    status: str
    vectorstore_type: str
    combinations: list[CombinationResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ExperimentReport(BaseModel):
    experiment: ExperimentResponse
    best_combination: Optional[CombinationResponse] = None
    summary: dict
