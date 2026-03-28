"""Saved collections API — list, delete, query, and save from experiments."""

import asyncio
import os
import shutil
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.models.saved_collection import SavedCollection
from app.models.experiment import Experiment
from app.schemas.collection import (
    SavedCollectionResponse,
    CollectionQueryRequest,
    CollectionQueryResponse,
)
from app.services.llm_factory import get_llm, get_embeddings, _resolve_provider
from app.services.token_tracker import log_llm_response

logger = logging.getLogger(__name__)

router = APIRouter()


def _get_dir_size(path: str) -> int:
    """Get total size of a directory in bytes."""
    total = 0
    if os.path.exists(path):
        for dirpath, _, filenames in os.walk(path):
            for f in filenames:
                total += os.path.getsize(os.path.join(dirpath, f))
    return total


@router.get("/", response_model=List[SavedCollectionResponse])
def list_collections(db: Session = Depends(get_db)):
    """List all saved collections with updated sizes."""
    cols = db.query(SavedCollection).order_by(SavedCollection.created_at.desc()).all()
    for col in cols:
        col.size_bytes = _get_dir_size(col.persist_path)
    db.commit()
    return cols


@router.delete("/{collection_id}")
def delete_collection(collection_id: int, db: Session = Depends(get_db)):
    """Delete a saved collection (files + DB row). Does not affect experiment history."""
    col = db.query(SavedCollection).filter(SavedCollection.id == collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    # Remove files
    if os.path.exists(col.persist_path):
        shutil.rmtree(col.persist_path, ignore_errors=True)

    db.delete(col)
    db.commit()
    return {"detail": "Collection deleted", "collection_id": collection_id}


@router.post("/{collection_id}/query", response_model=CollectionQueryResponse)
async def query_collection(
    collection_id: int,
    req: CollectionQueryRequest,
    db: Session = Depends(get_db),
):
    """Query a saved collection: retrieve contexts and generate an LLM answer."""
    col = db.query(SavedCollection).filter(SavedCollection.id == collection_id).first()
    if not col:
        raise HTTPException(status_code=404, detail="Collection not found")

    if not os.path.exists(col.persist_path):
        raise HTTPException(status_code=410, detail="Collection files no longer exist on disk")

    # Recreate embeddings with same model/dimensions
    embeddings = get_embeddings(db, model=col.embedding_model, dimensions=col.embedding_dimensions)

    # Open existing ChromaDB collection (no re-indexing)
    from langchain_community.vectorstores import Chroma
    vectorstore = Chroma(
        collection_name=col.collection_name,
        persist_directory=col.persist_path,
        embedding_function=embeddings,
    )

    # Retrieve
    top_k = req.top_k or col.top_k
    if col.search_type == "mmr":
        docs = vectorstore.max_marginal_relevance_search(req.question, k=top_k)
    else:
        docs = vectorstore.similarity_search(req.question, k=top_k)

    contexts = [doc.page_content for doc in docs]
    combined_context = "\n\n".join(contexts)

    # Generate answer
    llm = get_llm(db, temperature=0)
    prompt = f"""Based on the following context, answer the question.
If the answer cannot be found in the context, say "I cannot find the answer in the provided context."

Context:
{combined_context}

Question: {req.question}

Answer:"""

    response = await llm.ainvoke(prompt)

    # Log token usage
    token_usage = {}
    try:
        provider = _resolve_provider(db, None, capability="llm")
        log_llm_response(
            db=db,
            response=response,
            operation="collection_query",
            provider_name=provider.name,
            model_name=provider.default_llm_model or "unknown",
            metadata={"collection_id": col.id, "question": req.question[:100]},
        )
        if hasattr(response, "usage_metadata") and response.usage_metadata:
            token_usage = dict(response.usage_metadata)
    except Exception:
        pass

    return CollectionQueryResponse(
        answer=response.content,
        contexts=contexts,
        token_usage=token_usage,
    )


def _save_collection_sync(experiment_id: int):
    """Background task to save the winning collection from an experiment."""
    asyncio.run(_save_collection_task(experiment_id))


async def _save_collection_task(experiment_id: int):
    """Save the winning collection from an existing completed experiment."""
    db = SessionLocal()
    try:
        from app.services.experiment_runner import _save_winning_collection
        from app.models.document import Document as DocModel
        from app.models.dataset import Dataset
        from app.services.document_loader import load_documents

        experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
        if not experiment:
            return

        dataset = db.query(Dataset).filter(Dataset.id == experiment.dataset_id).first()
        if not dataset:
            return

        doc_models = db.query(DocModel).filter(DocModel.id.in_(dataset.document_ids or [])).all()
        filepaths = [doc.filepath for doc in doc_models]
        source_documents = load_documents(filepaths)

        await _save_winning_collection(experiment, source_documents, db)
    except Exception as e:
        logger.error(f"Failed to save collection for experiment {experiment_id}: {e}")
    finally:
        db.close()


@router.post("/save-from-experiment/{experiment_id}")
def save_from_experiment(
    experiment_id: int,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
    """Save the winning collection from an existing completed experiment."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    completed = [c for c in exp.combinations if c.status == "completed" and c.overall_score is not None]
    if not completed:
        raise HTTPException(status_code=400, detail="No completed combinations to save")

    # Check if already saved
    existing = db.query(SavedCollection).filter(SavedCollection.experiment_id == experiment_id).first()
    if existing:
        raise HTTPException(status_code=409, detail="Collection already saved for this experiment")

    background_tasks.add_task(_save_collection_sync, experiment_id)
    best = max(completed, key=lambda c: c.overall_score)
    return {
        "detail": "Collection save started",
        "experiment_id": experiment_id,
        "best_score": best.overall_score,
    }
