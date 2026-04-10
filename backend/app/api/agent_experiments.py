"""API endpoints for Agent Experiments, Interaction Datasets, Simulations, and Results."""
import itertools
import logging
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from sqlalchemy import func as sqlfunc

from app.core.database import get_db
from app.models.agent import (
    AgentConfig, PromptVariant, Scenario, Persona,
    InteractionDataset, InteractionDatasetItem,
    AgentExperiment, AgentExperimentCombination,
    SimulationRun, SimulationTranscript, SimulationMetrics,
)
from app.schemas.agent import (
    InteractionDatasetCreate, InteractionDatasetResponse,
    InteractionDatasetItemCreate, InteractionDatasetItemResponse,
    GenerateDatasetRequest,
    AgentExperimentCreate, AgentExperimentResponse, AgentCombinationResponse,
    SimulationTranscriptResponse, SimulationMetricsResponse,
)

logger = logging.getLogger(__name__)
router = APIRouter()


# ══════════════════════════════════════════════════════════════════════
#  INTERACTION DATASETS
# ══════════════════════════════════════════════════════════════════════

@router.get("/datasets", response_model=list[InteractionDatasetResponse])
def list_datasets(db: Session = Depends(get_db)):
    datasets = db.query(InteractionDataset).order_by(InteractionDataset.updated_at.desc()).all()
    return datasets


@router.post("/datasets", response_model=InteractionDatasetResponse, status_code=201)
def create_dataset(body: InteractionDatasetCreate, db: Session = Depends(get_db)):
    ds = InteractionDataset(**body.model_dump())
    db.add(ds)
    db.commit()
    db.refresh(ds)
    return ds


@router.get("/datasets/{dataset_id}", response_model=InteractionDatasetResponse)
def get_dataset(dataset_id: int, db: Session = Depends(get_db)):
    ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    return ds


@router.delete("/datasets/{dataset_id}", status_code=204)
def delete_dataset(dataset_id: int, db: Session = Depends(get_db)):
    ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    db.delete(ds)
    db.commit()


@router.post("/datasets/{dataset_id}/duplicate", response_model=InteractionDatasetResponse)
def duplicate_dataset(dataset_id: int, db: Session = Depends(get_db)):
    ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    new_ds = InteractionDataset(
        name=f"{ds.name} (copy)",
        description=ds.description,
        agent_config_id=ds.agent_config_id,
        interaction_mode=ds.interaction_mode,
        status="ready" if ds.status == "ready" else "draft",
    )
    db.add(new_ds)
    db.flush()
    for item in ds.items:
        new_item = InteractionDatasetItem(
            dataset_id=new_ds.id,
            scenario_id=item.scenario_id,
            persona_id=item.persona_id,
            interaction_mode=item.interaction_mode,
            objective=item.objective,
            expected_output=item.expected_output,
            conversation_history=item.conversation_history,
            metadata_=item.metadata_,
            is_manual=item.is_manual,
        )
        db.add(new_item)
    new_ds.total_items = len(ds.items)
    db.commit()
    db.refresh(new_ds)
    return new_ds


# Dataset items
@router.get("/datasets/{dataset_id}/items", response_model=list[InteractionDatasetItemResponse])
def list_dataset_items(dataset_id: int, db: Session = Depends(get_db)):
    items = db.query(InteractionDatasetItem).filter(
        InteractionDatasetItem.dataset_id == dataset_id
    ).order_by(InteractionDatasetItem.id).all()
    result = []
    for item in items:
        result.append(InteractionDatasetItemResponse(
            id=item.id, dataset_id=item.dataset_id,
            scenario_id=item.scenario_id, persona_id=item.persona_id,
            interaction_mode=item.interaction_mode,
            objective=item.objective,
            expected_output=item.expected_output,
            conversation_history=item.conversation_history,
            metadata=item.metadata_ or {},
            is_manual=item.is_manual,
            created_at=item.created_at,
        ))
    return result


