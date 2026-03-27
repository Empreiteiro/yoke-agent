"""Experiment runner that orchestrates the full grid search execution."""

import logging
import time
import traceback
from datetime import datetime
from typing import Optional, Dict, Any

from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)

from app.models.document import Document as DocumentModel
from app.models.dataset import Dataset, DatasetItem
from app.models.experiment import Experiment, ExperimentCombination
from app.services.document_loader import load_documents
from app.services.rag_pipeline import run_rag_pipeline
from app.services.ragas_evaluator import evaluate_rag_results


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
