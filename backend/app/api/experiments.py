"""Experiment management API routes with grid search and execution."""

import asyncio
import csv
import io
import itertools
import uuid
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.core.database import get_db, SessionLocal
from app.models.experiment import Experiment, ExperimentCombination, HumanRating
from app.models.dataset import Dataset
from app.schemas.provider import EMBEDDING_DIMENSIONS
from app.schemas.experiment import (
    CorrelationStat,
    ExperimentCorrelationReport,
    ExperimentCreate,
    ExperimentResponse,
    GridSearchConfig,
    ExperimentReport,
    HumanRatingCreate,
    HumanRatingResponse,
    HumanRatingUpdate,
)
from app.services.experiment_runner import run_experiment as run_experiment_service

router = APIRouter()


def _run_experiment_sync(experiment_id: int, max_workers: int = 2):
    """Synchronous wrapper for background experiment execution."""
    db = SessionLocal()
    try:
        # Load vectorstore config from DB if configured
        from app.models.experiment import Experiment as ExpModel
        from app.models.vectorstore_config import VectorStoreConfig as VSConfig
        exp = db.query(ExpModel).filter(ExpModel.id == experiment_id).first()
        vs_config = None
        if exp and exp.vectorstore_type != "chromadb":
            vs_entry = db.query(VSConfig).filter(
                VSConfig.vectorstore_type == exp.vectorstore_type,
                VSConfig.is_active == True,
            ).first()
            if vs_entry:
                vs_config = dict(vs_entry.config or {})
                if vs_entry.api_key:
                    vs_config["api_key"] = vs_entry.api_key

        asyncio.run(run_experiment_service(experiment_id, db, vectorstore_config=vs_config, max_workers=max_workers))
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


class BulkDeleteRequest(BaseModel):
    ids: list[int]


