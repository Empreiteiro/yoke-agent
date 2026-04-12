"""Experiment runner that orchestrates the full grid search execution."""

import asyncio
import logging
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

import os

# Default parallelism level (can be overridden per experiment)
DEFAULT_MAX_WORKERS = 2

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

        # Run RAG or GraphRAG pipeline based on pipeline_type
        pipeline_type = combination.params.get("pipeline_type", "rag")

        if pipeline_type == "graphrag":
            from app.services.graphrag_pipeline import run_graphrag_pipeline
            rag_results = await run_graphrag_pipeline(
                documents=source_documents,
                questions=questions,
                params=combination.params,
                db=db,
                experiment_id=combination.experiment_id,
                combination_id=combination.id,
            )
        else:
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

        # Calculate overall_score from available metrics (resilient to partial results)
        fixed = [
            combination.faithfulness,
            combination.answer_relevancy,
            combination.context_precision,
            combination.context_recall,
        ]
        available = [v for v in fixed if v is not None]
        combination.overall_score = sum(available) / len(available) if available else scores.get("overall_score")
        combination.detailed_results = eval_results.get("detailed_results")
        combination.status = "completed"

        # Aggregate token usage for this combination
        try:
            from app.models.token_usage import TokenUsageLog
            from sqlalchemy import func as sqlfunc
            token_row = db.query(
                sqlfunc.sum(TokenUsageLog.total_tokens).label("tokens"),
                sqlfunc.sum(TokenUsageLog.estimated_cost).label("cost"),
            ).filter(
                TokenUsageLog.combination_id == combination.id,
            ).first()
            combination.total_tokens = token_row.tokens or 0
            combination.total_cost = token_row.cost or 0.0
        except Exception:
            pass

        # Aggregate latency metrics (issue #112) — merge into detailed_results items
        try:
            latencies = [r.get("total_latency_ms") for r in rag_results if r.get("total_latency_ms") is not None]
            retrievals = [r.get("retrieval_ms") for r in rag_results if r.get("retrieval_ms") is not None]
            generations = [r.get("generation_ms") for r in rag_results if r.get("generation_ms") is not None]
            if latencies:
                ordered = sorted(latencies)
                p95_idx = max(0, int(round(0.95 * (len(ordered) - 1))))
                combination.avg_latency_ms = sum(latencies) / len(latencies)
                combination.p95_latency_ms = ordered[p95_idx]
            if retrievals:
                combination.avg_retrieval_ms = sum(retrievals) / len(retrievals)
            if generations:
                combination.avg_generation_ms = sum(generations) / len(generations)

            # Merge per-Q&A latency into detailed_results so the UI can display it
            details = combination.detailed_results
            if isinstance(details, list) and len(details) == len(rag_results):
                merged = []
                for det, rag in zip(details, rag_results):
                    if isinstance(det, dict):
                        det = dict(det)
                        det["retrieval_ms"] = rag.get("retrieval_ms")
                        det["generation_ms"] = rag.get("generation_ms")
                        det["total_latency_ms"] = rag.get("total_latency_ms")
                    merged.append(det)
                combination.detailed_results = merged
        except Exception as e:
            logger.warning(f"Failed to aggregate latency for combination {combination.id}: {e}")

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


async def _run_combination_with_session(
    combination_id: int,
    source_documents: list,
    questions: list[str],
    ground_truths: list[str],
    vectorstore_type: str,
    vectorstore_config: Optional[Dict[str, Any]],
    optional_metrics: Optional[list[str]],
    experiment_id: int,
    semaphore: asyncio.Semaphore,
) -> bool:
    """Run a single combination with its own DB session (for parallel execution)."""
    from app.core.database import SessionLocal

    async with semaphore:
        db = SessionLocal()
        try:
            # Check if experiment was stopped
            experiment = db.query(Experiment).filter(Experiment.id == experiment_id).first()
            if experiment and experiment.status == "stopped":
                return True  # signal stopped

            combination = db.query(ExperimentCombination).filter(
                ExperimentCombination.id == combination_id
            ).first()
            if not combination or combination.status != "pending":
                return False

            await run_single_combination(
                combination=combination,
                source_documents=source_documents,
                questions=questions,
                ground_truths=ground_truths,
                vectorstore_type=vectorstore_type,
                vectorstore_config=vectorstore_config,
                optional_metrics=optional_metrics,
                db=db,
            )
            return combination.status == "failed"
        except Exception as e:
            logger.error(f"Parallel combination {combination_id} error: {e}")
            return True
        finally:
            db.close()


async def run_experiment(
    experiment_id: int,
    db: Session,
    vectorstore_config: Optional[Dict[str, Any]] = None,
    max_workers: int = DEFAULT_MAX_WORKERS,
) -> None:
    """Run all combinations in an experiment, with parallel execution."""
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

    # Read optional metrics from the first combination's params (shared across all combos)
    first_combo = (
        db.query(ExperimentCombination)
        .filter(ExperimentCombination.experiment_id == experiment_id)
        .first()
    )
    optional_metrics = first_combo.params.get("optional_metrics") if first_combo else None

    experiment.status = "running"
    db.commit()

    # Get pending combination IDs
    pending = (
        db.query(ExperimentCombination)
        .filter(
            ExperimentCombination.experiment_id == experiment_id,
            ExperimentCombination.status == "pending",
        )
        .all()
    )
    pending_ids = [c.id for c in pending]

    all_success = True
    was_stopped = False

    if max_workers <= 1:
        # Sequential execution (original behavior)
        for combination in pending:
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
    else:
        # Parallel execution with semaphore
        semaphore = asyncio.Semaphore(max_workers)
        logger.info(f"Running {len(pending_ids)} combinations with max_workers={max_workers}")

        tasks = [
            _run_combination_with_session(
                combination_id=cid,
                source_documents=source_documents,
                questions=questions,
                ground_truths=ground_truths,
                vectorstore_type=experiment.vectorstore_type,
                vectorstore_config=vectorstore_config,
                optional_metrics=optional_metrics,
                experiment_id=experiment_id,
                semaphore=semaphore,
            )
            for cid in pending_ids
        ]

        results = await asyncio.gather(*tasks, return_exceptions=True)
        for r in results:
            if isinstance(r, Exception):
                all_success = False
            elif r:
                all_success = False

        # Refresh experiment status
        db.refresh(experiment)
        was_stopped = experiment.status == "stopped"

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
