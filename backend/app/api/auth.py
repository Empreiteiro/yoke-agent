"""API Key management routes."""

import hashlib
import secrets
import logging
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.auth import invalidate_key_cache
from app.models.api_key import ApiKey
from app.schemas.api_key import ApiKeyCreate, ApiKeyResponse, ApiKeyCreateResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/status")
def auth_status(db: Session = Depends(get_db)):
    count = db.query(ApiKey).filter(ApiKey.is_active == True).count()  # noqa: E712
    return {"bootstrap_mode": count == 0, "key_count": count}


@router.get("/keys", response_model=list[ApiKeyResponse])
def list_api_keys(db: Session = Depends(get_db)):
    return db.query(ApiKey).order_by(ApiKey.created_at.desc()).all()


@router.post("/keys", response_model=ApiKeyCreateResponse)
def create_api_key(data: ApiKeyCreate, db: Session = Depends(get_db)):
    raw_key = "rag_" + secrets.token_hex(24)
    key_hash = hashlib.sha256(raw_key.encode()).hexdigest()
    key_prefix = raw_key[:12]

    api_key = ApiKey(
        name=data.name or "Default",
        key_hash=key_hash,
        key_prefix=key_prefix,
        is_active=True,
    )
    db.add(api_key)
    db.commit()
    db.refresh(api_key)
    invalidate_key_cache()

    return ApiKeyCreateResponse(
        id=api_key.id,
        name=api_key.name,
        key_prefix=api_key.key_prefix,
        is_active=api_key.is_active,
        created_at=api_key.created_at,
        key=raw_key,
    )


@router.delete("/keys/{key_id}")
def delete_api_key(key_id: int, db: Session = Depends(get_db)):
    api_key = db.query(ApiKey).filter(ApiKey.id == key_id).first()
    if not api_key:
        raise HTTPException(status_code=404, detail="API key not found")

    active_count = db.query(ApiKey).filter(ApiKey.is_active == True).count()  # noqa: E712
    if active_count <= 1 and api_key.is_active:
        raise HTTPException(
            status_code=400,
            detail="Cannot delete the last active API key. Create another key first.",
        )

    db.delete(api_key)
    db.commit()
    invalidate_key_cache()
    return {"detail": "API key deleted"}
