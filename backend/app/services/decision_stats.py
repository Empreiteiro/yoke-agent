"""Statistics for Model Comparison results.

Everything here is computed on demand from stored predictions, so changing
an analysis setting (which labels count as "block", the deployment
prevalence, error costs…) never needs a re-run:

* **Uncertainty** — Wilson intervals for accuracy and rates, a bootstrap
  interval for macro-F1 and an order-statistic interval for median latency.
* **Significance** — paired McNemar tests between models (every model saw
  the same rows), Holm-adjusted, and which models are statistically tied
  with the top-ranked one.
* **Guardrail (binary) view** — labels are split into a positive "block"
  class and the rest: detection rate, miss rate, over-blocking (FPR),
  precision at a deployment prevalence and an expected error cost.
* **Scores** — ROC / PR curves and operating points from the probability
  (or confidence) each model gave the positive class.
* **Calibration** — ECE, Brier score and a reliability table.
* **Slices** — accuracy per dataset difficulty.
* **Policy sensitivity** — accuracy spread across variants (prompt or policy
  wording) of the same model.
"""

from __future__ import annotations

import math
from collections import defaultdict
from dataclasses import dataclass
from typing import Iterable, Optional, Sequence

import numpy as np

Z95 = 1.959963984540054
ALPHA = 0.05
BOOTSTRAP_ROUNDS = 1000
BOOTSTRAP_CHUNK = 100
CALIBRATION_BINS = 10
MAX_CURVE_POINTS = 101
MCNEMAR_EXACT_MAX = 1000

FAILURE_POLICIES = ("open", "closed", "exclude")
# Label names treated as the "allow" class when the user hasn't chosen.
SAFE_LABEL_NAMES = {
    "safe", "benign", "allow", "allowed", "clean", "harmless", "legitimate", "not_flagged", "unflagged",
}


@dataclass
class PredictionRow:
    model_result_id: int
    item_id: int
    expected_label: str
    predicted_label: Optional[str]
    status: str
    is_correct: bool
    confidence: Optional[float] = None
    probabilities: Optional[dict] = None
    latency_ms: Optional[float] = None


# ── Intervals & tests ───────────────────────────────────────────────────


def wilson_interval(successes: int, n: int, z: float = Z95) -> Optional[list[float]]:
    """95% Wilson score interval for a proportion; ``None`` when ``n == 0``."""
    if n <= 0:
        return None
    p = successes / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    half = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    # The bounds are exactly 0 / 1 at p = 0 / 1; avoid 0.9999999999999999.
    lo = 0.0 if successes == 0 else max(0.0, center - half)
    hi = 1.0 if successes == n else min(1.0, center + half)
    return [lo, hi]


def mcnemar_p(b: int, c: int) -> float:
    """Two-sided McNemar p-value for discordant counts ``b`` and ``c``.

    Exact binomial test for small samples, chi-square with continuity
    correction otherwise.
    """
    n = b + c
    if n == 0:
        return 1.0
    if n <= MCNEMAR_EXACT_MAX:
        k = min(b, c)
        tail = sum(math.comb(n, i) for i in range(k + 1)) / (2 ** n)
        return min(1.0, 2 * tail)
    stat = (abs(b - c) - 1) ** 2 / n
    return math.erfc(math.sqrt(stat / 2))


def holm_adjust(pvalues: Sequence[float]) -> list[float]:
    """Holm–Bonferroni adjusted p-values (same order as the input)."""
    m = len(pvalues)
    order = sorted(range(m), key=lambda i: pvalues[i])
    adjusted = [0.0] * m
    running = 0.0
    for rank, i in enumerate(order):
        running = max(running, min(1.0, (m - rank) * pvalues[i]))
        adjusted[i] = running
    return adjusted