@router.post("/datasets/{dataset_id}/items", response_model=InteractionDatasetItemResponse, status_code=201)
def add_dataset_item(dataset_id: int, body: InteractionDatasetItemCreate, db: Session = Depends(get_db)):
    ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    item = InteractionDatasetItem(
        dataset_id=dataset_id,
        scenario_id=body.scenario_id,
        persona_id=body.persona_id,
        interaction_mode=body.interaction_mode,
        objective=body.objective,
        generated_input=body.generated_input,
        expected_output=body.expected_output,
        conversation_history=body.conversation_history,
        metadata_=body.metadata,
        is_manual=body.is_manual,
    )
    db.add(item)
    ds.total_items = (ds.total_items or 0) + 1
    db.commit()
    db.refresh(item)
    return InteractionDatasetItemResponse(
        id=item.id, dataset_id=item.dataset_id,
        scenario_id=item.scenario_id, persona_id=item.persona_id,
        interaction_mode=item.interaction_mode,
        objective=item.objective,
        expected_output=item.expected_output,
        conversation_history=item.conversation_history,
        metadata=item.metadata_ or {},
        is_manual=item.is_manual,
        created_at=item.created_at,
    )


@router.delete("/datasets/{dataset_id}/items/{item_id}", status_code=204)
def delete_dataset_item(dataset_id: int, item_id: int, db: Session = Depends(get_db)):
    item = db.query(InteractionDatasetItem).filter(
        InteractionDatasetItem.id == item_id,
        InteractionDatasetItem.dataset_id == dataset_id,
    ).first()
    if not item:
        raise HTTPException(404, "Item not found")
    ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
    db.delete(item)
    if ds:
        ds.total_items = max((ds.total_items or 1) - 1, 0)
    db.commit()


@router.post("/datasets/{dataset_id}/import", response_model=InteractionDatasetResponse)
def import_dataset_items(dataset_id: int, body: list[InteractionDatasetItemCreate], db: Session = Depends(get_db)):
    ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    for b in body:
        item = InteractionDatasetItem(
            dataset_id=dataset_id,
            scenario_id=b.scenario_id,
            persona_id=b.persona_id,
            interaction_mode=b.interaction_mode,
            objective=b.objective,
            expected_output=b.expected_output,
            conversation_history=b.conversation_history,
            metadata_=b.metadata,
            is_manual=b.is_manual,
        )
        db.add(item)
    ds.total_items = (ds.total_items or 0) + len(body)
    if ds.status == "draft":
        ds.status = "ready"
    db.commit()
    db.refresh(ds)
    return ds


@router.get("/datasets/{dataset_id}/export")
def export_dataset(dataset_id: int, db: Session = Depends(get_db)):
    ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    items = db.query(InteractionDatasetItem).filter(InteractionDatasetItem.dataset_id == dataset_id).all()
    return {
        "name": ds.name,
        "description": ds.description,
        "interaction_mode": ds.interaction_mode,
        "items": [
            {
                "interaction_mode": i.interaction_mode,
                "objective": i.objective,
                "generated_input": i.generated_input,
                "expected_output": i.expected_output,
                "conversation_history": i.conversation_history,
                "metadata": i.metadata_,
            }
            for i in items
        ],
    }


