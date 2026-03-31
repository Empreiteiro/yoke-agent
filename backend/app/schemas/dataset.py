from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class DatasetItemCreate(BaseModel):
    question: str
    ground_truth: str
    context: Optional[str] = None
    source_document: Optional[str] = None


class DatasetItemResponse(BaseModel):
    id: int
    question: str
    ground_truth: str
    context: Optional[str] = None
    source_document: Optional[str] = None
    is_manual: int
    created_at: datetime

    class Config:
        from_attributes = True


class DatasetItemUpdate(BaseModel):
    question: Optional[str] = None
    ground_truth: Optional[str] = None
    context: Optional[str] = None


class DatasetCreate(BaseModel):
    name: Optional[str] = None
    description: Optional[str] = None
    document_ids: list[int]


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    error_message: Optional[str] = None
    document_ids: Optional[list[int]] = None
    sampled_pages: Optional[list] = None
    items: list[DatasetItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasetGenerateOptions(BaseModel):
    reading_mode: str = "full"  # "full" or "partial"
    max_pages: Optional[int] = None  # When partial, max pages to read (random)
    num_questions: Optional[int] = None  # None = auto-calculate based on content size
    language: str = "auto"  # "auto", "English", "Portuguese", "Spanish", etc.
    provider_id: Optional[int] = None  # LLM provider ID (None = auto-detect first active)
    model: Optional[str] = None  # LLM model name (None = provider default)


class DatasetApprove(BaseModel):
    pass
