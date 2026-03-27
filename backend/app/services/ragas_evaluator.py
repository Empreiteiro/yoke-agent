"""RAGAS evaluation service for RAG pipeline results."""

from typing import List, Dict, Any, Optional

from datasets import Dataset as HFDataset
from ragas import evaluate
from ragas.metrics import (
    faithfulness,
    answer_relevancy,
    context_precision,
    context_recall,
    answer_similarity,
    answer_correctness,
)


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


async def evaluate_rag_results(
    rag_results: List[Dict[str, Any]],
    ground_truths: List[str],
    optional_metrics: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Evaluate RAG pipeline results using RAGAS.

    Args:
        rag_results: List of dicts with 'question', 'answer', 'contexts'
        ground_truths: List of expected answers (ground truth)
        optional_metrics: Names of optional metrics to include

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

    # Run RAGAS evaluation
    result = evaluate(dataset=dataset, metrics=metrics)

    # Extract scores
    scores = {}
    for metric_name in FIXED_METRICS:
        scores[metric_name] = result.get(metric_name)

    if optional_metrics:
        for metric_name in optional_metrics:
            if metric_name in OPTIONAL_METRICS:
                scores[metric_name] = result.get(metric_name)

    # Calculate overall score (average of fixed metrics)
    fixed_scores = [v for k, v in scores.items() if k in FIXED_METRICS and v is not None]
    scores["overall_score"] = sum(fixed_scores) / len(fixed_scores) if fixed_scores else 0.0

    # Get per-question details from the result dataset
    detailed_results = []
    if hasattr(result, "to_pandas"):
        df = result.to_pandas()
        for _, row in df.iterrows():
            detailed_results.append(row.to_dict())

    return {
        "scores": scores,
        "detailed_results": detailed_results,
    }