@router.post("/datasets/generate", response_model=InteractionDatasetResponse)
async def generate_dataset(body: GenerateDatasetRequest, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Generate an interaction dataset from scenarios + personas using LLM."""
    config = db.query(AgentConfig).filter(AgentConfig.id == body.agent_config_id).first()
    if not config:
        raise HTTPException(404, "Agent config not found")
    ds = InteractionDataset(
        name=body.name,
        description=body.description,
        agent_config_id=body.agent_config_id,
        interaction_mode=body.interaction_mode,
        status="generating",
    )
    db.add(ds)
    db.commit()
    db.refresh(ds)
    bg.add_task(_generate_dataset_bg, ds.id, body)
    return ds


async def _generate_dataset_bg(dataset_id: int, body: GenerateDatasetRequest):
    """Background task: generate interaction dataset items."""
    from app.core.database import SessionLocal
    db = SessionLocal()
    try:
        ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
        config = db.query(AgentConfig).filter(AgentConfig.id == body.agent_config_id).first()
        # Gather scenarios
        sq = db.query(Scenario).filter(Scenario.agent_config_id == body.agent_config_id)
        if body.scenario_ids:
            sq = sq.filter(Scenario.id.in_(body.scenario_ids))
        scenarios = sq.all()
        # Gather personas
        pq = db.query(Persona).filter(Persona.agent_config_id == body.agent_config_id)
        if body.persona_ids:
            pq = pq.filter(Persona.id.in_(body.persona_ids))
        personas = pq.all()

        count = 0
        for scenario in scenarios:
            for persona in personas:
                item = InteractionDatasetItem(
                    dataset_id=dataset_id,
                    scenario_id=scenario.id,
                    persona_id=persona.id,
                    interaction_mode=body.interaction_mode,
                    objective=scenario.objective,
                    expected_output=scenario.expected_output,
                    metadata_={
                        "scenario_type": scenario.scenario_type,
                        "scenario_name": scenario.name,
                        "persona_name": persona.name,
                        "persona_group": persona.group_name,
                        "tags": scenario.tags or [],
                    },
                )
                db.add(item)
                count += 1
        ds.total_items = count
        ds.status = "ready"
        db.commit()
    except Exception as e:
        logger.exception("Dataset generation failed")
        ds = db.query(InteractionDataset).filter(InteractionDataset.id == dataset_id).first()
        if ds:
            ds.status = "error"
            ds.error_message = str(e)
            db.commit()
    finally:
        db.close()


# ══════════════════════════════════════════════════════════════════════
#  AGENT EXPERIMENTS
# ══════════════════════════════════════════════════════════════════════

@router.get("/experiments", response_model=list[AgentExperimentResponse])
def list_experiments(db: Session = Depends(get_db)):
    exps = db.query(AgentExperiment).order_by(AgentExperiment.updated_at.desc()).all()
    result = []
    for e in exps:
        result.append(AgentExperimentResponse(
            id=e.id, name=e.name, description=e.description,
            agent_config_id=e.agent_config_id, dataset_id=e.dataset_id,
            grid_config=e.grid_config, status=e.status,
            created_at=e.created_at, updated_at=e.updated_at,
            combination_count=len(e.combinations),
        ))
    return result


@router.post("/experiments", response_model=AgentExperimentResponse, status_code=201)
def create_experiment(body: AgentExperimentCreate, db: Session = Depends(get_db)):
    config = db.query(AgentConfig).filter(AgentConfig.id == body.agent_config_id).first()
    if not config:
        raise HTTPException(404, "Agent config not found")

    exp = AgentExperiment(
        name=body.name,
        description=body.description,
        agent_config_id=body.agent_config_id,
        dataset_id=body.dataset_id,
        grid_config=body.grid_config.model_dump(),
        status="configured",
    )
    db.add(exp)
    db.flush()

    # Generate combinations: Cartesian product
    gc = body.grid_config
    combos = list(itertools.product(
        gc.prompt_variant_ids,
        gc.llm_models,
        gc.temperatures,
        gc.max_turns,
    ))

    for variant_id, model, temp, max_turns in combos:
        combo = AgentExperimentCombination(
            experiment_id=exp.id,
            params={
                "prompt_variant_id": variant_id,
                "model": model,
                "temperature": temp,
                "max_turns": max_turns,
                "persona_group_names": gc.persona_group_names,
                "scenario_types": gc.scenario_types,
                "interaction_count_override": gc.interaction_count_override,
            },
        )
        db.add(combo)

    db.commit()
    db.refresh(exp)
    return AgentExperimentResponse(
        id=exp.id, name=exp.name, description=exp.description,
        agent_config_id=exp.agent_config_id, dataset_id=exp.dataset_id,
        grid_config=exp.grid_config, status=exp.status,
        created_at=exp.created_at, updated_at=exp.updated_at,
        combination_count=len(exp.combinations),
    )


@router.get("/experiments/{exp_id}", response_model=AgentExperimentResponse)
def get_experiment(exp_id: int, db: Session = Depends(get_db)):
    e = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not e:
        raise HTTPException(404, "Experiment not found")
    return AgentExperimentResponse(
        id=e.id, name=e.name, description=e.description,
        agent_config_id=e.agent_config_id, dataset_id=e.dataset_id,
        grid_config=e.grid_config, status=e.status,
        created_at=e.created_at, updated_at=e.updated_at,
        combination_count=len(e.combinations),
    )


@router.delete("/experiments/{exp_id}", status_code=204)
def delete_experiment(exp_id: int, db: Session = Depends(get_db)):
    e = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not e:
        raise HTTPException(404, "Experiment not found")
    db.delete(e)
    db.commit()


@router.get("/experiments/{exp_id}/combinations", response_model=list[AgentCombinationResponse])
def list_combinations(exp_id: int, db: Session = Depends(get_db)):
    return db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id
    ).order_by(AgentExperimentCombination.id).all()


@router.post("/experiments/{exp_id}/run")
async def run_experiment(exp_id: int, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Start running all experiment combinations."""
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")
    if exp.status == "running":
        raise HTTPException(400, "Experiment is already running")

    exp.status = "running"
    run = SimulationRun(experiment_id=exp.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    bg.add_task(_run_experiment_sync, exp.id, run.id)
    return {"status": "started", "experiment_id": exp.id, "run_id": run.id}


def _run_experiment_sync(experiment_id: int, run_id: int):
    """Synchronous wrapper — runs in a background thread with its own event loop.

    FastAPI BackgroundTasks runs sync functions in a thread pool, which avoids
    conflicts with the uvicorn event loop. The async simulation engine gets its
    own clean event loop via asyncio.run().
    """
    import asyncio
    asyncio.run(_run_experiment_async(experiment_id, run_id))


async def _run_experiment_async(experiment_id: int, run_id: int):
    """Actual async execution logic."""
    from app.core.database import SessionLocal
    from app.services.agent_simulation_engine import run_simulation

    db = SessionLocal()
    try:
        exp = db.query(AgentExperiment).filter(AgentExperiment.id == experiment_id).first()
        run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        combos = db.query(AgentExperimentCombination).filter(
            AgentExperimentCombination.experiment_id == experiment_id,
            AgentExperimentCombination.status.in_(["pending", "failed"]),
        ).all()

        total = 0
        completed = 0
        failed = 0

        for combo in combos:
            combo.status = "running"
            db.commit()
            try:
                await run_simulation(db, exp, combo)
                combo.status = "completed"
                completed += 1
            except Exception as e:
                logger.exception(f"Combination {combo.id} failed")
                combo.status = "failed"
                combo.error_message = str(e)
                failed += 1
            total += 1
            db.commit()

        run.total_simulations = total
        run.completed_simulations = completed
        run.failed_simulations = failed
        run.status = "completed"
        exp.status = "evaluating"
        db.commit()

        # Auto-evaluate as soon as simulations finish — the user no longer
        # has to click "Evaluate All Combinations". Any failure here is
        # logged but doesn't mark the experiment as failed (the simulation
        # transcripts are still valid and can be re-scored manually later).
        try:
            from app.services.agent_evaluator import evaluate_experiment
            await evaluate_experiment(db, experiment_id)
            logger.info(f"Auto-evaluation finished for experiment {experiment_id}")
        except Exception:
            logger.exception(f"Auto-evaluation failed for experiment {experiment_id}")

        exp = db.query(AgentExperiment).filter(AgentExperiment.id == experiment_id).first()
        if exp:
            exp.status = "completed"
            db.commit()
    except Exception as e:
        logger.exception("Experiment run failed")
        exp = db.query(AgentExperiment).filter(AgentExperiment.id == experiment_id).first()
        if exp:
            exp.status = "failed"
        run = db.query(SimulationRun).filter(SimulationRun.id == run_id).first()
        if run:
            run.status = "failed"
        db.commit()
    finally:
        db.close()


@router.post("/experiments/{exp_id}/stop")
def stop_experiment(exp_id: int, db: Session = Depends(get_db)):
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")
    exp.status = "stopped"
    # Stop pending and running combinations
    db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id,
        AgentExperimentCombination.status.in_(["pending", "running"]),
    ).update({"status": "stopped"}, synchronize_session="fetch")
    db.commit()
    return {"status": "stopped"}


@router.post("/experiments/{exp_id}/resume")
async def resume_experiment(
    exp_id: int,
    retry_failed: bool = False,
    bg: BackgroundTasks = None,
    db: Session = Depends(get_db),
):
    """Resume a stopped/failed experiment. Optionally retry failed combinations."""
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")
    if exp.status not in ("stopped", "failed", "completed"):
        raise HTTPException(400, f"Cannot resume experiment with status: {exp.status}")

    # Reset stopped and stuck (running) combinations back to pending
    db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id,
        AgentExperimentCombination.status.in_(["stopped", "running"]),
    ).update({"status": "pending", "error_message": None}, synchronize_session="fetch")

    # Optionally retry failed combinations
    if retry_failed:
        db.query(AgentExperimentCombination).filter(
            AgentExperimentCombination.experiment_id == exp_id,
            AgentExperimentCombination.status == "failed",
        ).update({
            "status": "pending",
            "error_message": None,
            "total_simulations": 0,
            "completed_simulations": 0,
            "failed_simulations": 0,
        }, synchronize_session="fetch")

    remaining = db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id,
        AgentExperimentCombination.status == "pending",
    ).count()

    if remaining == 0:
        raise HTTPException(400, "No combinations to resume. All are already completed.")

    exp.status = "running"
    run = SimulationRun(experiment_id=exp.id, status="running")
    db.add(run)
    db.commit()
    db.refresh(run)

    bg.add_task(_run_experiment_sync, exp.id, run.id)
    return {
        "status": "resumed",
        "experiment_id": exp.id,
        "remaining": remaining,
        "retry_failed": retry_failed,
    }


