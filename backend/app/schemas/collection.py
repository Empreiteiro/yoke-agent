from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class SavedCollectionResponse(BaseModel):
    id: int
    name: str
    experiment_id: Optional[int] = None
    combination_id: Optional[int] = None
    collection_name: str
    embedding_model: str
    embedding_dimensions: Optional[int] = None
    distance_metric: str
    chunk_size: int
    chunk_overlap: int
    top_k: int
    search_type: str
    overall_score: Optional[float] = None
    size_bytes: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class CollectionQueryRequest(BaseModel):
    question: str
    top_k: Optional[int] = None


class CollectionQueryResponse(BaseModel):
    answer: str
    contexts: list[str]
    token_usage: dict = {}
