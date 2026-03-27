"""Experiment management API routes with grid search and execution."""

import asyncio
import itertools
import uuid
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
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


def _run_experiment_sync(experiment_id: int):
    """Synchronous wrapper for background experiment execution."""
    db = SessionLocal()
    try:
        asyncio.run(run_experiment_service(experiment_id, db))
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
    # Enrich with dataset names
    result = []
    for exp in experiments:
        dataset = db.query(Dataset).filter(Dataset.id == exp.dataset_id).first()
        exp_dict = ExperimentResponse.model_validate(exp).model_dump()
        exp_dict["dataset_name"] = dataset.name if dataset else None
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


@router.post("/{experiment_id}/configure-grid")
def configure_grid(
    experiment_id: int, config: GridSearchConfig, db: Session = Depends(get_db)
):
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

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
                "embedding_dimensions": dim,
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
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db),
):
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

    background_tasks.add_task(_run_experiment_sync, experiment_id)
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