@router.get("/experiments/{exp_id}/status")
def get_experiment_status(exp_id: int, db: Session = Depends(get_db)):
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")
    combos = db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id
    ).all()
    return {
        "experiment_id": exp.id,
        "status": exp.status,
        "total_combinations": len(combos),
        "completed": sum(1 for c in combos if c.status == "completed"),
        "failed": sum(1 for c in combos if c.status == "failed"),
        "running": sum(1 for c in combos if c.status == "running"),
        "pending": sum(1 for c in combos if c.status == "pending"),
    }


# ══════════════════════════════════════════════════════════════════════
#  TRANSCRIPTS & METRICS
# ══════════════════════════════════════════════════════════════════════

@router.get("/experiments/{exp_id}/transcripts", response_model=list[SimulationTranscriptResponse])
def list_transcripts(
    exp_id: int,
    combination_id: int | None = None,
    scenario_type: str | None = None,
    db: Session = Depends(get_db),
):
    q = db.query(SimulationTranscript).join(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id
    )
    if combination_id:
        q = q.filter(SimulationTranscript.combination_id == combination_id)
    return q.order_by(SimulationTranscript.id).limit(500).all()


@router.get("/transcripts/{transcript_id}", response_model=SimulationTranscriptResponse)
def get_transcript(transcript_id: int, db: Session = Depends(get_db)):
    t = db.query(SimulationTranscript).filter(SimulationTranscript.id == transcript_id).first()
    if not t:
        raise HTTPException(404, "Transcript not found")
    return t


