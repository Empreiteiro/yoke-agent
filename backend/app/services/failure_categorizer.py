"""Rule-based failure categorizer for RAGAS per-question results (issue #117).

A low overall RAGAS score doesn't tell you *why* an answer failed. This helper
assigns each Q&A pair one of a small set of failure categories by looking at
the individual metric values, so the UI can show where the pipeline is
breaking (retrieval vs generation vs grounding).

Categories
----------
- ``ok``: all metrics above the threshold.
- ``missing_context``: retrieval didn't surface the supporting evidence
  (low ``context_recall``). Usually a chunking or top_k problem.
- ``irrelevant_retrieval``: retrieved chunks aren't on-topic
  (low ``context_precision``). Usually a search/embedding problem.
- ``hallucination``: the answer isn't grounded in the retrieved context
  (low ``faithfulness`` while context looked fine). A generation problem.
- ``incomplete_answer``: context and grounding look fine, but the answer
  doesn't actually address the question (low ``answer_relevancy``).
- ``unknown``: not enough metric signal to classify (e.g. all None).

The classifier is intentionally simple and deterministic — it's meant as a
first-pass triage, not a replacement for human review.
"""

from typing import Any, Dict, Iterable, List, Optional

DEFAULT_THRESHOLD = 0.5

FAILURE_CATEGORIES = [
    "ok",
    "missing_context",
    "irrelevant_retrieval",
    "hallucination",
    "incomplete_answer",
    "unknown",
]


def _pick(row: Dict[str, Any], *keys: str) -> Optional[float]:
    """Return the first non-None numeric value for ``keys``."""
    for k in keys:
        v = row.get(k)
        if v is None:
            continue
        try:
            return float(v)
        except (TypeError, ValueError):
            continue
    return None


def categorize_result(
    row: Dict[str, Any],
    threshold: float = DEFAULT_THRESHOLD,
) -> str:
    """Classify a single per-question RAGAS row into a failure category."""
    faithfulness = _pick(row, "faithfulness")
    relevancy = _pick(row, "answer_relevancy")
    precision = _pick(row, "context_precision")
    recall = _pick(row, "context_recall")

    metrics = [faithfulness, relevancy, precision, recall]
    if all(m is None for m in metrics):
        return "unknown"

    # If every metric above threshold → ok. (None values treated as "unknown"
    # at this stage, so we require every *known* metric to pass.)
    known = [m for m in metrics if m is not None]
    if known and all(m >= threshold for m in known):
        return "ok"

    # Retrieval failures take priority — without the right context the rest
    # is garbage-in/garbage-out.
    if recall is not None and recall < threshold:
        return "missing_context"
    if precision is not None and precision < threshold:
        return "irrelevant_retrieval"

    # Generation failures — retrieval is reasonable, but the answer is off.
    if faithfulness is not None and faithfulness < threshold:
        return "hallucination"
    if relevancy is not None and relevancy < threshold:
        return "incomplete_answer"

    return "unknown"


def categorize_detailed_results(
    rows: Iterable[Dict[str, Any]],
    threshold: float = DEFAULT_THRESHOLD,
) -> List[Dict[str, Any]]:
    """Return rows with a ``failure_category`` field added to each item."""
    annotated: List[Dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            row = dict(row)
            row["failure_category"] = categorize_result(row, threshold=threshold)
        annotated.append(row)
    return annotated


def summarize_categories(rows: Iterable[Dict[str, Any]]) -> Dict[str, int]:
    """Count occurrences of each failure category in ``rows``."""
    counts = {c: 0 for c in FAILURE_CATEGORIES}
    for row in rows:
        if not isinstance(row, dict):
            continue
        cat = row.get("failure_category") or "unknown"
        counts[cat] = counts.get(cat, 0) + 1
    return counts
