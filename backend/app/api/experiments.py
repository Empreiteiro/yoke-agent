"""Experiment management API routes with grid search and execution."""

import asyncio
import csv
import io
import itertools
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.models.experiment import Experiment, ExperimentCombination
from app.models.dataset import Dataset
from app.schemas.provider import EMBEDDING_DIMENSIONS
from app.schemas.experiment import (
    ExperimentCreate,
    ExperimentResponse,
    GridSearchConfig,
    ExperimentReport,
)
from app.services.experiment_runner import run_experiment as run_experiment_service

router = APIRouter()


def _run_experiment_sync(experiment_id: int, max_workers: int = 2):
    """Synchronous wrapper for background experiment execution."""
    db = SessionLocal()
    try:
        asyncio.run(run_experiment_service(experiment_id, db, max_workers=max_workers))
    finally:
        db.close()


@router.post("/", response_model=ExperimentResponse)
def create_experiment(data: ExperimentCreate, db: Session = Depends(get_db)):
    experiment = Experiment(
        name=data.name or f"experiment-{uuid.uuid4().hex[:8]}",
        description=data.description,
        dataset_id=data.dataset_id,
        vectorstore_type=data.vectorstore_type,
    )
    db.add(experiment)
    db.commit()
    db.refresh(experiment)
    return experiment


@router.get("/", response_model=list[ExperimentResponse])
def list_experiments(db: Session = Depends(get_db)):
    experiments = db.query(Experiment).order_by(Experiment.created_at.desc()).all()
    # Enrich with dataset names, filter out internal estimate experiments
    result = []
    for exp in experiments:
        if exp.name and exp.name.startswith("estimate-"):
            continue
        dataset = db.query(Dataset).filter(Dataset.id == exp.dataset_id).first()
        exp_dict = ExperimentResponse.model_validate(exp).model_dump()
        exp_dict["dataset_name"] = dataset.name if dataset else None
        exp_dict["dataset_questions"] = len(dataset.items) if dataset else 0
        result.append(exp_dict)
    return result