@router.get("/transcripts/{transcript_id}/metrics", response_model=SimulationMetricsResponse)
def get_transcript_metrics(transcript_id: int, db: Session = Depends(get_db)):
    m = db.query(SimulationMetrics).filter(SimulationMetrics.transcript_id == transcript_id).first()
    if not m:
        raise HTTPException(404, "Metrics not found for this transcript")
    return m


@router.get("/experiments/{exp_id}/results")
def get_experiment_results(exp_id: int, db: Session = Depends(get_db)):
    """Get aggregated results for all combinations."""
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")
    combos = db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id
    ).order_by(AgentExperimentCombination.overall_score.desc().nullslast()).all()
    return {
        "experiment": {
            "id": exp.id,
            "name": exp.name,
            "status": exp.status,
            "agent_config_id": exp.agent_config_id,
        },
        "combinations": [
            {
                "id": c.id,
                "params": c.params,
                "status": c.status,
                "overall_score": c.overall_score,
                "aggregated_metrics": c.aggregated_metrics,
                "metrics_by_scenario_type": c.metrics_by_scenario_type,
                "metrics_by_persona_group": c.metrics_by_persona_group,
                "total_simulations": c.total_simulations,
                "completed_simulations": c.completed_simulations,
                "total_tokens": c.total_tokens,
                "total_cost": c.total_cost,
                "duration_seconds": c.duration_seconds,
            }
            for c in combos
        ],
    }


