from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager

from app.core.config import settings
from app.core.database import engine, Base
from app.api import documents, datasets, experiments, vectorstores, providers


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    yield


app = FastAPI(
    title="RAG Optimization Pipeline",
    description="End-to-end platform for optimizing Retrieval-Augmented Generation pipelines",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(documents.router, prefix="/api/documents", tags=["documents"])
app.include_router(datasets.router, prefix="/api/datasets", tags=["datasets"])
app.include_router(experiments.router, prefix="/api/experiments", tags=["experiments"])
app.include_router(vectorstores.router, prefix="/api/vectorstores", tags=["vectorstores"])
app.include_router(providers.router, prefix="/api/providers", tags=["providers"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
