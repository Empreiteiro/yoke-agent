"""RAGAS evaluation service for RAG pipeline results."""

import asyncio
import logging
import os
from concurrent.futures import ThreadPoolExecutor
from typing import List, Dict, Any, Optional

from datasets import Dataset as HFDataset
from sqlalchemy.orm import Session

# Must run before `import ragas` — see the module docstring.
from app.services import ragas_compat  # noqa: F401
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_similarity,
    answer_correctness,
)

logger = logging.getLogger(__name__)

# Fixed metrics (always evaluated)
FIXED_METRICS = {
    "faithfulness": faithfulness,
    "answer_relevancy": answer_relevancy,
    "context_precision": context_precision,
    "context_recall": context_recall,
}

# Optional metrics (user can select)
OPTIONAL_METRICS = {
    "answer_similarity": answer_similarity,
    "answer_correctness": answer_correctness,
}


def get_metrics(optional_metric_names: Optional[List[str]] = None):
    """Get the list of RAGAS metrics to evaluate."""
    metrics = list(FIXED_METRICS.values())

    if optional_metric_names:
        for name in optional_metric_names:
            metric = OPTIONAL_METRICS.get(name)
            if metric:
                metrics.append(metric)

    return metrics


def _set_provider_env_vars(db: Session) -> dict:
    """Set environment variables from configured providers so RAGAS can use them.
    Returns the original env vars to restore later."""
    original = {}
    try:
        from app.models.provider import Provider
        providers = db.query(Provider).filter(Provider.is_active == True).all()
        for p in providers:
            if p.provider_type == "openai" and p.api_key:
                original["OPENAI_API_KEY"] = os.environ.get("OPENAI_API_KEY")
                os.environ["OPENAI_API_KEY"] = p.api_key
            elif p.provider_type == "anthropic" and p.api_key:
                original["ANTHROPIC_API_KEY"] = os.environ.get("ANTHROPIC_API_KEY")
                os.environ["ANTHROPIC_API_KEY"] = p.api_key
    except Exception as e:
        logger.warning(f"Failed to set provider env vars: {e}")
    return original


def _restore_env_vars(original: dict):
    """Restore environment variables to their original values."""
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def _run_evaluate(dataset, metrics, all_metric_names: List[str]) -> dict:
    """Run RAGAS evaluate in an isolated context (own thread, own event loop)."""
    result = evaluate(dataset=dataset, metrics=metrics)

    # Extract scores safely — EvaluationResult uses [] access, not .get()
    # Some RAGAS versions return per-question lists; we need the aggregate float.
    scores = {}
    for name in all_metric_names:
        try:
            val = result[name]
            if isinstance(val, list):
                val = sum(val) / len(val) if val else None
            scores[name] = float(val) if val is not None else None
        except (KeyError, TypeError, IndexError):
            scores[name] = None

    # Extract per-question details
    detailed = []
    try:
        df = result.to_pandas()
        for _, row in df.iterrows():
            detailed.append(row.to_dict())
    except Exception:
        pass

    return {"scores": scores, "detailed_results": detailed}


async def evaluate_rag_results(
    rag_results: List[Dict[str, Any]],
    ground_truths: List[str],
    optional_metrics: Optional[List[str]] = None,
    db: Optional[Session] = None,
) -> Dict[str, Any]:
    """Evaluate RAG pipeline results using RAGAS.

    Args:
        rag_results: List of dicts with 'question', 'answer', 'contexts'
        ground_truths: List of expected answers (ground truth)
        optional_metrics: Names of optional metrics to include
        db: Database session to resolve provider API keys

    Returns:
        Dict with metric scores and detailed per-question results
    """
    # Build HuggingFace Dataset for RAGAS
    eval_data = {
        "question": [r["question"] for r in rag_results],
        "answer": [r["answer"] for r in rag_results],
        "contexts": [r["contexts"] for r in rag_results],
        "ground_truth": ground_truths,
    }

    dataset = HFDataset.from_dict(eval_data)
    metrics = get_metrics(optional_metrics)

    # Collect all metric names to extract
    all_metric_names = list(FIXED_METRICS.keys())
    if optional_metrics:
        all_metric_names += [m for m in optional_metrics if m in OPTIONAL_METRICS]

    # Set provider API keys as env vars so RAGAS can create its own clients
    original_env = {}
    if db:
        original_env = _set_provider_env_vars(db)

    try:
        # Run RAGAS in a separate thread so it can create its own event loop
        # (avoids conflict with the running asyncio loop)
        loop = asyncio.get_event_loop()
        with ThreadPoolExecutor(max_workers=1) as executor:
            raw = await loop.run_in_executor(
                executor, lambda: _run_evaluate(dataset, metrics, all_metric_names)
            )
    finally:
        if original_env:
            _restore_env_vars(original_env)

    scores = raw["scores"]

    # Calculate overall score (average of fixed metrics)
    fixed_scores = [v for k, v in scores.items() if k in FIXED_METRICS and v is not None]
    scores["overall_score"] = sum(fixed_scores) / len(fixed_scores) if fixed_scores else 0.0

    return {
        "scores": scores,
        "detailed_results": raw["detailed_results"],
    }