def _macro_f1_from_counts(tp: np.ndarray, pred: np.ndarray, support: np.ndarray) -> np.ndarray:
    """Macro-F1 per row of ``(rounds, labels)`` count matrices.

    Matches ``compute_metrics``: averaged over labels present in the sample;
    a present label the model never predicted counts as F1 = 0.
    """
    with np.errstate(divide="ignore", invalid="ignore"):
        precision = np.where(pred > 0, tp / np.maximum(pred, 1), 0.0)
        recall = np.where(support > 0, tp / np.maximum(support, 1), 0.0)
        f1 = np.where(precision + recall > 0, 2 * precision * recall / np.maximum(precision + recall, 1e-12), 0.0)
    present = support > 0
    counts = present.sum(axis=1)
    return np.where(counts > 0, (f1 * present).sum(axis=1) / np.maximum(counts, 1), np.nan)


def bootstrap_macro_f1(
    expected: Sequence[int],
    predicted: Sequence[int],
    n_labels: int,
    rounds: int = BOOTSTRAP_ROUNDS,
    seed: int = 0,
) -> Optional[list[float]]:
    """Percentile bootstrap 95% interval for macro-F1.

    ``expected`` / ``predicted`` are label indices; a failed prediction is
    ``-1`` (it counts against recall but isn't a prediction of any label).
    Macro-F1 only depends on the confusion counts, so resampling rows is
    drawn directly as a multinomial over confusion cells — the same
    distribution as resampling rows, at a cost independent of their number.
    """
    n = len(expected)
    if n < 2 or n_labels < 1:
        return None
    k = n_labels
    exp = np.asarray(expected, dtype=np.int64)
    pred = np.asarray(predicted, dtype=np.int64)
    valid = exp >= 0
    exp, pred = exp[valid], pred[valid]
    if exp.size < 2:
        return None
    # Column k holds "no answer".
    cells = exp * (k + 1) + np.where(pred >= 0, pred, k)
    probs = np.bincount(cells, minlength=k * (k + 1)) / exp.size
    rng = np.random.default_rng(seed)
    stats_: list[np.ndarray] = []
    for start in range(0, rounds, BOOTSTRAP_CHUNK):
        b = min(BOOTSTRAP_CHUNK, rounds - start)
        draws = rng.multinomial(exp.size, probs, size=b).reshape(b, k, k + 1)
        support = draws.sum(axis=2)
        predc = draws[:, :, :k].sum(axis=1)
        tp = np.diagonal(draws[:, :, :k], axis1=1, axis2=2)
        stats_.append(_macro_f1_from_counts(tp, predc, support))
    values = np.concatenate(stats_)
    values = values[~np.isnan(values)]
    if values.size == 0:
        return None
    lo, hi = np.percentile(values, [100 * ALPHA / 2, 100 * (1 - ALPHA / 2)])
    return [float(lo), float(hi)]


def median_interval(values: Sequence[float], z: float = Z95) -> Optional[list[float]]:
    """Distribution-free 95% interval for the median (order statistics).

    The number of observations below the median is Binomial(n, ½), so the
    interval runs between the order statistics at n/2 ∓ z·√n/2.
    """
    arr = np.sort(np.asarray([v for v in values if v is not None], dtype=float))
    n = arr.size
    if n < 2:
        return None
    half = z * math.sqrt(n) / 2
    lo = max(0, int(math.floor(n / 2 - half)))
    hi = min(n - 1, int(math.ceil(n / 2 + half)))
    return [float(arr[lo]), float(arr[hi])]


# ── Binary (guardrail) view ─────────────────────────────────────────────


def _ratio(num: float, den: float) -> Optional[float]:
    return num / den if den else None


