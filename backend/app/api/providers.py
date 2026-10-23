import logging

from fastapi import APIRouter, Depends, HTTPException, Query
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

logger = logging.getLogger(__name__)
router = APIRouter()

EMBEDDING_FAMILIES = {"bert", "nomic-bert"}


@router.get("/catalog")
def get_provider_catalog():
    """Return the catalog of supported provider types and their known models."""
    return PROVIDER_CATALOG


@router.get("/ollama/discover")
def discover_ollama_models(base_url: str = Query(..., description="Ollama server URL")):
    """Discover available LLM and embedding models from an Ollama server."""
    import httpx

    url = base_url.rstrip("/")
    try:
        resp = httpx.get(f"{url}/api/tags", timeout=10)
        resp.raise_for_status()
    except Exception as e:
        raise HTTPException(status_code=502, detail=f"Cannot reach Ollama at {url}: {e}")

    data = resp.json()
    llm_models = []
    embedding_models = []

    for m in data.get("models", []):
        name = m.get("name", "")
        family = m.get("details", {}).get("family", "")
        if family in EMBEDDING_FAMILIES:
            embedding_models.append(name)
        else:
            llm_models.append(name)

    return {
        "base_url": url,
        "llm_models": llm_models,
        "embedding_models": embedding_models,
        "total": len(llm_models) + len(embedding_models),
    }


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
    decision_ok = None
    errors = []

    if provider.supports_llm and provider.llm_models:
        try:
            from app.services.llm_factory import (
                get_llm, flex_supported_for, pick_flex_model,
            )
            # When flex is opted-in, prefer a flex-compatible model for
            # the smoke test. The default model may not support flex —
            # OpenAI/Google then return 400 and the user sees the test
            # fail even though the provider is configured correctly.
            flex_on = (provider.extra_config or {}).get("flex_tier")
            test_model = None
            if flex_on:
                if not flex_supported_for(provider.provider_type, provider.default_llm_model or ""):
                    test_model = pick_flex_model(provider)
                    if not test_model:
                        raise ValueError(
                            "Flex tier is enabled but no configured model "
                            "supports it. Add a flex-eligible model "
                            "(OpenAI: o3, gpt-5*, gpt-6*; "
                            "Google: gemini-2.5-*, gemini-3*) or disable Flex."
                        )
            llm = get_llm(db, provider_id=provider.id, model=test_model)
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

    if provider.supports_decision:
        try:
            from app.services.decision_models import test_decision_provider
            choice = test_decision_provider(provider)
            decision_ok = True
            logger.info("Decision provider %s answered test question with %r", provider.name, choice)
        except Exception as e:
            decision_ok = False
            errors.append(f"Decision model: {str(e)}")

    success = (llm_ok is not False) and (embedding_ok is not False) and (decision_ok is not False)
    message = "All tests passed" if success else "; ".join(errors)

    return ProviderTestResult(
        success=success,
        message=message,
        llm_ok=llm_ok,
        embedding_ok=embedding_ok,
        decision_ok=decision_ok,
    )


@router.get("/models/available", response_model=AvailableModelsResponse)
def get_available_models(db: Session = Depends(get_db)):
    """Return all LLM and embedding models from active providers."""
    providers = db.query(Provider).filter(Provider.is_active == True).all()

    llm_models = []
    embedding_models = []
    decision_models = []

    for p in providers:
        if p.supports_decision:
            for model in (p.decision_models or []):
                decision_models.append({
                    "provider_id": p.id,
                    "provider_name": p.name,
                    "provider_type": p.provider_type,
                    "model": model,
                    "is_default": model == p.default_decision_model,
                })
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
        decision_models=decision_models,
    )


@router.get("/models/embedding-dimensions")
def get_embedding_dimensions():
    """Return dimension capabilities for all known embedding models."""
    return EMBEDDING_DIMENSIONS


# ── Claude Code CLI status & auth ─────────────────────────────────────


@router.get("/claude-code/status")
def get_claude_code_status():
    """Check if Claude Code CLI is installed and authenticated."""
    from app.services.claude_code_llm import ChatClaudeCode
    return ChatClaudeCode.get_status()


@router.post("/claude-code/auth")
def save_claude_code_token(data: dict):
    """Save a Claude Code OAuth token for authentication."""
    token = data.get("token", "").strip()
    if not token:
        raise HTTPException(status_code=400, detail="Token is required")
    from app.services.claude_code_llm import ChatClaudeCode
    ChatClaudeCode.save_token(token)
    # Verify it works
    status = ChatClaudeCode.get_status()
    return {"success": True, "status": status}
