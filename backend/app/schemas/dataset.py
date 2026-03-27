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
    name: str
    description: Optional[str] = None
    document_ids: list[int]


class DatasetResponse(BaseModel):
    id: int
    name: str
    description: Optional[str] = None
    status: str
    document_ids: Optional[list[int]] = None
    items: list[DatasetItemResponse] = []
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class DatasetApprove(BaseModel):
    pass
