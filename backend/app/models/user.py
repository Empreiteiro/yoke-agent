"""User and audit log models for multi-tenancy (issue #123)."""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, Text, Index, func
from sqlalchemy.orm import relationship

from app.core.database import Base


ROLE_ADMIN = "admin"
ROLE_USER = "user"
ROLE_VIEWER = "viewer"
VALID_ROLES = {ROLE_ADMIN, ROLE_USER, ROLE_VIEWER}


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    email = Column(String(255), unique=True, nullable=False, index=True)
    password_hash = Column(String(255), nullable=False)
    role = Column(String(20), default=ROLE_USER, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, server_default=func.now())
    updated_at = Column(DateTime, server_default=func.now(), onupdate=func.now())

    api_keys = relationship("ApiKey", back_populates="user")


class AuditLog(Base):
    """Append-only log of user actions.

    Writes happen from ``AuditLogMiddleware`` after each non-exempt request so
    downstream admins can see who did what and when. The middleware captures
    method, path, status, user id, and client IP; individual endpoints can
    enrich the metadata column with resource-specific details if they need to.
    """

    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=True, index=True)
    user_email = Column(String(255))
    action = Column(String(50))  # HTTP method
    resource = Column(String(255))  # URL path
    status_code = Column(Integer)
    ip_address = Column(String(64))
    extra = Column(Text)  # JSON-encoded extra fields (nullable)
    created_at = Column(DateTime, server_default=func.now(), index=True)

    __table_args__ = (
        Index("ix_audit_logs_user_created", "user_id", "created_at"),
    )
