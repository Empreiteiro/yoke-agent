from pydantic import BaseModel, Field
from datetime import datetime
from typing import Any, Optional


class RAGParams(BaseModel):
    chunk_size: int = Field(..., description="Size of text chunks in tokens")
    chunk_overlap: int = Field(..., description="Overlap between chunks as percentage")
    embedding_model: str = Field(..., description="Embedding model identifier")
    top_k: int = Field(..., description="Number of documents to retrieve")
    search_type: str = Field(..., description="Search type: vector, hybrid, mmr, multi_query, agentic")
    embedding_dimensions: Optional[int] = Field(None, description="Embedding output dimensions (None = model default)")
    distance_metric: str = Field("cosine", description="Distance metric: cosine, l2, ip")
    chunking_strategy: str = Field("recursive", description="Chunking strategy: recursive, token, semantic")
    answer_language: str = Field("auto", description="Language for generated answers: auto, English, Portuguese, etc.")
    pipeline_type: str = Field("rag", description="Pipeline type: rag or graphrag")
    multi_query_count: Optional[int] = Field(None, description="Number of alternative queries for multi_query search")
    agent_max_steps: Optional[int] = Field(None, description="Max retrieval steps for agentic search")
    crag_relevance_threshold: Optional[float] = Field(None, description="Relevance threshold for CRAG grading (0-1)")
    crag_max_retries: Optional[int] = Field(None, description="Max query reformulation attempts for CRAG")
    self_rag_retrieval_threshold: Optional[float] = Field(None, description="Confidence threshold for Self-RAG retrieval decision (0-1)")
    raptor_max_levels: Optional[int] = Field(None, description="Depth of RAPTOR summary tree")
    raptor_clustering: Optional[str] = Field(None, description="RAPTOR clustering method: kmeans, gmm")
    raptor_retrieval_mode: Optional[str] = Field(None, description="RAPTOR retrieval: collapsed, tree_traversal, level_specific")
    prompt_template: Optional[str] = Field(None, description="Custom answer generation prompt (must contain {context} and {question})")


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
    chunking_strategies: list[str] = ["recursive"]  # recursive, token, semantic
    answer_language: str = "auto"  # Language for LLM answers: auto, English, Portuguese, etc.
    # Optional RAGAS metrics to include beyond the fixed ones
    optional_metrics: list[str] = []
    # Multi-Query RAG settings
    multi_query_counts: list[int] = [3]  # Number of alternative queries (3-5)
    # Agentic RAG settings
    agent_max_steps: list[int] = [5]  # Max agent retrieval steps (3-10)
    # CRAG settings
    crag_relevance_thresholds: list[float] = [0.7]  # Relevance threshold (0-1)
    crag_max_retries: list[int] = [2]  # Max reformulation attempts (1-3)
    # Self-RAG settings
    self_rag_retrieval_thresholds: list[float] = [0.5]  # Retrieval decision threshold (0-1)
    # RAPTOR settings
    raptor_max_levels: list[int] = [3]  # Tree depth (2-5)
    raptor_clustering: list[str] = ["kmeans"]  # kmeans, gmm
    raptor_retrieval_modes: list[str] = ["collapsed"]  # collapsed, tree_traversal, level_specific
    # Prompt templates (grid-searchable: test different prompts in the same experiment)
    prompt_templates: list[str] = []  # Empty = use default prompt. Each entry is a full prompt with {context} and {question} placeholders.
    # GraphRAG settings
    pipeline_types: list[str] = ["rag"]  # rag, graphrag
    entity_extraction_models: list[str] = []  # LLM models for entity extraction
    max_gleanings: list[int] = [1]  # extraction passes per chunk
    community_levels: list[int] = [1]  # Leiden resolution
    search_modes: list[str] = ["local"]  # local, global, hybrid


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
    total_tokens: Optional[int] = 0
    total_cost: Optional[float] = 0.0
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