@router.post("/experiments/{exp_id}/evaluate")
async def evaluate_experiment(exp_id: int, db: Session = Depends(get_db)):
    """Evaluate all completed transcripts synchronously and return results."""
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")

    # Run in a thread with its own event loop
    import asyncio, concurrent.futures
    def run():
        asyncio.run(_evaluate_experiment_async(exp_id))

    with concurrent.futures.ThreadPoolExecutor() as pool:
        await asyncio.get_event_loop().run_in_executor(pool, run)

    # Return fresh combination data
    db.refresh(exp)
    combos = db.query(AgentExperimentCombination).filter(
        AgentExperimentCombination.experiment_id == exp_id
    ).all()
    return {
        "status": "completed",
        "experiment_id": exp_id,
        "evaluated_combinations": len([c for c in combos if c.aggregated_metrics]),
    }


def _evaluate_experiment_sync(experiment_id: int):
    """Sync wrapper for evaluation (runs in thread with own event loop)."""
    import asyncio
    asyncio.run(_evaluate_experiment_async(experiment_id))


async def _evaluate_experiment_async(experiment_id: int):
    from app.core.database import SessionLocal
    from app.services.agent_evaluator import evaluate_experiment
    db = SessionLocal()
    try:
        await evaluate_experiment(db, experiment_id)
    except Exception:
        logger.exception("Evaluation failed")
    finally:
        db.close()


@router.post("/experiments/{exp_id}/report/generate")
async def generate_report(exp_id: int, db: Session = Depends(get_db)):
    """Generate an LLM-powered improvement report synchronously and return it."""
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")

    import asyncio, concurrent.futures, traceback

    result_container: dict = {}
    def run():
        from app.services.agent_report_generator import generate_report as gen
        from app.core.database import SessionLocal
        db2 = SessionLocal()
        try:
            result = asyncio.run(gen(db2, exp_id))
            result_container["result"] = result
        except Exception as e:
            logger.exception(f"Report generation failed for experiment {exp_id}")
            result_container["error"] = str(e) or e.__class__.__name__
            result_container["traceback"] = traceback.format_exc()
        finally:
            db2.close()

    with concurrent.futures.ThreadPoolExecutor() as pool:
        await asyncio.get_event_loop().run_in_executor(pool, run)

    if "error" in result_container:
        raise HTTPException(
            status_code=500,
            detail=f"Report generation failed: {result_container['error']}",
        )

    return result_container.get("result", {"report": "", "experiment_id": exp_id})


@router.get("/experiments/{exp_id}/report")
def get_report(exp_id: int, db: Session = Depends(get_db)):
    """Get an existing generated report."""
    exp = db.query(AgentExperiment).filter(AgentExperiment.id == exp_id).first()
    if not exp:
        raise HTTPException(404, "Experiment not found")
    grid = exp.grid_config or {}
    return {
        "report": grid.get("report", ""),
        "generated": grid.get("report_generated", False),
        "experiment_id": exp_id,
    }


def _generate_report_sync(experiment_id: int):
    """Sync wrapper for report generation (runs in thread with own event loop)."""
    import asyncio
    asyncio.run(_generate_report_async(experiment_id))


async def _generate_report_async(experiment_id: int):
    from app.core.database import SessionLocal
    from app.services.agent_report_generator import generate_report
    db = SessionLocal()
    try:
        await generate_report(db, experiment_id)
    except Exception:
        logger.exception("Report generation failed")
    finally:
        db.close()
