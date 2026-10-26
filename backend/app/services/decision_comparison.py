"""Model Comparison engine: decision models vs. LLMs on labeled datasets.

Every model in a comparison classifies the *same* sample of dataset rows.
Decision models (TypeSafe Jev, System One-compatible endpoints, OpenAI's
Decisions API) receive the task as a typed ``choice`` question; LLMs
receive the same task and label definitions as a prompt. For each model we
record every prediction plus aggregated accuracy (correct / incorrect /
failed), per-label precision and recall, a confusion matrix, latency
percentiles and total cost.
"""

from __future__ import annotations

import asyncio
import logging
import math
import random
import threading
import time
from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Iterable, Optional

from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.models.decision import (
    DecisionComparison, DecisionDatasetItem, DecisionModelResult, DecisionPrediction,
)
from app.models.provider import Provider
from app.models.token_usage import TokenUsageLog
from app.services.decision_models import (
    DECISION_PROVIDER_TYPES, DecisionClient, estimate_request_tokens,
)
from app.services.llm_classifier import build_messages, parse_answer
from app.services.token_tracker import (
    FLEX_DISCOUNT, extract_llm_token_usage, lookup_decision_pricing, lookup_pricing,
)

logger = logging.getLogger(__name__)

DEFAULT_CONCURRENCY = 8
MAX_CONCURRENCY = 32
LLM_CALL_TIMEOUT_S = 120
FLUSH_EVERY = 25
# Abort a model early when its first calls all fail (bad key, wrong URL…)
# instead of burning through the whole sample.
FAIL_FAST_AFTER = 8
RAW_OUTPUT_LIMIT = 500
NO_ANSWER = "(no answer)"
# Typical size of {"label": "...", "confidence": 0.9} in tokens.
LLM_EST_OUTPUT_TOKENS = 18

_stop_requests: set[int] = set()
_stop_lock = threading.Lock()


def request_stop(comparison_id: int) -> None:
    with _stop_lock:
        _stop_requests.add(comparison_id)


def _clear_stop(comparison_id: int) -> None:
    with _stop_lock:
        _stop_requests.discard(comparison_id)


def _stop_requested(comparison_id: int) -> bool:
    with _stop_lock:
        return comparison_id in _stop_requests


def _utcnow() -> datetime:
    return datetime.now(timezone.utc).replace(tzinfo=None)


# ── Sampling ────────────────────────────────────────────────────────────


def select_items(
    items: list[tuple[int, str]],
    sample_size: Optional[int],
    sampling: str = "stratified",
    seed: int = 42,
) -> list[int]:
    """Pick the row ids a comparison will evaluate.

    ``items`` is ``[(item_id, expected_label), …]``. ``stratified`` keeps the
    label distribution of the full dataset (largest-remainder allocation),
    ``random`` samples uniformly, ``first`` takes rows in dataset order.
    """
    ids = sorted(i for i, _ in items)
    if not sample_size or sample_size >= len(ids) or sampling == "all":
        return ids
    if sample_size <= 0:
        raise ValueError("sample_size must be positive")
    rng = random.Random(seed)
    if sampling == "first":
        return ids[:sample_size]
    if sampling == "random":
        return sorted(rng.sample(ids, sample_size))
    if sampling != "stratified":
        raise ValueError(f"Unknown sampling strategy: {sampling}")

    by_label: dict[str, list[int]] = defaultdict(list)
    for item_id, label in sorted(items):
        by_label[label].append(item_id)
    total = len(ids)
    quotas = {label: sample_size * len(group) / total for label, group in by_label.items()}
    alloc = {label: int(math.floor(q)) for label, q in quotas.items()}
    remainder = sample_size - sum(alloc.values())
    for label in sorted(quotas, key=lambda l: (quotas[l] - alloc[l], l), reverse=True)[:remainder]:
        alloc[label] += 1
    chosen: list[int] = []
    for label in sorted(by_label):
        group = by_label[label]
        chosen.extend(rng.sample(group, min(alloc[label], len(group))))
    return sorted(chosen)


# ── Pricing & estimates ─────────────────────────────────────────────────


