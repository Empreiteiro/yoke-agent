from pydantic import BaseModel
from datetime import datetime


class ApiKeyCreate(BaseModel):
    name: str = "Default"


class ApiKeyResponse(BaseModel):
    id: int
    name: str
    key_prefix: str
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ApiKeyCreateResponse(ApiKeyResponse):
    key: str
