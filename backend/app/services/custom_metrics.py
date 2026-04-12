"""Custom evaluation metrics hook (issue #124).

Users can drop Python modules into a ``custom_metrics/`` directory and have
their functions run alongside the built-in RAGAS metrics. Each module should
expose a ``metrics`` mapping like:

    # custom_metrics/answer_length.py
    def answer_length(row):
        ans = row.get("answer") or ""
        return min(len(ans) / 500, 1.0)

    metrics = {"answer_length": answer_length}

Function signature:
    ``fn(row: dict) -> float``

where ``row`` contains the same keys the pipeline emits per Q&A pair:

    - ``question``
    - ``answer``
    - ``contexts`` (list[str])
    - ``ground_truth``

The return value MUST be a float in [0, 1] (or ``None`` to skip). Exceptions
in a metric are caught, logged, and the row gets ``None`` for that metric.

The loader uses an **env-configurable directory** (default
``backend/custom_metrics/``) so production deployments can mount a volume
without code changes. Modules are reloaded on every call to
``load_custom_metrics()`` so a restart is not required when tweaking metrics.
"""

import importlib.util
import logging
import os
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional

logger = logging.getLogger(__name__)


def _metrics_dir() -> Path:
    override = os.environ.get("CUSTOM_METRICS_DIR")
    if override:
        return Path(override)
    # Default: <repo>/backend/custom_metrics
    return Path(__file__).resolve().parents[2] / "custom_metrics"


def load_custom_metrics() -> Dict[str, Callable[[Dict[str, Any]], Optional[float]]]:
    """Discover and import all custom metric modules in the metrics directory.

    Returns a flat mapping of metric name → callable. Modules are loaded from
    disk every call so studio operators can edit files without restarting the
    server.
    """
    metrics: Dict[str, Callable] = {}
    directory = _metrics_dir()
    if not directory.exists() or not directory.is_dir():
        return metrics

    for py_file in sorted(directory.glob("*.py")):
        if py_file.name.startswith("_"):
            continue
        module_name = f"custom_metrics.{py_file.stem}"
        try:
            spec = importlib.util.spec_from_file_location(module_name, py_file)
            if spec is None or spec.loader is None:
                continue
            module = importlib.util.module_from_spec(spec)
            spec.loader.exec_module(module)  # type: ignore[attr-defined]
        except Exception as e:
            logger.warning("Failed to load custom metrics module %s: %s", py_file.name, e)
            continue

        module_metrics = getattr(module, "metrics", None)
        if not isinstance(module_metrics, dict):
            logger.warning("Custom metrics module %s has no `metrics` dict", py_file.name)
            continue
        for name, fn in module_metrics.items():
            if not callable(fn):
                continue
            if name in metrics:
                logger.warning("Duplicate custom metric %s (from %s) — last one wins", name, py_file.name)
            metrics[name] = fn
    return metrics


def run_custom_metrics(
    rows: List[Dict[str, Any]],
    ground_truths: Optional[List[str]] = None,
) -> Dict[str, Any]:
    """Run every registered custom metric against every row.

    Returns a dict shaped like::

        {
            "metric_name": {
                "scores": [0.8, 0.7, ...],
                "average": 0.75,
            },
            ...
        }

    The caller is responsible for merging ``scores`` back onto per-question
    ``detailed_results`` rows.
    """
    registered = load_custom_metrics()
    if not registered:
        return {}

    results: Dict[str, Dict[str, Any]] = {}
    for name, fn in registered.items():
        scores: List[Optional[float]] = []
        for idx, row in enumerate(rows):
            payload = dict(row)
            if ground_truths is not None and idx < len(ground_truths):
                payload.setdefault("ground_truth", ground_truths[idx])
            try:
                value = fn(payload)
                if value is None:
                    scores.append(None)
                else:
                    scores.append(float(value))
            except Exception as e:
                logger.warning("Custom metric %s failed on row %d: %s", name, idx, e)
                scores.append(None)

        known = [s for s in scores if s is not None]
        avg = sum(known) / len(known) if known else None
        results[name] = {"scores": scores, "average": avg}

    return results
