"""Experiment runner that orchestrates the full grid search execution."""

import logging
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

import os

from app.models.document import Document as DocumentModel
from app.models.dataset import Dataset, DatasetItem
from app.models.experiment import Experiment, ExperimentCombination
from app.models.saved_collection import SavedCollection
from app.services.document_loader import load_documents
from app.services.rag_pipeline import run_rag_pipeline, chunk_documents
from app.services.ragas_evaluator import evaluate_rag_results
from app.services.llm_factory import get_embeddings


async def run_single_combination(
    combination: ExperimentCombination,
    source_documents: list,
    questions: list[str],
    ground_truths: list[str],
    vectorstore_type: str,
    vectorstore_config: Optional[Dict[str, Any]] = None,
    optional_metrics: Optional[list[str]] = None,
    db: Session = None,
) -> None:
    """Run a single parameter combination and evaluate with RAGAS."""
    start_time = time.time()

    try:
        combination.status = "running"
        if db:
            db.commit()

        # Run RAG pipeline
        rag_results = await run_rag_pipeline(
            documents=source_documents,
            questions=questions,
            params=combination.params,
            db=db,
            vectorstore_type=vectorstore_type,
            vectorstore_config=vectorstore_config,
            experiment_id=combination.experiment_id,
            combination_id=combination.id,
        )

        # Evaluate with RAGAS
        eval_results = await evaluate_rag_results(
            rag_results=rag_results,
            ground_truths=ground_truths,
            optional_metrics=optional_metrics,
            db=db,
        )

        # Update combination with results
        scores = eval_results["scores"]
        combination.faithfulness = scores.get("faithfulness")
        combination.answer_relevancy = scores.get("answer_relevancy")
        combination.context_precision = scores.get("context_precision")
        combination.context_recall = scores.get("context_recall")
        combination.answer_similarity = scores.get("answer_similarity")
        combination.answer_correctness = scores.get("answer_correctness")
        combination.overall_score = scores.get("overall_score")
        combination.detailed_results = eval_results.get("detailed_results")
        combination.status = "completed"

    except Exception as e:
        logger.error(f"Combination {combination.id} failed: {e}\n{traceback.format_exc()}")
        combination.status = "failed"
        combination.error_message = str(e)
        combination.detailed_results = {"error": str(e), "traceback": traceback.format_exc()}

    finally:
        combination.duration_seconds = time.time() - start_time
        combination.completed_at = datetime.utcnow()
        if db:
            db.commit()


async def run_experiment(
    experiment_id: int,
    db: Session,
    vectorstore_config: Optional[Dict[str, Any]] = None,
) -> None:
    """Run all combinations in an experiment."""
    experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not experiment:
        raise ValueError(f"Experiment {experiment_id} not found")

    # Load dataset
    dataset = db.query(Dataset).filter(Dataset.id == experiment.dataset_id).first()
    if not dataset:
        raise ValueError(f"Dataset {experiment.dataset_id} not found")

    items = db.query(DatasetItem).filter(DatasetItem.dataset_id == dataset.id).all()
    questions = [item.question for item in items]
    ground_truths = [item.ground_truth for item in items]

    # Load source documents
    doc_models = db.query(DocumentModel).filter(
        DocumentModel.id.in_(dataset.document_ids or [])
    ).all()
    filepaths = [doc.filepath for doc in doc_models]
    source_documents = load_documents(filepaths)

    # Get optional metrics from the first combination's config or default
    optional_metrics = None

    experiment.status = "running"
    db.commit()

    # Run each combination
    pending = (
        db.query(ExperimentCombination)
        .filter(
            ExperimentCombination.experiment_id == experiment_id,
            ExperimentCombination.status == "pending",
        )
        .all()
    )

    all_success = True
    was_stopped = False
    for combination in pending:
        # Check if experiment was stopped before running next combination
        db.refresh(experiment)
        if experiment.status == "stopped":
            was_stopped = True
            logger.info(f"Experiment {experiment_id} was stopped by user")
            break

        await run_single_combination(
            combination=combination,
            source_documents=source_documents,
            questions=questions,
            ground_truths=ground_truths,
            vectorstore_type=experiment.vectorstore_type,
            vectorstore_config=vectorstore_config,
            optional_metrics=optional_metrics,
            db=db,
        )
        if combination.status == "failed":
            all_success = False

    if not was_stopped:
        # Check for stuck combinations (still "running" after loop finished)
        stuck = (
            db.query(ExperimentCombination)
            .filter(
                ExperimentCombination.experiment_id == experiment_id,
                ExperimentCombination.status == "running",
            )
            .all()
        )
        for combo in stuck:
            combo.status = "failed"
            combo.error_message = "Combination timed out or got stuck during execution"
            combo.completed_at = datetime.utcnow()
            all_success = False

        experiment.status = "completed" if all_success else "completed_with_errors"
        db.commit()

        # Save winning collection for later querying
        try:
            await _save_winning_collection(
                experiment=experiment,
                source_documents=source_documents,
                db=db,
            )
        except Exception as e:
            logger.warning(f"Failed to save winning collection for experiment {experiment_id}: {e}")


async def _save_winning_collection(
    experiment: Experiment,
    source_documents: list,
    db: Session,
) -> None:
    """Re-index the winning combination's documents into a persistent collection."""
    completed = [
        c for c in experiment.combinations
        if c.status == "completed" and c.overall_score is not None
    ]
    if not completed:
        return

    best = max(completed, key=lambda c: c.overall_score)
    params = best.params

    # Skip if already saved for this experiment
    existing = db.query(SavedCollection).filter(
        SavedCollection.experiment_id == experiment.id
    ).first()
    if existing:
        return

    collection_name = f"saved_{experiment.id}_{best.id}"
    persist_path = os.path.abspath(f"./saved_collections/{collection_name}")
    os.makedirs(persist_path, exist_ok=True)

    # Re-chunk with winning params
    chunks = chunk_documents(
        source_documents,
        params["chunk_size"],
        params["chunk_overlap"],
    )

    # Create embeddings with winning model/dimensions
    embeddings = get_embeddings(
        db,
        model=params["embedding_model"],
        dimensions=params.get("embedding_dimensions"),
    )

    # Index into persistent ChromaDB
    from langchain_community.vectorstores import Chroma
    distance_metric = params.get("distance_metric", "cosine")
    Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        collection_name=collection_name,
        persist_directory=persist_path,
        collection_metadata={"hnsw:space": distance_metric},
    )

    # Calculate size
    total_size = 0
    for dirpath, _, filenames in os.walk(persist_path):
        for f in filenames:
            total_size += os.path.getsize(os.path.join(dirpath, f))

    # Save to DB
    saved = SavedCollection(
        name=f"{experiment.name} — Best",
        experiment_id=experiment.id,
        combination_id=best.id,
        collection_name=collection_name,
        persist_path=persist_path,
        embedding_model=params["embedding_model"],
        embedding_dimensions=params.get("embedding_dimensions"),
        distance_metric=distance_metric,
        chunk_size=params["chunk_size"],
        chunk_overlap=params["chunk_overlap"],
        top_k=params.get("top_k", 5),
        search_type=params.get("search_type", "vector"),
        overall_score=best.overall_score,
        size_bytes=total_size,
    )
    db.add(saved)
    db.commit()