def default_prices(kind: str, provider: Provider, model: str) -> tuple[Optional[float], Optional[float], str]:
    """Suggested ``(input $/1M, output $/1M, source)`` for a model.

    Returns ``(None, None, "unknown")`` when no price is known — the caller
    then shows "set a price" in the UI instead of inventing a number.
    """
    ptype = provider.provider_type
    if kind == "decision":
        pricing = lookup_decision_pricing(ptype, model)
        if not pricing:
            return None, None, "unknown"
        vendor = "TypeSafe" if ptype == "typesafe" else "OpenAI"
        return pricing["prompt"], pricing["completion"], f"{vendor} list price"

    if ptype in ("ollama", "claude_code"):
        return 0.0, 0.0, "local"
    pricing = lookup_pricing(model)
    if not pricing:
        return None, None, "unknown"
    prompt, completion = pricing["prompt"], pricing["completion"]
    source = "price table"
    from app.services.llm_factory import flex_supported_for

    if (provider.extra_config or {}).get("flex_tier") and flex_supported_for(ptype, model):
        prompt, completion = prompt * FLEX_DISCOUNT, completion * FLEX_DISCOUNT
        source = "price table (flex tier)"
    return prompt, completion, source


def cost_of(input_tokens: int, output_tokens: int, in_price: Optional[float], out_price: Optional[float]) -> Optional[float]:
    if in_price is None and out_price is None:
        return None
    return ((input_tokens * (in_price or 0.0)) + (output_tokens * (out_price or 0.0))) / 1_000_000