def binary_metrics(
    rows: Iterable[PredictionRow],
    positive: set[str],
    failure_policy: str = "open",
    prevalence: Optional[float] = None,
    fn_cost: float = 1.0,
    fp_cost: float = 1.0,
) -> dict:
    """Confusion counts and rates for "positive (block) vs. the rest".

    ``failure_policy`` decides what a failed request means: ``open`` lets
    the text through (counts as a negative prediction), ``closed`` blocks
    it, ``exclude`` drops the row.
    """
    tp = fp = tn = fn = excluded = 0
    for r in rows:
        actual = r.expected_label in positive
        if r.status == "ok":
            flagged = r.predicted_label in positive
        elif failure_policy == "exclude":
            excluded += 1
            continue
        else:
            flagged = failure_policy == "closed"
        if actual and flagged:
            tp += 1
        elif actual:
            fn += 1
        elif flagged:
            fp += 1
        else:
            tn += 1

    n = tp + fp + tn + fn
    recall = _ratio(tp, tp + fn)
    fpr = _ratio(fp, fp + tn)
    precision = _ratio(tp, tp + fp)
    specificity = None if fpr is None else 1 - fpr
    f1 = (
        2 * precision * recall / (precision + recall)
        if precision is not None and recall is not None and (precision + recall) > 0
        else (0.0 if recall is not None else None)
    )
    balanced = (recall + specificity) / 2 if recall is not None and specificity is not None else None
    mcc_den = math.sqrt((tp + fp) * (tp + fn) * (tn + fp) * (tn + fn))
    mcc = (tp * tn - fp * fn) / mcc_den if mcc_den else None

    sample_prevalence = _ratio(tp + fn, n)
    p = prevalence if prevalence is not None else sample_prevalence
    ppv_at_prevalence = None
    expected_cost = None
    if p is not None and recall is not None and fpr is not None:
        den = recall * p + fpr * (1 - p)
        ppv_at_prevalence = recall * p / den if den else None
        expected_cost = 1000 * (p * (1 - recall) * fn_cost + (1 - p) * fpr * fp_cost)

    return {
        "n": n,
        "excluded": excluded,
        "tp": tp, "fp": fp, "tn": tn, "fn": fn,
        "recall": recall,
        "recall_ci": wilson_interval(tp, tp + fn),
        "miss_rate": None if recall is None else 1 - recall,
        "fpr": fpr,
        "fpr_ci": wilson_interval(fp, fp + tn),
        "specificity": specificity,
        "precision": precision,
        "f1": f1,
        "balanced_accuracy": balanced,
        "mcc": mcc,
        "sample_prevalence": sample_prevalence,
        "prevalence_used": p,
        "precision_at_prevalence": ppv_at_prevalence,
        "expected_cost_per_1k": expected_cost,
    }


def positive_score(row: PredictionRow, positive: set[str], failure_policy: str) -> tuple[Optional[float], str]:
    """Score for "this row belongs to the positive class" and its source.

    Prefers the model's probability distribution, then its confidence in
    the label it picked, then the hard label (0/1).
    """
    if row.status != "ok":
        if failure_policy == "exclude":
            return None, "failed"
        return (1.0 if failure_policy == "closed" else 0.0), "failed"
    if row.probabilities:
        total = sum(float(v) for k, v in row.probabilities.items() if k in positive)
        return max(0.0, min(1.0, total)), "probabilities"
    flagged = row.predicted_label in positive
    if row.confidence is not None:
        conf = max(0.0, min(1.0, row.confidence))
        return (conf if flagged else 1 - conf), "confidence"
    return (1.0 if flagged else 0.0), "hard"


