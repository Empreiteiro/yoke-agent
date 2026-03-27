from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional

router = APIRouter()

SUPPORTED_VECTORSTORES = {
    "chromadb": {
        "name": "ChromaDB",
        "description": "Open-source embedding database, easy local setup",
        "default": True,
        "config_fields": ["persist_directory"],
    },
    "pinecone": {
        "name": "Pinecone",
        "description": "Managed vector database for production workloads",
        "default": False,
        "config_fields": ["api_key", "environment", "index_name"],
    },
    "weaviate": {
        "name": "Weaviate",
        "description": "Open-source vector search engine",
        "default": False,
        "config_fields": ["url", "api_key", "class_name"],
    },
    "qdrant": {
        "name": "Qdrant",
        "description": "High-performance vector similarity search",
        "default": False,
        "config_fields": ["url", "api_key", "collection_name"],
    },
    "pgvector": {
        "name": "PGVector",
        "description": "PostgreSQL extension for vector similarity search",
        "default": False,
        "config_fields": ["connection_string", "collection_name"],
    },
}


@router.get("/")
def list_vectorstores():
    return {"vectorstores": SUPPORTED_VECTORSTORES}


class VectorStoreConfig(BaseModel):
    type: str
    config: Optional[dict] = None


@router.post("/validate")
def validate_vectorstore_config(data: VectorStoreConfig):
    if data.type not in SUPPORTED_VECTORSTORES:
        return {"valid": False, "error": f"Unsupported vectorstore: {data.type}"}
    required_fields = SUPPORTED_VECTORSTORES[data.type]["config_fields"]
    if data.config:
        missing = [f for f in required_fields if f not in data.config]
        if missing:
            return {"valid": False, "error": f"Missing fields: {missing}"}
    return {"valid": True}