def estimate_tokens(kind: str, task: str, labels: list[dict], texts: Iterable[str]) -> tuple[int, int]:
    """Estimate ``(input_tokens, output_tokens)`` for classifying ``texts``."""
    texts = list(texts)
    if kind == "decision":
        return sum(estimate_request_tokens(t, task, labels) for t in texts), 0
    system, _ = build_messages(task, labels, "")
    overhead = len(system) + 40
    input_tokens = sum((overhead + len(t)) // 4 for t in texts)
    return input_tokens, LLM_EST_OUTPUT_TOKENS * len(texts)


# ── Metrics ─────────────────────────────────────────────────────────────


def _percentile(values: list[float], pct: float) -> Optional[float]:
    if not values:
        return None
    ordered = sorted(values)
    k = (len(ordered) - 1) * pct
    lo, hi = math.floor(k), math.ceil(k)
    if lo == hi:
        return ordered[int(k)]
    return ordered[lo] + (ordered[hi] - ordered[lo]) * (k - lo)


def _mean(values: list[float]) -> Optional[float]:
    return sum(values) / len(values) if values else None


def compute_metrics(predictions: list[DecisionPrediction], label_names: list[str]) -> dict:
    """Aggregate per-item predictions into the fields of a model result."""
    total = len(predictions)
    correct = sum(1 for p in predictions if p.is_correct)
    failed = sum(1 for p in predictions if p.status != "ok")
    incorrect = total - correct - failed

    support = Counter(p.expected_label for p in predictions)
    predicted = Counter(p.predicted_label for p in predictions if p.status == "ok")
    true_pos = Counter(p.expected_label for p in predictions if p.is_correct)
    confusion: dict[str, dict[str, int]] = defaultdict(lambda: defaultdict(int))
    for p in predictions:
        confusion[p.expected_label][p.predicted_label if p.status == "ok" else NO_ANSWER] += 1

    per_label = {}
    f1s = []
    for label in label_names:
        tp, sup, pred = true_pos[label], support[label], predicted[label]
        precision = tp / pred if pred else None
        recall = tp / sup if sup else None
        if precision is not None and recall is not None and (precision + recall) > 0:
            f1 = 2 * precision * recall / (precision + recall)
        elif sup:
            f1 = 0.0
        else:
            f1 = None
        if sup:
            f1s.append(f1 or 0.0)
        per_label[label] = {
            "support": sup,
            "correct": tp,
            "predicted": pred,
            "precision": precision,
            "recall": recall,
            "f1": f1,
        }

    latencies = [p.latency_ms for p in predictions if p.latency_ms is not None and p.status != "error"]
    confidences = [p.confidence for p in predictions if p.confidence is not None]
    costs = [p.cost for p in predictions if p.cost is not None]

    return {
        "total": total,
        "processed": total,
        "correct": correct,
        "incorrect": incorrect,
        "failed": failed,
        "accuracy": correct / total if total else None,
        "macro_f1": _mean(f1s),
        "input_tokens": sum(p.input_tokens or 0 for p in predictions),
        "output_tokens": sum(p.output_tokens or 0 for p in predictions),
        "total_cost": sum(costs) if costs else None,
        "avg_latency_ms": _mean(latencies),
        "p50_latency_ms": _percentile(latencies, 0.5),
        "p95_latency_ms": _percentile(latencies, 0.95),
        "avg_confidence": _mean(confidences),
        "avg_confidence_correct": _mean([p.confidence for p in predictions if p.is_correct and p.confidence is not None]),
        "avg_confidence_incorrect": _mean([p.confidence for p in predictions if not p.is_correct and p.confidence is not None]),
        "per_label": per_label,
        "confusion": {k: dict(v) for k, v in confusion.items()},
    }


# ── Classifiers ─────────────────────────────────────────────────────────


@dataclass
class Outcome:
    predicted: Optional[str] = None
    status: str = "ok"  # ok | invalid | error
    confidence: Optional[float] = None
    input_tokens: int = 0
    output_tokens: int = 0
    tokens_estimated: bool = False
    latency_ms: Optional[float] = None
    raw: Optional[str] = None
    error: Optional[str] = None


class _DecisionClassifier:
    def __init__(self, provider: Provider, model: str, task: str, labels: list[dict], concurrency: int):
        self.client = DecisionClient(provider, model)
        self.task = task
        self.labels = labels
        self.label_names = [l["name"] for l in labels]
        self.concurrency = concurrency
        self.http = None

    async def __aenter__(self):
        self.http = self.client.new_http_client(self.concurrency)
        return self

    async def __aexit__(self, *exc):
        if self.http is not None:
            await self.http.aclose()

    async def classify(self, text: str) -> Outcome:
        answer = await self.client.decide(self.http, text, self.task, self.labels)
        label = answer.choice if answer.choice in self.label_names else None
        if label is None and answer.choice:
            lowered = {name.lower(): name for name in self.label_names}
            label = lowered.get(answer.choice.strip().lower())
        raw = str(answer.raw.get("answers") if isinstance(answer.raw, dict) else answer.raw)
        return Outcome(
            predicted=label,
            status="ok" if label else "invalid",
            confidence=answer.confidence,
            input_tokens=answer.input_tokens,
            output_tokens=answer.output_tokens,
            tokens_estimated=answer.tokens_estimated,
            latency_ms=answer.latency_ms,
            raw=raw[:RAW_OUTPUT_LIMIT],
            error=None if label else (
                f"Model refused: {answer.refusal}" if answer.refusal
                else f"Answer {answer.choice!r} is not one of the dataset labels"
            ),
        )


class _LLMClassifier:
    def __init__(self, db: Session, provider: Provider, model: str, task: str, labels: list[dict], temperature: Optional[float]):
        from app.services.llm_factory import get_llm

        fmt = "json" if provider.provider_type == "ollama" else None
        self.llm = get_llm(db, provider_id=provider.id, model=model, temperature=temperature, format=fmt, isolated=True)
        self.task = task
        self.labels = labels
        self.label_names = [l["name"] for l in labels]

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return None

    async def classify(self, text: str) -> Outcome:
        from langchain_core.messages import HumanMessage, SystemMessage

        system, user = build_messages(self.task, self.labels, text)
        started = time.perf_counter()
        response = await asyncio.wait_for(
            self.llm.ainvoke([SystemMessage(content=system), HumanMessage(content=user)]),
            timeout=LLM_CALL_TIMEOUT_S,
        )
        latency = (time.perf_counter() - started) * 1000
        content = response.content if hasattr(response, "content") else str(response)
        if isinstance(content, list):  # Anthropic-style content blocks
            content = "".join(
                block.get("text", "") if isinstance(block, dict) else str(block) for block in content
            )
        tokens = extract_llm_token_usage(response)
        estimated = False
        if not tokens["total_tokens"]:
            tokens = {
                "prompt_tokens": (len(system) + len(user)) // 4,
                "completion_tokens": max(1, len(content) // 4),
            }
            estimated = True
        label, confidence = parse_answer(content, self.label_names)
        return Outcome(
            predicted=label,
            status="ok" if label else "invalid",
            confidence=confidence,
            input_tokens=tokens["prompt_tokens"],
            output_tokens=tokens["completion_tokens"],
            tokens_estimated=estimated,
            latency_ms=latency,
            raw=content[:RAW_OUTPUT_LIMIT],
            error=None if label else "Could not map the answer to exactly one dataset label",
        )


def _build_classifier(db: Session, result: DecisionModelResult, comp: DecisionComparison, concurrency: int):
    provider = db.query(Provider).filter(Provider.id == result.provider_id).first()
    if not provider:
        raise ValueError(f"Provider #{result.provider_id} no longer exists")
    if not provider.is_active:
        raise ValueError(f"Provider '{provider.name}' is inactive")
    if result.kind == "decision":
        if provider.provider_type not in DECISION_PROVIDER_TYPES:
            raise ValueError(f"Provider '{provider.name}' does not serve decision models")
        return _DecisionClassifier(provider, result.model_name, comp.task, comp.labels, concurrency)
    temperature = (comp.config or {}).get("temperature", 0.0)
    return _LLMClassifier(db, provider, result.model_name, comp.task, comp.labels, temperature)


# ── Runner ──────────────────────────────────────────────────────────────


def run_comparison_sync(comparison_id: int) -> None:
    """Entry point for FastAPI BackgroundTasks (runs in a worker thread)."""
    asyncio.run(run_comparison(comparison_id))


async def run_comparison(comparison_id: int) -> None:
    db = SessionLocal()
    try:
        comp = db.query(DecisionComparison).filter(DecisionComparison.id == comparison_id).first()
        if not comp:
            return
        comp.status = "running"
        comp.started_at = comp.started_at or _utcnow()
        comp.error_message = None
        db.commit()

        rows = (
            db.query(DecisionDatasetItem.id, DecisionDatasetItem.text, DecisionDatasetItem.expected_label)
            .filter(DecisionDatasetItem.id.in_(comp.item_ids or []))
            .order_by(DecisionDatasetItem.id)
            .all()
        )
        items = [(r.id, r.text, r.expected_label) for r in rows]
        pending = [r for r in comp.model_results if r.status != "completed"]
        concurrency = max(1, min(int((comp.config or {}).get("concurrency") or DEFAULT_CONCURRENCY), MAX_CONCURRENCY))

        # Models run concurrently; each has its own concurrency budget. All
        # DB writes happen in synchronous blocks on this single session, so
        # coroutines never interleave inside a transaction.
        await asyncio.gather(*[
            _run_model_safe(db, comp, result, items, concurrency) for result in pending
        ])

        db.refresh(comp)
        statuses = [r.status for r in comp.model_results]
        if _stop_requested(comparison_id) or comp.status == "stopping":
            comp.status = "stopped"
        elif statuses and all(s == "failed" for s in statuses):
            comp.status = "failed"
            comp.error_message = "All models failed — check provider credentials and endpoints."
        else:
            comp.status = "completed"
        comp.completed_at = _utcnow()
        db.commit()
    except Exception as e:
        logger.exception("Comparison %s crashed", comparison_id)
        db.rollback()
        comp = db.query(DecisionComparison).filter(DecisionComparison.id == comparison_id).first()
        if comp:
            comp.status = "failed"
            comp.error_message = str(e)
            comp.completed_at = _utcnow()
            db.commit()
    finally:
        _clear_stop(comparison_id)
        db.close()


async def _run_model_safe(db, comp, result, items, concurrency) -> None:
    """Run one model; an unexpected crash fails that model, not the run."""
    result_id = result.id
    try:
        await _run_model(db, comp, result, items, concurrency)
    except Exception as e:
        logger.exception("Model result %s crashed", result_id)
        db.rollback()
        res = db.get(DecisionModelResult, result_id)
        if res:
            res.status = "failed"
            res.error_message = f"{type(e).__name__}: {e}"
            res.completed_at = _utcnow()
            db.commit()


def _should_stop(db: Session, comparison_id: int) -> bool:
    if _stop_requested(comparison_id):
        return True
    status = db.query(DecisionComparison.status).filter(DecisionComparison.id == comparison_id).scalar()
    return status in ("stopping", "stopped")


async def _run_model(
    db: Session,
    comp: DecisionComparison,
    result: DecisionModelResult,
    items: list[tuple[int, str, str]],
    concurrency: int,
) -> None:
    comparison_id = comp.id
    result_id = result.id
    label_names = [l["name"] for l in comp.labels]
    done_ids = {
        row.item_id for row in
        db.query(DecisionPrediction.item_id).filter(DecisionPrediction.model_result_id == result_id).all()
    }
    todo = [it for it in items if it[0] not in done_ids]

    result.status = "running"
    result.error_message = None
    result.total = len(items)
    result.started_at = result.started_at or _utcnow()
    db.commit()

    in_price, out_price = result.input_price_per_million, result.output_price_per_million
    run_in_tokens = run_out_tokens = 0
    run_estimated = False
    consecutive_errors = 0
    successes = 0
    fail_fast = False
    first_error: Optional[str] = None
    aborted = asyncio.Event()
    buffer: list[DecisionPrediction] = []
    last_flush = time.monotonic()
    started = time.perf_counter()

    def flush(force: bool = False) -> None:
        nonlocal last_flush
        if not buffer or (not force and len(buffer) < FLUSH_EVERY and time.monotonic() - last_flush < 1.5):
            return
        db.add_all(buffer)
        buffer.clear()
        res = db.get(DecisionModelResult, result_id)
        res.processed = len(done_ids)
        db.commit()
        last_flush = time.monotonic()
        if _should_stop(db, comparison_id):
            aborted.set()

    try:
        classifier = _build_classifier(db, result, comp, concurrency)
    except Exception as e:
        res = db.get(DecisionModelResult, result_id)
        res.status = "failed"
        res.error_message = str(e)
        res.completed_at = _utcnow()
        db.commit()
        return

    if result.provider_type == "claude_code":
        concurrency = min(concurrency, 2)  # each call spawns a CLI subprocess
    semaphore = asyncio.Semaphore(concurrency)

    async def classify(item: tuple[int, str, str]):
        async with semaphore:
            if aborted.is_set() or _stop_requested(comparison_id):
                return item, None
            try:
                return item, await classifier.classify(item[1])
            except Exception as e:  # network error, auth error, timeout…
                message = f"{type(e).__name__}: {e}" if str(e) else type(e).__name__
                return item, Outcome(status="error", error=message[:RAW_OUTPUT_LIMIT])

    async with classifier:
        tasks = [asyncio.ensure_future(classify(it)) for it in todo]
        try:
            for fut in asyncio.as_completed(tasks):
                (item_id, _text, expected), outcome = await fut
                if outcome is None:
                    continue
                if outcome.status == "error":
                    consecutive_errors += 1
                    first_error = first_error or outcome.error
                    if consecutive_errors >= FAIL_FAST_AFTER and successes == 0:
                        fail_fast = True
                        aborted.set()
                else:
                    consecutive_errors = 0
                    successes += 1
                run_in_tokens += outcome.input_tokens
                run_out_tokens += outcome.output_tokens
                run_estimated = run_estimated or outcome.tokens_estimated
                done_ids.add(item_id)
                buffer.append(DecisionPrediction(
                    comparison_id=comparison_id,
                    model_result_id=result_id,
                    item_id=item_id,
                    expected_label=expected,
                    predicted_label=outcome.predicted,
                    status=outcome.status,
                    is_correct=outcome.status == "ok" and outcome.predicted == expected,
                    confidence=outcome.confidence,
                    latency_ms=outcome.latency_ms,
                    input_tokens=outcome.input_tokens,
                    output_tokens=outcome.output_tokens,
                    cost=cost_of(outcome.input_tokens, outcome.output_tokens, in_price, out_price),
                    error=outcome.error,
                    raw_output=outcome.raw,
                ))
                flush()
        finally:
            for t in tasks:
                if not t.done():
                    t.cancel()
            flush(force=True)

    wall_ms = (time.perf_counter() - started) * 1000
    predictions = db.query(DecisionPrediction).filter(DecisionPrediction.model_result_id == result_id).all()
    metrics = compute_metrics(predictions, label_names)
    res = db.get(DecisionModelResult, result_id)
    for key, value in metrics.items():
        setattr(res, key, value)
    res.total = len(items)
    res.tokens_estimated = bool(res.tokens_estimated or run_estimated)
    res.wall_time_ms = (res.wall_time_ms or 0.0) + wall_ms

    if fail_fast:
        res.status = "failed"
        res.error_message = f"Stopped after {consecutive_errors} consecutive errors. First error: {first_error}"
    elif len(done_ids) < len(items):
        res.status = "stopped"
    elif metrics["total"] and metrics["failed"] == metrics["total"]:
        res.status = "failed"
        res.error_message = first_error or "Every request failed"
    else:
        res.status = "completed"
    res.completed_at = _utcnow()

    if run_in_tokens or run_out_tokens:
        db.add(TokenUsageLog(
            operation="model_comparison",
            provider_name=res.provider_name or "unknown",
            model_name=res.model_name,
            model_type="decision" if res.kind == "decision" else "llm",
            prompt_tokens=run_in_tokens,
            completion_tokens=run_out_tokens,
            total_tokens=run_in_tokens + run_out_tokens,
            estimated_cost=cost_of(run_in_tokens, run_out_tokens, in_price, out_price),
            extra_metadata={
                "comparison_id": comparison_id,
                "model_result_id": result_id,
                "tokens_estimated": run_estimated,
            },
        ))
    db.commit()


def recover_interrupted(db: Session) -> int:
    """Mark comparisons left 'running' by a server restart as stopped."""
    stale = db.query(DecisionComparison).filter(DecisionComparison.status.in_(["running", "stopping"])).all()
    for comp in stale:
        comp.status = "stopped"
        for res in comp.model_results:
            if res.status == "running":
                res.status = "stopped"
    if stale:
        db.commit()
    return len(stale)