def roc_analysis(scores: Sequence[float], labels: Sequence[bool]) -> Optional[dict]:
    """ROC-AUC, PR-AUC (average precision), curves and operating points."""
    pos = sum(1 for l in labels if l)
    neg = len(labels) - pos
    if pos == 0 or neg == 0:
        return None
    s = np.asarray(scores, dtype=float)
    y = np.asarray(labels, dtype=bool)

    # AUC = P(score_pos > score_neg) with ties counted half (rank-sum).
    order = np.argsort(s, kind="mergesort")
    ranks = np.empty(len(s), dtype=float)
    sorted_s = s[order]
    i = 0
    while i < len(s):
        j = i
        while j + 1 < len(s) and sorted_s[j + 1] == sorted_s[i]:
            j += 1
        ranks[order[i:j + 1]] = (i + j) / 2 + 1
        i = j + 1
    auc = (ranks[y].sum() - pos * (pos + 1) / 2) / (pos * neg)

    # Curve over distinct thresholds, highest first.
    desc = np.argsort(-s, kind="mergesort")
    s_desc, y_desc = s[desc], y[desc]
    tps = np.cumsum(y_desc)
    fps = np.cumsum(~y_desc)
    last = np.r_[np.where(np.diff(s_desc))[0], len(s_desc) - 1]
    thresholds = s_desc[last]
    tpr = tps[last] / pos
    fpr = fps[last] / neg
    precision = tps[last] / (tps[last] + fps[last])

    ap = float(np.sum(np.diff(np.r_[0.0, tpr]) * precision))
    f1 = np.where(precision + tpr > 0, 2 * precision * tpr / np.maximum(precision + tpr, 1e-12), 0.0)
    best = int(np.argmax(f1))

    def recall_at_fpr(limit: float) -> Optional[dict]:
        ok = np.where(fpr <= limit + 1e-12)[0]
        if ok.size == 0:
            return None
        k = ok[np.argmax(tpr[ok])]
        return {"threshold": float(thresholds[k]), "recall": float(tpr[k]), "fpr": float(fpr[k])}

    def fpr_at_recall(target: float) -> Optional[dict]:
        ok = np.where(tpr >= target - 1e-12)[0]
        if ok.size == 0:
            return None
        k = ok[np.argmin(fpr[ok])]
        return {"threshold": float(thresholds[k]), "recall": float(tpr[k]), "fpr": float(fpr[k])}

    points = [{"threshold": None, "tpr": 0.0, "fpr": 0.0, "precision": None}] + [
        {"threshold": float(t), "tpr": float(a), "fpr": float(b), "precision": float(p)}
        for t, a, b, p in zip(thresholds, tpr, fpr, precision)
    ]
    if len(points) > MAX_CURVE_POINTS:
        keep = np.unique(np.linspace(0, len(points) - 1, MAX_CURVE_POINTS).round().astype(int))
        points = [points[k] for k in keep]

    return {
        "auc": float(auc),
        "pr_auc": ap,
        "positives": pos,
        "negatives": neg,
        "distinct_scores": int(len(thresholds)),
        "points": points,
        "best_f1": {"threshold": float(thresholds[best]), "f1": float(f1[best]),
                    "recall": float(tpr[best]), "fpr": float(fpr[best])},
        "recall_at_fpr_1": recall_at_fpr(0.01),
        "recall_at_fpr_5": recall_at_fpr(0.05),
        "fpr_at_recall_95": fpr_at_recall(0.95),
    }


# ── Calibration & slices ────────────────────────────────────────────────


def calibration(confidences: Sequence[float], correct: Sequence[bool], bins: int = CALIBRATION_BINS) -> Optional[dict]:
    """Expected calibration error, Brier score and a reliability table.

    Uses the confidence a model reported for the label it chose: a
    calibrated model is right 80% of the time when it says 0.8.
    """
    n = len(confidences)
    if n == 0:
        return None
    conf = np.clip(np.asarray(confidences, dtype=float), 0.0, 1.0)
    hit = np.asarray(correct, dtype=float)
    idx = np.minimum((conf * bins).astype(int), bins - 1)
    table = []
    ece = 0.0
    for b in range(bins):
        mask = idx == b
        count = int(mask.sum())
        if not count:
            table.append({"lo": b / bins, "hi": (b + 1) / bins, "count": 0, "avg_confidence": None, "accuracy": None})
            continue
        avg_conf = float(conf[mask].mean())
        acc = float(hit[mask].mean())
        ece += count / n * abs(acc - avg_conf)
        table.append({"lo": b / bins, "hi": (b + 1) / bins, "count": count, "avg_confidence": avg_conf, "accuracy": acc})
    return {
        "n": n,
        "ece": float(ece),
        "brier": float(np.mean((conf - hit) ** 2)),
        "avg_confidence": float(conf.mean()),
        "accuracy": float(hit.mean()),
        "overconfidence": float(conf.mean() - hit.mean()),
        "bins": table,
    }


