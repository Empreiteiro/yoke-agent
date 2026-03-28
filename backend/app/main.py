import logging
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from sqlalchemy import inspect, text

from app.core.config import settings
from app.core.database import engine, Base
from app.api import documents, datasets, experiments, vectorstores, providers, token_usage, collections
from app.models import saved_collection  # noqa: F401 — ensure table creation

logger = logging.getLogger(__name__)


def _run_migrations(engine):
    """Add missing columns to existing tables."""
    inspector = inspect(engine)
    migrations = [
        ("datasets", "error_message", "TEXT"),
        ("experiment_combinations", "error_message", "TEXT"),
        ("experiment_combinations", "total_tokens", "INTEGER DEFAULT 0"),
        ("experiment_combinations", "total_cost", "REAL DEFAULT 0.0"),
    ]
    with engine.connect() as conn:
        for table, column, col_type in migrations:
            if table in inspector.get_table_names():
                existing = [c["name"] for c in inspector.get_columns(table)]
                if column not in existing:
                    conn.execute(text(f"ALTER TABLE {table} ADD COLUMN {column} {col_type}"))
                    conn.commit()
                    logger.info(f"Added column {table}.{column}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
    _run_migrations(engine)
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
app.include_router(token_usage.router, prefix="/api/token-usage", tags=["token-usage"])
app.include_router(collections.router, prefix="/api/collections", tags=["collections"])


@app.get("/api/health")
async def health_check():
    return {"status": "healthy", "version": "0.1.0"}
