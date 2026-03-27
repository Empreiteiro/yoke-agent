from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from typing import List

from app.core.database import get_db
from app.models.provider import Provider
from app.schemas.provider import (
    ProviderCreate,
    ProviderUpdate,
    ProviderResponse,
    ProviderTestResult,
    AvailableModelsResponse,
    PROVIDER_CATALOG,
    EMBEDDING_DIMENSIONS,
)

router = APIRouter()


@router.get("/catalog")
def get_provider_catalog():
    """Return the catalog of supported provider types and their known models."""
    return PROVIDER_CATALOG


@router.get("/", response_model=List[ProviderResponse])
def list_providers(db: Session = Depends(get_db)):
    providers = db.query(Provider).order_by(Provider.created_at.desc()).all()
    result = []
    for p in providers:
        resp = ProviderResponse.model_validate(p)
        resp.has_api_key = bool(p.api_key)
        result.append(resp)
    return result


@router.post("/", response_model=ProviderResponse)
def create_provider(data: ProviderCreate, db: Session = Depends(get_db)):
    if data.provider_type not in PROVIDER_CATALOG:
        raise HTTPException(status_code=400, detail=f"Unknown provider type: {data.provider_type}")

    provider = Provider(**data.model_dump())
    db.add(provider)
    db.commit()
    db.refresh(provider)

    resp = ProviderResponse.model_validate(provider)
    resp.has_api_key = bool(provider.api_key)
    return resp


@router.get("/{provider_id}", response_model=ProviderResponse)
def get_provider(provider_id: int, db: Session = Depends(get_db)):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    resp = ProviderResponse.model_validate(provider)
    resp.has_api_key = bool(provider.api_key)
    return resp


@router.put("/{provider_id}", response_model=ProviderResponse)
def update_provider(provider_id: int, data: ProviderUpdate, db: Session = Depends(get_db)):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(provider, key, value)

    db.commit()
    db.refresh(provider)

    resp = ProviderResponse.model_validate(provider)
    resp.has_api_key = bool(provider.api_key)
    return resp


@router.delete("/{provider_id}")
def delete_provider(provider_id: int, db: Session = Depends(get_db)):
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")
    db.delete(provider)
    db.commit()
    return {"detail": "Provider deleted"}


@router.post("/{provider_id}/test", response_model=ProviderTestResult)
def test_provider(provider_id: int, db: Session = Depends(get_db)):
    """Test connectivity for a provider by making a minimal API call."""
    provider = db.query(Provider).filter(Provider.id == provider_id).first()
    if not provider:
        raise HTTPException(status_code=404, detail="Provider not found")

    llm_ok = None
    embedding_ok = None
    errors = []

    if provider.supports_llm and provider.llm_models:
        try:
            from app.services.llm_factory import get_llm
            llm = get_llm(db, provider_id=provider.id)
            llm.invoke("Say 'ok'")
            llm_ok = True
        except Exception as e:
            llm_ok = False
            errors.append(f"LLM: {str(e)}")

    if provider.supports_embedding and provider.embedding_models:
        try:
            from app.services.llm_factory import get_embeddings
            emb = get_embeddings(db, provider_id=provider.id)
            emb.embed_query("test")
            embedding_ok = True
        except Exception as e:
            embedding_ok = False
            errors.append(f"Embedding: {str(e)}")

    success = (llm_ok is not False) and (embedding_ok is not False)
    message = "All tests passed" if success else "; ".join(errors)

    return ProviderTestResult(
        success=success,
        message=message,
        llm_ok=llm_ok,
        embedding_ok=embedding_ok,
    )


@router.get("/models/available", response_model=AvailableModelsResponse)
def get_available_models(db: Session = Depends(get_db)):
    """Return all LLM and embedding models from active providers."""
    providers = db.query(Provider).filter(Provider.is_active == True).all()

    llm_models = []
    embedding_models = []

    for p in providers:
        if p.supports_llm:
            for model in (p.llm_models or []):
                llm_models.append({
                    "provider_id": p.id,
                    "provider_name": p.name,
                    "provider_type": p.provider_type,
                    "model": model,
                    "is_default": model == p.default_llm_model,
                })
        if p.supports_embedding:
            for model in (p.embedding_models or []):
                embedding_models.append({
                    "provider_id": p.id,
                    "provider_name": p.name,
                    "provider_type": p.provider_type,
                    "model": model,
                    "is_default": model == p.default_embedding_model,
                })

    return AvailableModelsResponse(
        llm_models=llm_models,
        embedding_models=embedding_models,
    )


@router.get("/models/embedding-dimensions")
def get_embedding_dimensions():
    """Return dimension capabilities for all known embedding models."""
    return EMBEDDING_DIMENSIONS