def slice_accuracy(rows: Iterable[PredictionRow], groups: dict[int, Optional[str]]) -> dict:
    """Accuracy (with Wilson interval) per group value, e.g. difficulty."""
    counts: dict[str, list[int]] = defaultdict(lambda: [0, 0])
    for r in rows:
        group = groups.get(r.item_id)
        if not group:
            continue
        counts[group][0] += 1
        counts[group][1] += 1 if r.is_correct else 0
    return {
        g: {"n": n, "correct": c, "accuracy": c / n, "accuracy_ci": wilson_interval(c, n)}
        for g, (n, c) in sorted(counts.items())
    }


# ── Cross-model ─────────────────────────────────────────────────────────


def pairwise_mcnemar(correct_by_model: dict[int, dict[int, bool]], order: Sequence[int]) -> list[dict]:
    """Paired McNemar tests for every pair of models, Holm-adjusted."""
    pairs = []
    for i, a in enumerate(order):
        for b in order[i + 1:]:
            ca, cb = correct_by_model.get(a, {}), correct_by_model.get(b, {})
            common = ca.keys() & cb.keys()
            a_only = sum(1 for k in common if ca[k] and not cb[k])
            b_only = sum(1 for k in common if cb[k] and not ca[k])
            pairs.append({
                "a": a, "b": b, "n": len(common),
                "a_only": a_only, "b_only": b_only,
                "p_value": mcnemar_p(a_only, b_only),
            })
    for pair, adj in zip(pairs, holm_adjust([p["p_value"] for p in pairs])):
        pair["p_adjusted"] = adj
        pair["significant"] = adj < ALPHA
    return pairs


def ties_with_best(correct_by_model: dict[int, dict[int, bool]], best_id: Optional[int], others: Sequence[int]) -> dict[int, dict]:
    """For each model, whether its accuracy is distinguishable from the
    top-ranked model's (McNemar, Holm-adjusted within this family)."""
    if best_id is None or best_id not in correct_by_model:
        return {}
    tests = pairwise_mcnemar(correct_by_model, [best_id, *[o for o in others if o != best_id]])
    tests = [t for t in tests if t["a"] == best_id]
    adjusted = holm_adjust([t["p_value"] for t in tests])
    out = {best_id: {"p_value": None, "p_adjusted": None, "tied": True, "is_best": True}}
    for t, adj in zip(tests, adjusted):
        out[t["b"]] = {"p_value": t["p_value"], "p_adjusted": adj, "tied": adj >= ALPHA, "is_best": False}
    return out


def policy_sensitivity(results: Sequence[dict]) -> list[dict]:
    """Accuracy spread across variants of the same model.

    Results are grouped by (kind, provider, model); groups with at least
    two finished variants are reported.
    """
    groups: dict[tuple, list[dict]] = defaultdict(list)
    for r in results:
        if r.get("accuracy") is None:
            continue
        groups[(r["kind"], r.get("provider_id"), r["model_name"])].append(r)
    out = []
    for (kind, _provider_id, model_name), members in groups.items():
        if len(members) < 2:
            continue
        ranked = sorted(members, key=lambda r: r["accuracy"], reverse=True)
        out.append({
            "kind": kind,
            "model_name": model_name,
            "provider_name": ranked[0].get("provider_name"),
            "spread": ranked[0]["accuracy"] - ranked[-1]["accuracy"],
            "best_id": ranked[0]["id"],
            "worst_id": ranked[-1]["id"],
            "variants": [
                {
                    "id": r["id"],
                    "variant": r.get("variant"),
                    "display_name": r.get("display_name"),
                    "accuracy": r["accuracy"],
                    "macro_f1": r.get("macro_f1"),
                    "policy_hash": r.get("policy_hash"),
                }
                for r in ranked
            ],
        })
    out.sort(key=lambda g: g["spread"], reverse=True)
    return out


# ── Settings & full analysis ────────────────────────────────────────────


