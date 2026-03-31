"""Vector store configuration API routes."""

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.vectorstore_config import VectorStoreConfig
from app.schemas.vectorstore_config import (
    VectorStoreConfigCreate,
    VectorStoreConfigUpdate,
    VectorStoreConfigResponse,
)

router = APIRouter()

VECTORSTORE_CATALOG = {
    "pinecone": {
        "label": "Pinecone",
        "description": "Managed vector database for production workloads",
        "icon": "🌲",
        "requires_api_key": True,
        "config_fields": [
            {"name": "environment", "label": "Environment", "required": True, "placeholder": "us-east-1-aws"},
            {"name": "index_name", "label": "Index Name", "required": True, "placeholder": "my-index"},
        ],
    },
    "qdrant": {
        "label": "Qdrant",
        "description": "High-performance vector similarity search engine",
        "icon": "🔷",
        "requires_api_key": False,
        "config_fields": [
            {"name": "url", "label": "URL", "required": True, "placeholder": "http://localhost:6333"},
        ],
    },
    "weaviate": {
        "label": "Weaviate",
        "description": "Open-source vector search engine with semantic capabilities",
        "icon": "🟩",
        "requires_api_key": False,
        "config_fields": [
            {"name": "url", "label": "URL", "required": True, "placeholder": "http://localhost:8080"},
        ],
    },
    "pgvector": {
        "label": "PGVector",
        "description": "PostgreSQL extension for vector similarity search",
        "icon": "🐘",
        "requires_api_key": False,
        "config_fields": [
            {"name": "connection_string", "label": "Connection String", "required": True, "placeholder": "postgresql://user:pass@localhost/db"},
        ],
    },
}


def _to_response(vs: VectorStoreConfig) -> VectorStoreConfigResponse:
    return VectorStoreConfigResponse(
        id=vs.id,
        name=vs.name,
        vectorstore_type=vs.vectorstore_type,
        is_active=vs.is_active,
        has_api_key=bool(vs.api_key),
        config=vs.config,
        created_at=vs.created_at,
        updated_at=vs.updated_at,
    )


@router.get("/catalog")
def get_catalog():
    return VECTORSTORE_CATALOG


@router.get("/configs", response_model=list[VectorStoreConfigResponse])
def list_configs(db: Session = Depends(get_db)):
    configs = db.query(VectorStoreConfig).order_by(VectorStoreConfig.created_at.desc()).all()
    return [_to_response(c) for c in configs]


@router.post("/configs", response_model=VectorStoreConfigResponse)
def create_config(data: VectorStoreConfigCreate, db: Session = Depends(get_db)):
    if data.vectorstore_type not in VECTORSTORE_CATALOG:
        raise HTTPException(status_code=400, detail=f"Unsupported type: {data.vectorstore_type}")

    vs = VectorStoreConfig(
        name=data.name,
        vectorstore_type=data.vectorstore_type,
        is_active=data.is_active,
        api_key=data.api_key,
        config=data.config or {},
    )
    db.add(vs)
    db.commit()
    db.refresh(vs)
    return _to_response(vs)


@router.put("/configs/{config_id}", response_model=VectorStoreConfigResponse)
def update_config(config_id: int, data: VectorStoreConfigUpdate, db: Session = Depends(get_db)):
    vs = db.query(VectorStoreConfig).filter(VectorStoreConfig.id == config_id).first()
    if not vs:
        raise HTTPException(status_code=404, detail="Config not found")

    update_data = data.model_dump(exclude_unset=True)
    for key, value in update_data.items():
        setattr(vs, key, value)

    db.commit()
    db.refresh(vs)
    return _to_response(vs)


@router.delete("/configs/{config_id}")
def delete_config(config_id: int, db: Session = Depends(get_db)):
    vs = db.query(VectorStoreConfig).filter(VectorStoreConfig.id == config_id).first()
    if not vs:
        raise HTTPException(status_code=404, detail="Config not found")
    db.delete(vs)
    db.commit()
    return {"detail": "Deleted"}


@router.post("/configs/{config_id}/test")
def test_config(config_id: int, db: Session = Depends(get_db)):
    vs = db.query(VectorStoreConfig).filter(VectorStoreConfig.id == config_id).first()
    if not vs:
        raise HTTPException(status_code=404, detail="Config not found")

    try:
        config = dict(vs.config or {})
        if vs.api_key:
            config["api_key"] = vs.api_key

        from app.services.vectorstore_factory import create_vectorstore_backend
        backend = create_vectorstore_backend(vs.vectorstore_type, config)
        return {"success": True, "message": f"Connection to {vs.vectorstore_type} initialized successfully."}
    except Exception as e:
        return {"success": False, "message": str(e)}


@router.get("/available")
def get_available(db: Session = Depends(get_db)):
    """Return ChromaDB (always) + all active configured vectorstores."""
    stores = [{"type": "chromadb", "name": "ChromaDB (Default)"}]

    active = db.query(VectorStoreConfig).filter(VectorStoreConfig.is_active == True).all()
    for vs in active:
        label = VECTORSTORE_CATALOG.get(vs.vectorstore_type, {}).get("label", vs.vectorstore_type)
        stores.append({"type": vs.vectorstore_type, "name": f"{label} — {vs.name}", "config_id": vs.id})

    return stores
