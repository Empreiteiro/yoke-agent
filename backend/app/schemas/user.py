"""Pydantic schemas for the user/auth endpoints (issue #123)."""

from datetime import datetime
from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["admin", "user", "viewer"]


class UserRegister(BaseModel):
    email: str = Field(..., max_length=255)
    password: str = Field(..., min_length=8, max_length=128)


class UserLogin(BaseModel):
    email: str = Field(..., max_length=255)
    password: str


class UserResponse(BaseModel):
    id: int
    email: str = Field(..., max_length=255)
    role: Role
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserResponse


class UserRoleUpdate(BaseModel):
    role: Role


class AuditLogResponse(BaseModel):
    id: int
    user_id: Optional[int]
    user_email: Optional[str]
    action: Optional[str]
    resource: Optional[str]
    status_code: Optional[int]
    ip_address: Optional[str]
    created_at: datetime

    class Config:
        from_attributes = True