def resolve_settings(label_names: Sequence[str], stored: Optional[dict]) -> dict:
    """Merge stored analysis settings with defaults.

    Without a stored choice, labels named like "safe"/"benign" become the
    negative class and every other label the positive (block) class.
    """
    stored = stored or {}
    names = list(label_names)
    if stored.get("positive_labels") is not None:
        positive = [l for l in stored["positive_labels"] if l in names]
        auto = False
    else:
        safe = [l for l in names if l.strip().lower() in SAFE_LABEL_NAMES]
        positive = [l for l in names if l not in safe] if safe else []
        auto = True
    policy = stored.get("failure_policy") if stored.get("failure_policy") in FAILURE_POLICIES else "open"
    return {
        "positive_labels": positive,
        "negative_labels": [l for l in names if l not in positive],
        "failure_policy": policy,
        "prevalence": stored.get("prevalence"),
        "fn_cost": float(stored.get("fn_cost") or 1.0),
        "fp_cost": float(stored.get("fp_cost") or 1.0),
        "auto_detected": auto,
        "enabled": 0 < len(positive) < len(names),
    }


def analyze(
    results: Sequence[dict],
    rows: Sequence[PredictionRow],
    label_names: Sequence[str],
    difficulties: dict[int, Optional[str]],
    settings: dict,
) -> dict:
    """Everything the results page shows beyond the per-model counters."""
    by_model: dict[int, list[PredictionRow]] = defaultdict(list)
    for r in rows:
        by_model[r.model_result_id].append(r)
    label_index = {name: i for i, name in enumerate(label_names)}
    positive = set(settings["positive_labels"])
    policy = settings["failure_policy"]

    models: dict[int, dict] = {}
    correct_by_model: dict[int, dict[int, bool]] = {}
    for res in results:
        rid = res["id"]
        preds = by_model.get(rid, [])
        correct_by_model[rid] = {p.item_id: bool(p.is_correct) for p in preds}
        n = len(preds)
        correct = sum(1 for p in preds if p.is_correct)
        expected_idx = [label_index.get(p.expected_label, -1) for p in preds]
        predicted_idx = [
            label_index.get(p.predicted_label, -1) if p.status == "ok" else -1 for p in preds
        ]
        latencies = [p.latency_ms for p in preds if p.latency_ms is not None and p.status != "error"]
        with_conf = [p for p in preds if p.status == "ok" and p.confidence is not None]
        entry: dict = {
            "n": n,
            "accuracy_ci": wilson_interval(correct, n),
            "macro_f1_ci": bootstrap_macro_f1(expected_idx, predicted_idx, len(label_names), seed=rid),
            "p50_latency_ci": median_interval(latencies),
            "calibration": calibration([p.confidence for p in with_conf], [p.is_correct for p in with_conf]),
            "confidence_coverage": _ratio(len(with_conf), n),
            "slices": {"difficulty": slice_accuracy(preds, difficulties)},
            "binary": None,
            "roc": None,
        }
        if settings["enabled"] and preds:
            entry["binary"] = binary_metrics(
                preds, positive, policy, settings["prevalence"], settings["fn_cost"], settings["fp_cost"],
            )
            scored = [(positive_score(p, positive, policy), p.expected_label in positive) for p in preds]
            scored = [((s, src), y) for (s, src), y in scored if s is not None]
            roc = roc_analysis([s for (s, _), _ in scored], [y for _, y in scored])
            if roc:
                sources = [src for (_, src), _ in scored if src != "failed"]
                roc["score_source"] = max(set(sources), key=sources.count) if sources else "failed"
            entry["roc"] = roc
        models[rid] = entry

    ranked = sorted((r for r in results if r.get("rank")), key=lambda r: r["rank"])
    order = [r["id"] for r in ranked]
    best_id = order[0] if order else None
    return {
        "settings": settings,
        "models": models,
        "pairwise": pairwise_mcnemar(correct_by_model, order),
        "ties_with_best": ties_with_best(correct_by_model, best_id, order[1:]),
        "best_id": best_id,
        "policy_sensitivity": policy_sensitivity(results),
        "has_difficulty": any(difficulties.values()),
    }