@router.get("/{experiment_id}", response_model=ExperimentResponse)
def get_experiment(experiment_id: int, db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    return exp


@router.delete("/{experiment_id}")
def delete_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """Delete an experiment and all its combinations."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status == "running":
        raise HTTPException(status_code=400, detail="Cannot delete a running experiment. Stop it first.")
    db.query(ExperimentCombination).filter(
        ExperimentCombination.experiment_id == experiment_id
    ).delete()
    db.delete(exp)
    db.commit()
    return {"detail": "Experiment deleted", "experiment_id": experiment_id}


@router.post("/{experiment_id}/propose-grid")
async def propose_grid_search(experiment_id: int, db: Session = Depends(get_db)):
    """Use LLM to propose a grid search configuration based on document analysis."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    exp.status = "proposing"
    db.commit()

    return {
        "detail": "Grid search proposal generated",
        "experiment_id": experiment_id,
        "default_config": {
            "chunk_sizes": [512, 1024],
            "chunk_overlaps": [10, 20],
            "embedding_models": ["text-embedding-3-small"],
            "top_k_values": [3, 5],
            "search_types": ["vector"],
        },
    }


@router.post("/{experiment_id}/estimate-cost")
def estimate_cost(
    experiment_id: int, config: GridSearchConfig, db: Session = Depends(get_db)
):
    """Estimate token usage and cost for a grid search configuration."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    dataset = db.query(Dataset).filter(Dataset.id == exp.dataset_id).first()
    num_questions = len(dataset.items) if dataset else 0

    # Estimate document size
    from app.models.document import Document as DocModel
    doc_models = db.query(DocModel).filter(DocModel.id.in_(dataset.document_ids or [])).all() if dataset else []
    import os
    total_doc_chars = sum(os.path.getsize(d.filepath) for d in doc_models if os.path.exists(d.filepath))

    # Count total combinations
    from app.schemas.provider import EMBEDDING_DIMENSIONS
    num_base = (
        len(config.chunk_sizes) * len(config.chunk_overlaps) *
        len(config.embedding_models) * len(config.top_k_values) *
        len(config.search_types) * len(config.distance_metrics) *
        len(config.chunking_strategies) if hasattr(config, "chunking_strategies") else
        len(config.chunk_sizes) * len(config.chunk_overlaps) *
        len(config.embedding_models) * len(config.top_k_values) *
        len(config.search_types) * len(config.distance_metrics)
    )
    # Account for dimension expansion
    dim_multiplier = 1
    if config.embedding_dimensions:
        total_dim_combos = 0
        for model in config.embedding_models:
            info = EMBEDDING_DIMENSIONS.get(model)
            if info:
                valid = [d for d in config.embedding_dimensions if d in info["supported"]]
                total_dim_combos += len(valid) or 1
            else:
                total_dim_combos += 1
        dim_multiplier = total_dim_combos / max(len(config.embedding_models), 1)
    total_combos = int(num_base * dim_multiplier)

    # Estimate tokens per combination
    avg_chunk_size = sum(config.chunk_sizes) / max(len(config.chunk_sizes), 1)
    est_chunks = int(total_doc_chars / max(avg_chunk_size, 1))

    # Embedding tokens: all chunks embedded once per combo
    embedding_tokens_per_combo = est_chunks * int(avg_chunk_size)
    # LLM tokens per combo: each question gets ~context + answer
    avg_top_k = sum(config.top_k_values) / max(len(config.top_k_values), 1)
    llm_input_per_question = int(avg_top_k * avg_chunk_size + 200)  # context + prompt overhead
    llm_output_per_question = 200  # estimated answer tokens
    llm_tokens_per_combo = num_questions * (llm_input_per_question + llm_output_per_question)
    # RAGAS evaluation tokens (LLM calls for metric computation)
    ragas_tokens_per_combo = num_questions * 2000  # rough estimate

    total_embedding = embedding_tokens_per_combo * total_combos
    total_llm = (llm_tokens_per_combo + ragas_tokens_per_combo) * total_combos

    # Cost estimates (approximate pricing per 1M tokens)
    EMBEDDING_COST_PER_M = 0.02  # text-embedding-3-small
    LLM_COST_PER_M = 0.50  # gpt-4o-mini average

    est_embedding_cost = (total_embedding / 1_000_000) * EMBEDDING_COST_PER_M
    est_llm_cost = (total_llm / 1_000_000) * LLM_COST_PER_M
    est_total_cost = est_embedding_cost + est_llm_cost

    return {
        "total_combinations": total_combos,
        "num_questions": num_questions,
        "estimated_chunks": est_chunks,
        "estimated_embedding_tokens": total_embedding,
        "estimated_llm_tokens": total_llm,
        "estimated_total_tokens": total_embedding + total_llm,
        "estimated_cost_usd": round(est_total_cost, 4),
        "breakdown": {
            "embedding_cost": round(est_embedding_cost, 4),
            "llm_cost": round(est_llm_cost, 4),
        },
    }


@router.post("/{experiment_id}/configure-grid")
def configure_grid(
    experiment_id: int, config: GridSearchConfig, db: Session = Depends(get_db)
):
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    # Rename temporary estimate experiments to a proper name
    if exp.name and exp.name.startswith("estimate-"):
        exp.name = f"experiment-{uuid.uuid4().hex[:8]}"

    # Clear existing combinations
    db.query(ExperimentCombination).filter(
        ExperimentCombination.experiment_id == experiment_id
    ).delete()

    # Generate base combinations (without dimensions, which are per-model)
    base_combos = list(
        itertools.product(
            config.chunk_sizes,
            config.chunk_overlaps,
            config.embedding_models,
            config.top_k_values,
            config.search_types,
            config.distance_metrics,
            config.chunking_strategies,
        )
    )

    # Expand with embedding dimensions (respecting per-model limits)
    combo_count = 0
    for combo in base_combos:
        embedding_model = combo[2]
        model_info = EMBEDDING_DIMENSIONS.get(embedding_model)
        default_dim = model_info["default"] if model_info else None

        if config.embedding_dimensions:
            # Filter to dimensions valid for this model
            supported = model_info["supported"] if model_info else []
            dims_for_model = [d for d in config.embedding_dimensions if d in supported]
            if not dims_for_model:
                dims_for_model = [default_dim]
        else:
            dims_for_model = [default_dim]

        for dim in dims_for_model:
            params = {
                "chunk_size": combo[0],
                "chunk_overlap": combo[1],
                "embedding_model": embedding_model,
                "top_k": combo[3],
                "search_type": combo[4],
                "distance_metric": combo[5],
                "chunking_strategy": combo[6],
                "embedding_dimensions": dim,
                "answer_language": config.answer_language,
            }
            db_combo = ExperimentCombination(
                experiment_id=experiment_id,
                params=params,
            )
            db.add(db_combo)
            combo_count += 1

    exp.status = "configured"
    db.commit()
    db.refresh(exp)
    return {
        "detail": f"Created {combo_count} combinations",
        "experiment_id": experiment_id,
        "total_combinations": combo_count,
    }


@router.post("/{experiment_id}/run")
async def run_experiment_endpoint(
    experiment_id: int,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    from app.core.config import settings

    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status not in ("configured", "completed", "failed"):
        raise HTTPException(
            status_code=400,
            detail=f"Experiment must be configured before running. Current status: {exp.status}",
        )

    exp.status = "running"
    db.commit()

    max_workers = settings.experiment_max_workers
    background_tasks.add_task(_run_experiment_sync, experiment_id, max_workers)
    return {"detail": "Experiment execution started", "experiment_id": experiment_id}


@router.post("/{experiment_id}/stop")
def stop_experiment(experiment_id: int, db: Session = Depends(get_db)):
    """Stop a running experiment. Marks pending combinations as stopped."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status != "running":
        raise HTTPException(
            status_code=400,
            detail=f"Experiment is not running. Current status: {exp.status}",
        )

    exp.status = "stopped"
    # Mark all pending combinations as stopped
    db.query(ExperimentCombination).filter(
        ExperimentCombination.experiment_id == experiment_id,
        ExperimentCombination.status == "pending",
    ).update({"status": "stopped"})
    db.commit()
    return {"detail": "Experiment stopped", "experiment_id": experiment_id}


@router.post("/{experiment_id}/resume")
async def resume_experiment(
    experiment_id: int,
    retry_failed: bool = False,
    background_tasks: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Resume a stopped or failed experiment. Optionally retry failed combinations."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")
    if exp.status not in ("stopped", "failed", "completed", "completed_with_errors"):
        raise HTTPException(
            status_code=400,
            detail=f"Experiment cannot be resumed. Current status: {exp.status}",
        )

    # Reset stopped and stuck (running) combinations back to pending
    db.query(ExperimentCombination).filter(
        ExperimentCombination.experiment_id == experiment_id,
        ExperimentCombination.status.in_(["stopped", "running"]),
    ).update({"status": "pending"}, synchronize_session="fetch")

    # Optionally retry failed combinations
    if retry_failed:
        db.query(ExperimentCombination).filter(
            ExperimentCombination.experiment_id == experiment_id,
            ExperimentCombination.status == "failed",
        ).update({"status": "pending", "error_message": None})

    remaining = db.query(ExperimentCombination).filter(
        ExperimentCombination.experiment_id == experiment_id,
        ExperimentCombination.status == "pending",
    ).count()

    if remaining == 0:
        raise HTTPException(
            status_code=400,
            detail="No combinations to resume. All are already completed.",
        )

    exp.status = "running"
    db.commit()

    background_tasks.add_task(_run_experiment_sync, experiment_id)
    return {
        "detail": f"Experiment resumed with {remaining} pending combinations",
        "experiment_id": experiment_id,
        "remaining": remaining,
    }


@router.get("/{experiment_id}/report", response_model=ExperimentReport)
def get_experiment_report(experiment_id: int, db: Session = Depends(get_db)):
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    best = None
    if exp.combinations:
        completed = [
            c for c in exp.combinations
            if c.status == "completed" and c.overall_score is not None
        ]
        if completed:
            best = max(completed, key=lambda c: c.overall_score)

    total = len(exp.combinations)
    completed_count = len([c for c in exp.combinations if c.status == "completed"])
    failed_count = len([c for c in exp.combinations if c.status == "failed"])

    return ExperimentReport(
        experiment=exp,
        best_combination=best,
        summary={
            "total_combinations": total,
            "completed": completed_count,
            "failed": failed_count,
            "pending": total - completed_count - failed_count,
        },
    )


@router.get("/{experiment_id}/export")
def export_experiment(experiment_id: int, format: str = "csv", db: Session = Depends(get_db)):
    """Export experiment results as CSV. One row per combination."""
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    completed = [c for c in exp.combinations if c.status == "completed"]
    completed.sort(key=lambda c: c.overall_score or 0, reverse=True)

    headers = [
        "rank", "chunk_size", "chunk_overlap", "chunking_strategy", "embedding_model",
        "embedding_dimensions", "top_k", "search_type", "distance_metric",
        "faithfulness", "answer_relevancy", "context_precision", "context_recall",
        "answer_similarity", "answer_correctness", "overall_score", "duration_seconds",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)

    for i, c in enumerate(completed):
        p = c.params or {}
        writer.writerow([
            i + 1,
            p.get("chunk_size", ""),
            p.get("chunk_overlap", ""),
            p.get("chunking_strategy", "recursive"),
            p.get("embedding_model", ""),
            p.get("embedding_dimensions", ""),
            p.get("top_k", ""),
            p.get("search_type", ""),
            p.get("distance_metric", "cosine"),
            c.faithfulness,
            c.answer_relevancy,
            c.context_precision,
            c.context_recall,
            c.answer_similarity,
            c.answer_correctness,
            c.overall_score,
            c.duration_seconds,
        ])

    output.seek(0)
    filename = f"{exp.name or 'experiment'}-results.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
