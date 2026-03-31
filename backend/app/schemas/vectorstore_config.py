from pydantic import BaseModel
from datetime import datetime
from typing import Optional


class VectorStoreConfigCreate(BaseModel):
    name: str
    vectorstore_type: str
    is_active: bool = True
    api_key: Optional[str] = None
    config: Optional[dict] = None


class VectorStoreConfigUpdate(BaseModel):
    name: Optional[str] = None
    is_active: Optional[bool] = None
    api_key: Optional[str] = None
    config: Optional[dict] = None


class VectorStoreConfigResponse(BaseModel):
    id: int
    name: str
    vectorstore_type: str
    is_active: bool
    has_api_key: bool = False
    config: Optional[dict] = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True