@router.post("/bulk-delete")
def bulk_delete_experiments(
    payload: BulkDeleteRequest, db: Session = Depends(get_db)
):
    """Delete multiple experiments at once (issue #115).

    Running experiments are skipped and reported in the response so the
    caller can show the user which ones need to be stopped first.
    """
    if not payload.ids:
        return {"deleted": [], "skipped": [], "not_found": []}

    exps = db.query(Experiment).filter(Experiment.id.in_(payload.ids)).all()
    existing_ids = {e.id for e in exps}
    not_found = [i for i in payload.ids if i not in existing_ids]

    deleted: list[int] = []
    skipped: list[dict] = []
    for exp in exps:
        if exp.status == "running":
            skipped.append({"id": exp.id, "reason": "running"})
            continue
        db.query(ExperimentCombination).filter(
            ExperimentCombination.experiment_id == exp.id
        ).delete()
        db.delete(exp)
        deleted.append(exp.id)
    db.commit()
    return {"deleted": deleted, "skipped": skipped, "not_found": not_found}


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

    # Split search types for counting
    ADVANCED_COST_TYPES = {"multi_query", "agentic", "crag", "self_rag", "raptor"}
    simple_types = [t for t in config.search_types if t not in ADVANCED_COST_TYPES]
    has_mq = "multi_query" in config.search_types
    has_ag = "agentic" in config.search_types
    has_crag = "crag" in config.search_types
    has_self_rag = "self_rag" in config.search_types
    has_raptor = "raptor" in config.search_types
    # Effective search type count includes sub-parameter expansion
    effective_search_count = (
        len(simple_types)
        + (len(config.multi_query_counts) if has_mq else 0)
        + (len(config.agent_max_steps) if has_ag else 0)
        + (len(config.crag_relevance_thresholds) * len(config.crag_max_retries) if has_crag else 0)
        + (len(config.self_rag_retrieval_thresholds) if has_self_rag else 0)
        + (len(config.raptor_max_levels) * len(config.raptor_clustering) * len(config.raptor_retrieval_modes) if has_raptor else 0)
    )

    num_base = (
        len(config.chunk_sizes) * len(config.chunk_overlaps) *
        len(config.embedding_models) * len(config.top_k_values) *
        max(effective_search_count, 1) * len(config.distance_metrics) *
        len(config.chunking_strategies) if hasattr(config, "chunking_strategies") else
        len(config.chunk_sizes) * len(config.chunk_overlaps) *
        len(config.embedding_models) * len(config.top_k_values) *
        max(effective_search_count, 1) * len(config.distance_metrics)
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
    # Prompt template multiplier
    prompt_multiplier = max(len(config.prompt_templates), 1)
    total_combos *= prompt_multiplier

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

    # GraphRAG entity extraction cost estimate
    graphrag_extraction_tokens = 0
    if "graphrag" in config.pipeline_types:
        entity_models = config.entity_extraction_models or ["gpt-4o-mini"]
        num_graphrag_combos = (
            len(config.chunk_sizes) * len(config.chunk_overlaps) *
            len(config.chunking_strategies) * len(config.embedding_models) *
            len(entity_models) * len(config.max_gleanings) *
            len(config.community_levels) * len(config.search_modes)
        )
        avg_gleanings = sum(config.max_gleanings) / max(len(config.max_gleanings), 1)
        # ~500 tokens per chunk per gleaning per combination
        graphrag_extraction_tokens = int(est_chunks * 500 * avg_gleanings * num_graphrag_combos)
        total_llm += graphrag_extraction_tokens

    # Multi-Query extra LLM cost: ~500 tokens/question for query generation
    multi_query_extra_tokens = 0
    if has_mq:
        mq_combos = int(
            len(config.chunk_sizes) * len(config.chunk_overlaps) *
            len(config.embedding_models) * len(config.top_k_values) *
            len(config.multi_query_counts) * len(config.distance_metrics) *
            len(config.chunking_strategies) * dim_multiplier
        )
        multi_query_extra_tokens = int(num_questions * 500 * mq_combos)
        total_llm += multi_query_extra_tokens

    # Agentic extra LLM cost: ~800 tokens × avg_steps/question
    agentic_extra_tokens = 0
    if has_ag:
        ag_combos = int(
            len(config.chunk_sizes) * len(config.chunk_overlaps) *
            len(config.embedding_models) * len(config.top_k_values) *
            len(config.agent_max_steps) * len(config.distance_metrics) *
            len(config.chunking_strategies) * dim_multiplier
        )
        avg_steps = sum(config.agent_max_steps) / max(len(config.agent_max_steps), 1)
        agentic_extra_tokens = int(num_questions * 800 * avg_steps * ag_combos)
        total_llm += agentic_extra_tokens

    # HyDE extra: ~300 tokens/question for hypothesis generation
    hyde_extra_tokens = 0
    if "hyde" in config.search_types:
        hyde_extra_tokens = int(num_questions * 300 * total_combos / max(effective_search_count, 1))
        total_llm += hyde_extra_tokens

    # CAG extra: full document in every prompt (~100K tokens/question, no embedding)
    cag_extra_tokens = 0
    if "cag" in config.search_types:
        cag_tokens_per_q = min(total_doc_chars, 100_000)
        cag_extra_tokens = int(num_questions * cag_tokens_per_q)
        total_llm += cag_extra_tokens

    # CRAG extra: ~800 tokens/question for grading + reformulation
    crag_extra_tokens = 0
    if has_crag:
        avg_retries = sum(config.crag_max_retries) / max(len(config.crag_max_retries), 1)
        crag_combos = int(len(config.crag_relevance_thresholds) * len(config.crag_max_retries))
        crag_extra_tokens = int(num_questions * 800 * (1 + avg_retries) * crag_combos)
        total_llm += crag_extra_tokens

    # Self-RAG extra: ~600 tokens/question for decision + grading
    self_rag_extra_tokens = 0
    if has_self_rag:
        sr_combos = len(config.self_rag_retrieval_thresholds)
        self_rag_extra_tokens = int(num_questions * 600 * sr_combos)
        total_llm += self_rag_extra_tokens

    # RAPTOR extra: ~1000 tokens/cluster for summarization × levels
    raptor_extra_tokens = 0
    if has_raptor:
        avg_levels = sum(config.raptor_max_levels) / max(len(config.raptor_max_levels), 1)
        raptor_combos = int(len(config.raptor_max_levels) * len(config.raptor_clustering) * len(config.raptor_retrieval_modes))
        raptor_extra_tokens = int(est_chunks * 1000 * avg_levels * raptor_combos)
        total_llm += raptor_extra_tokens

    # Cost estimates (approximate pricing per 1M tokens)
    EMBEDDING_COST_PER_M = 0.02  # text-embedding-3-small
    LLM_COST_PER_M = 0.50  # gpt-4o-mini average

    est_embedding_cost = (total_embedding / 1_000_000) * EMBEDDING_COST_PER_M
    est_llm_cost = (total_llm / 1_000_000) * LLM_COST_PER_M
    est_total_cost = est_embedding_cost + est_llm_cost

    result = {
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
    if graphrag_extraction_tokens:
        result["breakdown"]["graphrag_entity_extraction_tokens"] = graphrag_extraction_tokens
    if multi_query_extra_tokens:
        result["breakdown"]["multi_query_generation_tokens"] = multi_query_extra_tokens
    if agentic_extra_tokens:
        result["breakdown"]["agentic_reasoning_tokens"] = agentic_extra_tokens
    if hyde_extra_tokens:
        result["breakdown"]["hyde_hypothesis_tokens"] = hyde_extra_tokens
    if cag_extra_tokens:
        result["breakdown"]["cag_full_context_tokens"] = cag_extra_tokens
    if crag_extra_tokens:
        result["breakdown"]["crag_grading_tokens"] = crag_extra_tokens
    if self_rag_extra_tokens:
        result["breakdown"]["self_rag_decision_tokens"] = self_rag_extra_tokens
    if raptor_extra_tokens:
        result["breakdown"]["raptor_summarization_tokens"] = raptor_extra_tokens
    return result


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

    combo_count = 0

    # --- RAG combinations ---
    if "rag" in config.pipeline_types:
        # Split search types into simple (no sub-params) and advanced (with sub-params)
        ADVANCED_TYPES = {"multi_query", "agentic", "crag", "self_rag", "raptor"}
        simple_search_types = [t for t in config.search_types if t not in ADVANCED_TYPES]
        # HyDE and CAG are "simple" (no sub-params) — they pass through as-is
        has_multi_query = "multi_query" in config.search_types
        has_agentic = "agentic" in config.search_types
        has_crag = "crag" in config.search_types
        has_self_rag = "self_rag" in config.search_types
        has_raptor = "raptor" in config.search_types

        def _expand_dims(embedding_model):
            """Return list of embedding dimensions for a given model."""
            model_info = EMBEDDING_DIMENSIONS.get(embedding_model)
            default_dim = model_info["default"] if model_info else None
            if config.embedding_dimensions:
                supported = model_info["supported"] if model_info else []
                dims = [d for d in config.embedding_dimensions if d in supported]
                return dims if dims else [default_dim]
            return [default_dim]

        # Prompt templates: empty list = default prompt only (None in params)
        prompt_list = config.prompt_templates if config.prompt_templates else [None]

        # Reranker axis (issue #116). Always contains at least "none" so the
        # matrix has a baseline. rerank_top_ns is only applied when reranker != none.
        reranker_list = config.rerankers if config.rerankers else ["none"]
        rerank_top_n_list = config.rerank_top_ns if config.rerank_top_ns else [None]

        def _add_combo(params_dict):
            nonlocal combo_count
            for rr in reranker_list:
                if rr == "none":
                    db.add(ExperimentCombination(
                        experiment_id=experiment_id,
                        params={**params_dict, "reranker": "none"},
                    ))
                    combo_count += 1
                else:
                    for rt in rerank_top_n_list:
                        p = {**params_dict, "reranker": rr}
                        if rt is not None:
                            p["rerank_top_n"] = rt
                        db.add(ExperimentCombination(experiment_id=experiment_id, params=p))
                        combo_count += 1

        # Base parameter lists (without search_type, which is handled separately)
        base_lists = list(
            itertools.product(
                config.chunk_sizes,
                config.chunk_overlaps,
                config.embedding_models,
                config.top_k_values,
                config.distance_metrics,
                config.chunking_strategies,
            )
        )

        for combo in base_lists:
            embedding_model = combo[2]
            for dim in _expand_dims(embedding_model):
              for pt in prompt_list:
                base_params = {
                    "pipeline_type": "rag",
                    "chunk_size": combo[0],
                    "chunk_overlap": combo[1],
                    "embedding_model": embedding_model,
                    "top_k": combo[3],
                    "distance_metric": combo[4],
                    "chunking_strategy": combo[5],
                    "embedding_dimensions": dim,
                    "answer_language": config.answer_language,
                }
                if config.optional_metrics:
                    base_params["optional_metrics"] = config.optional_metrics
                if pt is not None:
                    base_params["prompt_template"] = pt

                # Simple search types (vector, hybrid, mmr)
                for st in simple_search_types:
                    _add_combo({**base_params, "search_type": st})

                # Multi-Query: expand with multi_query_counts
                if has_multi_query:
                    for mqc in config.multi_query_counts:
                        _add_combo({**base_params, "search_type": "multi_query", "multi_query_count": mqc})

                # Agentic: expand with agent_max_steps
                if has_agentic:
                    for ams in config.agent_max_steps:
                        _add_combo({**base_params, "search_type": "agentic", "agent_max_steps": ams})

                # CRAG: expand with relevance_threshold × max_retries
                if has_crag:
                    for crt in config.crag_relevance_thresholds:
                        for cmr in config.crag_max_retries:
                            _add_combo({**base_params, "search_type": "crag",
                                        "crag_relevance_threshold": crt, "crag_max_retries": cmr})

                # Self-RAG: expand with retrieval_threshold
                if has_self_rag:
                    for srt in config.self_rag_retrieval_thresholds:
                        _add_combo({**base_params, "search_type": "self_rag",
                                    "self_rag_retrieval_threshold": srt})

                # RAPTOR: expand with max_levels × clustering × retrieval_mode
                if has_raptor:
                    for rml in config.raptor_max_levels:
                        for rc in config.raptor_clustering:
                            for rrm in config.raptor_retrieval_modes:
                                _add_combo({**base_params, "search_type": "raptor",
                                            "raptor_max_levels": rml, "raptor_clustering": rc,
                                            "raptor_retrieval_mode": rrm})

    # --- GraphRAG combinations ---
    if "graphrag" in config.pipeline_types:
        entity_models = config.entity_extraction_models or ["gpt-4o-mini"]

        graphrag_base_combos = list(
            itertools.product(
                config.chunk_sizes,
                config.chunk_overlaps,
                config.chunking_strategies,
                config.embedding_models,
                entity_models,
                config.max_gleanings,
                config.community_levels,
                config.search_modes,
            )
        )

        for combo in graphrag_base_combos:
            embedding_model = combo[3]
            model_info = EMBEDDING_DIMENSIONS.get(embedding_model)
            default_dim = model_info["default"] if model_info else None

            if config.embedding_dimensions:
                supported = model_info["supported"] if model_info else []
                dims_for_model = [d for d in config.embedding_dimensions if d in supported]
                if not dims_for_model:
                    dims_for_model = [default_dim]
            else:
                dims_for_model = [default_dim]

            for dim in dims_for_model:
                params = {
                    "pipeline_type": "graphrag",
                    "chunk_size": combo[0],
                    "chunk_overlap": combo[1],
                    "chunking_strategy": combo[2],
                    "embedding_model": embedding_model,
                    "embedding_dimensions": dim,
                    "entity_extraction_model": combo[4],
                    "max_gleanings": combo[5],
                    "community_level": combo[6],
                    "search_mode": combo[7],
                    "answer_language": config.answer_language,
                }
                if config.optional_metrics:
                    params["optional_metrics"] = config.optional_metrics
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

    # Pool human ratings across the experiment for the summary panel
    combo_ids = [c.id for c in exp.combinations]
    rating_counts: dict[str, int] = {}
    total_ratings = 0
    if combo_ids:
        ratings = (
            db.query(HumanRating)
            .filter(HumanRating.combination_id.in_(combo_ids))
            .all()
        )
        total_ratings = len(ratings)
        for r in ratings:
            rating_counts[r.rating] = rating_counts.get(r.rating, 0) + 1

    return ExperimentReport(
        experiment=exp,
        best_combination=best,
        summary={
            "total_combinations": total,
            "completed": completed_count,
            "failed": failed_count,
            "pending": total - completed_count - failed_count,
            "human_ratings": {
                "total": total_ratings,
                "counts": rating_counts,
            },
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
        "rank", "pipeline_type", "chunk_size", "chunk_overlap", "chunking_strategy",
        "embedding_model", "embedding_dimensions", "top_k", "search_type", "distance_metric",
        "entity_extraction_model", "max_gleanings", "community_level", "search_mode",
        "faithfulness", "answer_relevancy", "context_precision", "context_recall",
        "answer_similarity", "answer_correctness", "overall_score", "duration_seconds",
        "total_tokens", "total_cost",
        "avg_latency_ms", "p95_latency_ms", "avg_retrieval_ms", "avg_generation_ms",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)

    for i, c in enumerate(completed):
        p = c.params or {}
        writer.writerow([
            i + 1,
            p.get("pipeline_type", "rag"),
            p.get("chunk_size", ""),
            p.get("chunk_overlap", ""),
            p.get("chunking_strategy", "recursive"),
            p.get("embedding_model", ""),
            p.get("embedding_dimensions", ""),
            p.get("top_k", ""),
            p.get("search_type", ""),
            p.get("distance_metric", "cosine"),
            p.get("entity_extraction_model", ""),
            p.get("max_gleanings", ""),
            p.get("community_level", ""),
            p.get("search_mode", ""),
            c.faithfulness,
            c.answer_relevancy,
            c.context_precision,
            c.context_recall,
            c.answer_similarity,
            c.answer_correctness,
            c.overall_score,
            c.duration_seconds,
            c.total_tokens,
            c.total_cost,
            c.avg_latency_ms,
            c.p95_latency_ms,
            c.avg_retrieval_ms,
            c.avg_generation_ms,
        ])

    output.seek(0)
    filename = f"{exp.name or 'experiment'}-results.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )


# ── Human feedback loop (issue #118) ────────────────────────────────

RATING_SCORE = {"correct": 1.0, "partial": 0.5, "incorrect": 0.0}


def _ratings_by_combo(db: Session, combination_id: int) -> dict[int, HumanRating]:
    rows = (
        db.query(HumanRating)
        .filter(HumanRating.combination_id == combination_id)
        .all()
    )
    return {r.question_index: r for r in rows}


@router.get(
    "/combinations/{combination_id}/ratings",
    response_model=list[HumanRatingResponse],
)
def list_combination_ratings(combination_id: int, db: Session = Depends(get_db)):
    combo = (
        db.query(ExperimentCombination)
        .filter(ExperimentCombination.id == combination_id)
        .first()
    )
    if not combo:
        raise HTTPException(status_code=404, detail="Combination not found")
    return (
        db.query(HumanRating)
        .filter(HumanRating.combination_id == combination_id)
        .order_by(HumanRating.question_index)
        .all()
    )


@router.post(
    "/combinations/{combination_id}/ratings",
    response_model=HumanRatingResponse,
)
def upsert_combination_rating(
    combination_id: int,
    payload: HumanRatingCreate,
    db: Session = Depends(get_db),
):
    """Create or update the rating for a (combination, question_index) pair."""
    combo = (
        db.query(ExperimentCombination)
        .filter(ExperimentCombination.id == combination_id)
        .first()
    )
    if not combo:
        raise HTTPException(status_code=404, detail="Combination not found")

    # Validate question_index against detailed_results length when available
    details = combo.detailed_results if isinstance(combo.detailed_results, list) else None
    if details is not None and payload.question_index >= len(details):
        raise HTTPException(
            status_code=400,
            detail=f"question_index {payload.question_index} out of range "
            f"(combination has {len(details)} questions)",
        )

    existing = (
        db.query(HumanRating)
        .filter(
            HumanRating.combination_id == combination_id,
            HumanRating.question_index == payload.question_index,
        )
        .first()
    )

    # Auto-fill question_text from detailed_results if caller didn't provide one
    question_text = payload.question_text
    if question_text is None and details is not None:
        item = details[payload.question_index]
        if isinstance(item, dict):
            question_text = item.get("user_input") or item.get("question")

    if existing:
        existing.rating = payload.rating
        if payload.notes is not None:
            existing.notes = payload.notes
        if question_text is not None and not existing.question_text:
            existing.question_text = question_text
        db.commit()
        db.refresh(existing)
        return existing

    rating = HumanRating(
        combination_id=combination_id,
        question_index=payload.question_index,
        rating=payload.rating,
        notes=payload.notes,
        question_text=question_text,
    )
    db.add(rating)
    db.commit()
    db.refresh(rating)
    return rating


@router.patch(
    "/combinations/{combination_id}/ratings/{rating_id}",
    response_model=HumanRatingResponse,
)
def update_combination_rating(
    combination_id: int,
    rating_id: int,
    payload: HumanRatingUpdate,
    db: Session = Depends(get_db),
):
    rating = (
        db.query(HumanRating)
        .filter(
            HumanRating.id == rating_id,
            HumanRating.combination_id == combination_id,
        )
        .first()
    )
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    if payload.rating is not None:
        rating.rating = payload.rating
    if payload.notes is not None:
        rating.notes = payload.notes
    db.commit()
    db.refresh(rating)
    return rating


@router.delete("/combinations/{combination_id}/ratings/{rating_id}")
def delete_combination_rating(
    combination_id: int, rating_id: int, db: Session = Depends(get_db)
):
    rating = (
        db.query(HumanRating)
        .filter(
            HumanRating.id == rating_id,
            HumanRating.combination_id == combination_id,
        )
        .first()
    )
    if not rating:
        raise HTTPException(status_code=404, detail="Rating not found")
    db.delete(rating)
    db.commit()
    return {"detail": "Rating deleted", "rating_id": rating_id}


def _pearson(xs: list[float], ys: list[float]) -> Optional[float]:
    n = len(xs)
    if n < 2:
        return None
    mean_x = sum(xs) / n
    mean_y = sum(ys) / n
    num = sum((xs[i] - mean_x) * (ys[i] - mean_y) for i in range(n))
    den_x = sum((x - mean_x) ** 2 for x in xs)
    den_y = sum((y - mean_y) ** 2 for y in ys)
    if den_x == 0 or den_y == 0:
        return None
    return num / ((den_x * den_y) ** 0.5)


def _spearman(xs: list[float], ys: list[float]) -> Optional[float]:
    """Spearman = Pearson on ranks. Average ranks for ties."""
    n = len(xs)
    if n < 2:
        return None

    def ranks(values: list[float]) -> list[float]:
        sorted_idx = sorted(range(n), key=lambda i: values[i])
        result = [0.0] * n
        i = 0
        while i < n:
            j = i
            while j + 1 < n and values[sorted_idx[j + 1]] == values[sorted_idx[i]]:
                j += 1
            avg_rank = (i + j) / 2.0 + 1.0  # 1-indexed
            for k in range(i, j + 1):
                result[sorted_idx[k]] = avg_rank
            i = j + 1
        return result

    return _pearson(ranks(xs), ranks(ys))


@router.get("/{experiment_id}/correlation", response_model=ExperimentCorrelationReport)
def get_experiment_correlation(experiment_id: int, db: Session = Depends(get_db)):
    """Pearson/Spearman correlation between human ratings and per-question RAGAS metrics.

    Pools across all combinations of the experiment. Each (combination, question)
    rating pair is matched with the per-question score in ``detailed_results``.
    """
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    combo_ids = [c.id for c in exp.combinations]
    if not combo_ids:
        return ExperimentCorrelationReport(
            experiment_id=experiment_id,
            total_ratings=0,
            rating_counts={},
            metrics=[],
            notes="No combinations in experiment.",
        )

    ratings = (
        db.query(HumanRating)
        .filter(HumanRating.combination_id.in_(combo_ids))
        .all()
    )

    rating_counts: dict[str, int] = {}
    for r in ratings:
        rating_counts[r.rating] = rating_counts.get(r.rating, 0) + 1

    if not ratings:
        return ExperimentCorrelationReport(
            experiment_id=experiment_id,
            total_ratings=0,
            rating_counts={},
            metrics=[],
            notes="No human ratings yet.",
        )

    # Build {combo_id: detailed_results}
    details_by_combo: dict[int, list] = {}
    for c in exp.combinations:
        if isinstance(c.detailed_results, list):
            details_by_combo[c.id] = c.detailed_results

    metric_names = [
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_similarity",
        "answer_correctness",
    ]

    stats: list[CorrelationStat] = []
    for metric in metric_names:
        xs: list[float] = []
        ys: list[float] = []
        for r in ratings:
            details = details_by_combo.get(r.combination_id)
            if not details or r.question_index >= len(details):
                continue
            item = details[r.question_index]
            if not isinstance(item, dict):
                continue
            score = item.get(metric)
            if score is None:
                continue
            try:
                ys.append(float(score))
            except (TypeError, ValueError):
                continue
            xs.append(RATING_SCORE[r.rating])

        stats.append(
            CorrelationStat(
                metric=metric,
                n=len(xs),
                pearson=_pearson(xs, ys) if xs else None,
                spearman=_spearman(xs, ys) if xs else None,
            )
        )

    return ExperimentCorrelationReport(
        experiment_id=experiment_id,
        total_ratings=len(ratings),
        rating_counts=rating_counts,
        metrics=stats,
    )


@router.get("/{experiment_id}/export-rated")
def export_rated_questions(experiment_id: int, db: Session = Depends(get_db)):
    """Export per-question rated data as CSV. One row per (combination, question).

    Only includes questions that have at least one human rating across the
    experiment, joined with the combination's per-question RAGAS scores —
    ready for fine-tuning or dataset improvement.
    """
    exp = db.query(Experiment).filter(Experiment.id == experiment_id).first()
    if not exp:
        raise HTTPException(status_code=404, detail="Experiment not found")

    combo_ids = [c.id for c in exp.combinations]
    ratings = (
        db.query(HumanRating)
        .filter(HumanRating.combination_id.in_(combo_ids))
        .order_by(HumanRating.combination_id, HumanRating.question_index)
        .all()
    )

    combos_by_id = {c.id: c for c in exp.combinations}

    headers = [
        "combination_id",
        "question_index",
        "rating",
        "notes",
        "question",
        "generated_answer",
        "ground_truth",
        "faithfulness",
        "answer_relevancy",
        "context_precision",
        "context_recall",
        "answer_similarity",
        "answer_correctness",
        "pipeline_type",
        "chunk_size",
        "chunk_overlap",
        "embedding_model",
        "top_k",
        "search_type",
    ]

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(headers)

    for r in ratings:
        combo = combos_by_id.get(r.combination_id)
        if not combo:
            continue
        details = combo.detailed_results if isinstance(combo.detailed_results, list) else []
        item: dict = {}
        if r.question_index < len(details) and isinstance(details[r.question_index], dict):
            item = details[r.question_index]
        p = combo.params or {}

        writer.writerow([
            combo.id,
            r.question_index,
            r.rating,
            r.notes or "",
            r.question_text or item.get("user_input") or item.get("question") or "",
            item.get("response") or item.get("answer") or "",
            item.get("reference") or item.get("ground_truth") or "",
            item.get("faithfulness", ""),
            item.get("answer_relevancy", ""),
            item.get("context_precision", ""),
            item.get("context_recall", ""),
            item.get("answer_similarity", ""),
            item.get("answer_correctness", ""),
            p.get("pipeline_type", "rag"),
            p.get("chunk_size", ""),
            p.get("chunk_overlap", ""),
            p.get("embedding_model", ""),
            p.get("top_k", ""),
            p.get("search_type", ""),
        ])

    output.seek(0)
    filename = f"{exp.name or 'experiment'}-rated.csv"
    return StreamingResponse(
        output,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={filename}"},
    )
