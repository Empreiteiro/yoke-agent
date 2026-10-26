"""Model Comparison API — decision models (TypeSafe Jev, System One), text
classifiers and rule baselines vs. LLMs.

Datasets:      /api/decision/datasets…
Models:        /api/decision/models
Comparisons:   /api/decision/comparisons…
Analysis:      /api/decision/comparisons/{id}/analysis (guardrail view,
               significance, calibration, ROC, slices, policy sensitivity)
"""

import csv
import io
import json
import logging
from typing import Optional

from fastapi import APIRouter, BackgroundTasks, Depends, File, Form, HTTPException, Query, Request, UploadFile
from fastapi.responses import Response, StreamingResponse
from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.tenancy import assert_can_access, current_user_id, current_user_role, scope_query
from app.models.decision import (
    DecisionComparison, DecisionDataset, DecisionDatasetItem, DecisionModelResult, DecisionPrediction,
)
from app.models.provider import Provider
from app.models.user import ROLE_ADMIN
from app.schemas.decision import (
    AnalysisSettings, ComparisonCreate, DecisionDatasetDetail, DecisionDatasetResponse, DecisionDatasetUpdate,
    DecisionItemResponse, EstimateRequest, ModelSpec,
)
from app.services import decision_comparison as engine
from app.services import decision_stats as stats
from app.services.decision_datasets import (
    DEFAULT_TASK, MAX_UPLOAD_BYTES, TEMPLATE_CSV, DatasetParseError, export_payload, insert_items, parse_dataset,
)
from app.services.decision_models import DECISION_PROVIDER_TYPES
from app.services.llm_classifier import SYSTEM_PROMPT, USER_PROMPT
from app.services.text_classifiers import CLASSIFIER_PROVIDER_TYPES

logger = logging.getLogger(__name__)
router = APIRouter()

MAX_COMPARISON_ITEMS = 10_000


# ══════════════════════════════════════════════════════════════════════
#  Helpers
# ══════════════════════════════════════════════════════════════════════


def _visible_datasets(request: Request, db: Session):
    q = db.query(DecisionDataset)
    user_id = current_user_id(request)
    if user_id is not None and current_user_role(request) != ROLE_ADMIN:
        q = q.filter(or_(
            DecisionDataset.is_builtin.is_(True),
            DecisionDataset.user_id == user_id,
            DecisionDataset.user_id.is_(None),
        ))
    return q


def _get_dataset(request: Request, db: Session, dataset_id: int) -> DecisionDataset:
    ds = db.query(DecisionDataset).filter(DecisionDataset.id == dataset_id).first()
    if not ds:
        raise HTTPException(404, "Dataset not found")
    if not ds.is_builtin:
        assert_can_access(request, ds)
    return ds


def _get_comparison(request: Request, db: Session, comparison_id: int) -> DecisionComparison:
    comp = db.query(DecisionComparison).filter(DecisionComparison.id == comparison_id).first()
    if not comp:
        raise HTTPException(404, "Comparison not found")
    assert_can_access(request, comp)
    return comp


def _ratio(num: Optional[float], den: Optional[float]) -> Optional[float]:
    if num is None or not den:
        return None
    return num / den


def _result_dict(res: DecisionModelResult) -> dict:
    total = res.total or 0
    evaluated = (res.correct or 0) + (res.incorrect or 0) + (res.failed or 0)
    config = res.config or {}
    return {
        "id": res.id,
        "position": res.position,
        "kind": res.kind,
        "provider_id": res.provider_id,
        "provider_name": res.provider_name,
        "provider_type": res.provider_type,
        "model_name": res.model_name,
        "display_name": res.display_name or res.model_name,
        "input_price_per_million": res.input_price_per_million,
        "output_price_per_million": res.output_price_per_million,
        "infra_cost_per_hour": res.infra_cost_per_hour,
        "pricing_known": (
            res.input_price_per_million is not None
            or res.output_price_per_million is not None
            or res.infra_cost_per_hour is not None
        ),
        "variant": res.variant,
        "policy_hash": res.policy_hash,
        "config": config,
        "deployment": config.get("deployment") or {},
        "status": res.status,
        "error_message": res.error_message,
        "total": total,
        "processed": res.processed or 0,
        "evaluated": evaluated,
        "correct": res.correct or 0,
        "incorrect": res.incorrect or 0,
        "failed": res.failed or 0,
        "errors": (res.incorrect or 0) + (res.failed or 0),
        "accuracy": res.accuracy,
        "error_rate": _ratio((res.incorrect or 0) + (res.failed or 0), evaluated),
        "incorrect_rate": _ratio(res.incorrect or 0, evaluated),
        "failure_rate": _ratio(res.failed or 0, evaluated),
        "macro_f1": res.macro_f1,
        "input_tokens": res.input_tokens or 0,
        "output_tokens": res.output_tokens or 0,
        "tokens_estimated": bool(res.tokens_estimated),
        "token_cost": res.token_cost,
        "infra_cost": res.infra_cost,
        "total_cost": res.total_cost,
        "cost_per_1k": _ratio(res.total_cost * 1000 if res.total_cost is not None else None, evaluated),
        "cost_per_correct": _ratio(res.total_cost, res.correct),
        "avg_latency_ms": res.avg_latency_ms,
        "p50_latency_ms": res.p50_latency_ms,
        "p90_latency_ms": res.p90_latency_ms,
        "p95_latency_ms": res.p95_latency_ms,
        "p99_latency_ms": res.p99_latency_ms,
        "latency_std_ms": res.latency_std_ms,
        "wall_time_ms": res.wall_time_ms,
        "throughput_rps": _ratio(evaluated, res.wall_time_ms / 1000 if res.wall_time_ms else None),
        "avg_attempts": res.avg_attempts,
        "retried": res.retried or 0,
        "avg_confidence": res.avg_confidence,
        "avg_confidence_correct": res.avg_confidence_correct,
        "avg_confidence_incorrect": res.avg_confidence_incorrect,
        "per_label": res.per_label or {},
        "confusion": res.confusion or {},
        "started_at": res.started_at,
        "completed_at": res.completed_at,
    }


def _rank(results: list[dict]) -> None:
    """Rank by accuracy (desc), then cost (asc); add share-of-cost and
    relative cost vs. the cheapest priced model."""
    scored = [r for r in results if r["accuracy"] is not None]
    scored.sort(key=lambda r: (-(r["accuracy"] or 0), r["total_cost"] if r["total_cost"] is not None else float("inf")))
    for idx, r in enumerate(scored, start=1):
        r["rank"] = idx
    for r in results:
        r.setdefault("rank", None)
    priced = [r["total_cost"] for r in results if r["total_cost"] is not None]
    total_cost = sum(priced) if priced else None
    cheapest = min((c for c in priced if c > 0), default=None)
    for r in results:
        r["cost_share"] = _ratio(r["total_cost"], total_cost)
        r["cost_vs_cheapest"] = _ratio(r["total_cost"], cheapest)


def _comparison_dict(comp: DecisionComparison, include_details: bool = True) -> dict:
    results = [_result_dict(r) for r in comp.model_results]
    _rank(results)
    item_count = len(comp.item_ids or [])
    processed = sum(r["processed"] for r in results)
    planned = item_count * len(results)
    priced = [r["total_cost"] for r in results if r["total_cost"] is not None]
    ranked = sorted([r for r in results if r["rank"]], key=lambda r: r["rank"])
    best = ranked[0] if ranked else None
    data = {
        "id": comp.id,
        "name": comp.name,
        "dataset_id": comp.dataset_id,
        "dataset_name": comp.dataset_name,
        "status": comp.status,
        "sampling": comp.sampling,
        "sample_size": comp.sample_size,
        "seed": comp.seed,
        "item_count": item_count,
        "model_count": len(results),
        "config": comp.config or {},
        "error_message": comp.error_message,
        "created_at": comp.created_at,
        "started_at": comp.started_at,
        "completed_at": comp.completed_at,
        "progress": {"processed": processed, "total": planned, "ratio": _ratio(processed, planned) or 0.0},
        "total_cost": sum(priced) if priced else None,
        "best_model": (
            {"display_name": best["display_name"], "accuracy": best["accuracy"], "kind": best["kind"]}
            if best else None
        ),
    }
    if include_details:
        data["task"] = comp.task
        data["labels"] = comp.labels or []
        data["models"] = results
    else:
        data["models"] = [
            {k: r[k] for k in ("id", "display_name", "kind", "variant", "status", "accuracy", "total_cost", "rank", "processed", "total")}
            for r in results
        ]
    return data


def _resolve_specs(
    db: Session, specs: list[ModelSpec], label_names: list[str],
) -> list[tuple[ModelSpec, Optional[Provider], Optional[float], Optional[float]]]:
    resolved = []
    for spec in specs:
        unknown = sorted(spec.referenced_labels() - set(label_names))
        if unknown:
            raise HTTPException(400, f"Model '{spec.model}' refers to labels not in the dataset: {', '.join(unknown)}")
        provider = None
        if spec.kind != "rules":
            provider = db.query(Provider).filter(Provider.id == spec.provider_id).first()
            if not provider:
                raise HTTPException(400, f"Provider #{spec.provider_id} not found")
            if not provider.is_active:
                raise HTTPException(400, f"Provider '{provider.name}' is inactive")
        if spec.kind == "decision":
            if provider.provider_type not in DECISION_PROVIDER_TYPES or not provider.supports_decision:
                raise HTTPException(400, f"Provider '{provider.name}' does not serve decision models")
        elif spec.kind == "classifier":
            if provider.provider_type not in CLASSIFIER_PROVIDER_TYPES or not provider.supports_decision:
                raise HTTPException(400, f"Provider '{provider.name}' does not serve text classifiers")
        elif spec.kind == "llm" and not provider.supports_llm:
            raise HTTPException(400, f"Provider '{provider.name}' does not serve LLMs")
        in_price, out_price = spec.input_price_per_million, spec.output_price_per_million
        if in_price is None and out_price is None:
            in_price, out_price, _source = engine.default_prices(spec.kind, provider, spec.model)
        resolved.append((spec, provider, in_price, out_price))
    return resolved


def _sample_ids(db: Session, dataset_id: int, sample_size: Optional[int], sampling: str, seed: int) -> list[int]:
    rows = (
        db.query(DecisionDatasetItem.id, DecisionDatasetItem.expected_label)
        .filter(DecisionDatasetItem.dataset_id == dataset_id)
        .all()
    )
    if not rows:
        raise HTTPException(400, "The dataset has no rows")
    try:
        return engine.select_items([(r.id, r.expected_label) for r in rows], sample_size, sampling, seed)
    except ValueError as e:
        raise HTTPException(400, str(e))


# ══════════════════════════════════════════════════════════════════════
#  Datasets
# ══════════════════════════════════════════════════════════════════════


@router.get("/datasets", response_model=list[DecisionDatasetResponse])
def list_datasets(request: Request, db: Session = Depends(get_db)):
    rows = _visible_datasets(request, db).all()
    # Built-ins in seed order, then the user's own datasets newest first.
    builtins = sorted((d for d in rows if d.is_builtin), key=lambda d: d.id)
    custom = sorted((d for d in rows if not d.is_builtin), key=lambda d: d.id, reverse=True)
    return builtins + custom


@router.get("/dataset-template")
def dataset_template():
    return Response(
        TEMPLATE_CSV,
        media_type="text/csv",
        headers={"Content-Disposition": 'attachment; filename="decision_dataset_template.csv"'},
    )


@router.post("/datasets/upload")
async def upload_dataset(
    request: Request,
    file: UploadFile = File(...),
    name: Optional[str] = Form(None),
    description: Optional[str] = Form(None),
    task: Optional[str] = Form(None),
    text_column: Optional[str] = Form(None),
    label_column: Optional[str] = Form(None),
    label_descriptions: Optional[str] = Form(None, description='JSON object {"label": "description"}'),
    dry_run: bool = Form(False),
    db: Session = Depends(get_db),
):
    """Upload a CSV / TSV / JSON / JSONL file as a custom dataset.

    With ``dry_run=true`` nothing is saved: the response describes the
    detected columns, labels and warnings so the UI can show a preview.
    """
    content = await file.read(MAX_UPLOAD_BYTES + 1)
    descriptions = None
    if label_descriptions:
        try:
            descriptions = json.loads(label_descriptions)
        except ValueError:
            raise HTTPException(400, "label_descriptions must be a JSON object")
        if not isinstance(descriptions, dict):
            raise HTTPException(400, "label_descriptions must be a JSON object")
    try:
        parsed = parse_dataset(
            file.filename or "upload.csv",
            content,
            text_column=text_column or None,
            label_column=label_column or None,
            label_descriptions=descriptions,
            allow_unmapped=dry_run,
        )
    except DatasetParseError as e:
        raise HTTPException(400, str(e))

    items = parsed.pop("items")
    if dry_run:
        return {"dry_run": True, **parsed}

    stem = (file.filename or "custom dataset").rsplit(".", 1)[0]
    dataset = DecisionDataset(
        user_id=current_user_id(request),
        name=(name or parsed.get("name") or stem).strip()[:255],
        description=description or parsed.get("description"),
        language=parsed.get("language"),
        task=(task or parsed.get("task") or DEFAULT_TASK).strip(),
        labels=parsed["labels"],
        is_builtin=False,
        source_filename=file.filename,
        item_count=len(items),
    )
    db.add(dataset)
    db.flush()
    insert_items(db, dataset.id, items)
    db.commit()
    db.refresh(dataset)
    return {"dry_run": False, "dataset": DecisionDatasetResponse.model_validate(dataset), **parsed}


@router.get("/datasets/{dataset_id}", response_model=DecisionDatasetDetail)
def get_dataset(dataset_id: int, request: Request, db: Session = Depends(get_db)):
    ds = _get_dataset(request, db, dataset_id)
    label_counts = dict(
        db.query(DecisionDatasetItem.expected_label, func.count(DecisionDatasetItem.id))
        .filter(DecisionDatasetItem.dataset_id == ds.id)
        .group_by(DecisionDatasetItem.expected_label)
        .all()
    )
    difficulty_counts = dict(
        db.query(DecisionDatasetItem.difficulty, func.count(DecisionDatasetItem.id))
        .filter(DecisionDatasetItem.dataset_id == ds.id, DecisionDatasetItem.difficulty.isnot(None))
        .group_by(DecisionDatasetItem.difficulty)
        .all()
    )
    detail = DecisionDatasetDetail.model_validate(ds)
    detail.label_counts = label_counts
    detail.difficulty_counts = difficulty_counts
    return detail


@router.get("/datasets/{dataset_id}/items")
def list_dataset_items(
    dataset_id: int,
    request: Request,
    label: Optional[str] = None,
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    ds = _get_dataset(request, db, dataset_id)
    q = db.query(DecisionDatasetItem).filter(DecisionDatasetItem.dataset_id == ds.id)
    if label:
        q = q.filter(DecisionDatasetItem.expected_label == label)
    if search:
        q = q.filter(DecisionDatasetItem.text.ilike(f"%{search}%"))
    total = q.count()
    rows = q.order_by(DecisionDatasetItem.id).offset(offset).limit(limit).all()
    return {"total": total, "items": [DecisionItemResponse.model_validate(r) for r in rows]}


@router.put("/datasets/{dataset_id}", response_model=DecisionDatasetResponse)
def update_dataset(dataset_id: int, body: DecisionDatasetUpdate, request: Request, db: Session = Depends(get_db)):
    ds = _get_dataset(request, db, dataset_id)
    if ds.is_builtin:
        raise HTTPException(403, "Built-in datasets are read-only — duplicate it to customize.")
    if body.labels is not None:
        current = {l["name"] for l in ds.labels or []}
        incoming = [l.model_dump() for l in body.labels]
        if {l["name"] for l in incoming} != current:
            raise HTTPException(400, "Label names can't change — only their descriptions.")
        ds.labels = incoming
    for field in ("name", "description", "task"):
        value = getattr(body, field)
        if value is not None:
            setattr(ds, field, value)
    db.commit()
    db.refresh(ds)
    return ds


@router.post("/datasets/{dataset_id}/duplicate", response_model=DecisionDatasetResponse)
def duplicate_dataset(dataset_id: int, request: Request, db: Session = Depends(get_db)):
    src = _get_dataset(request, db, dataset_id)
    copy = DecisionDataset(
        user_id=current_user_id(request),
        name=f"{src.name} (copy)"[:255],
        description=src.description,
        language=src.language,
        task=src.task,
        labels=[dict(l) for l in (src.labels or [])],
        is_builtin=False,
        source_filename=src.source_filename,
        item_count=src.item_count,
    )
    db.add(copy)
    db.flush()
    rows = (
        db.query(DecisionDatasetItem.text, DecisionDatasetItem.expected_label, DecisionDatasetItem.difficulty)
        .filter(DecisionDatasetItem.dataset_id == src.id)
        .order_by(DecisionDatasetItem.id)
        .all()
    )
    insert_items(db, copy.id, [{"text": r.text, "label": r.expected_label, "difficulty": r.difficulty} for r in rows])
    db.commit()
    db.refresh(copy)
    return copy


@router.delete("/datasets/{dataset_id}")
def delete_dataset(dataset_id: int, request: Request, db: Session = Depends(get_db)):
    ds = _get_dataset(request, db, dataset_id)
    if ds.is_builtin:
        raise HTTPException(403, "Built-in datasets can't be deleted")
    comparison_ids = [c.id for c in db.query(DecisionComparison.id).filter(DecisionComparison.dataset_id == ds.id)]
    if comparison_ids:
        running = db.query(DecisionComparison.id).filter(
            DecisionComparison.id.in_(comparison_ids),
            DecisionComparison.status.in_(["running", "stopping"]),
        ).first()
        if running:
            raise HTTPException(409, "A comparison on this dataset is still running — stop it first.")
        _delete_comparisons(db, comparison_ids)
    db.query(DecisionDatasetItem).filter(DecisionDatasetItem.dataset_id == ds.id).delete(synchronize_session=False)
    db.delete(ds)
    db.commit()
    return {"detail": "Dataset deleted", "deleted_comparisons": len(comparison_ids)}


@router.get("/datasets/{dataset_id}/export")
def export_dataset(dataset_id: int, request: Request, db: Session = Depends(get_db)):
    ds = _get_dataset(request, db, dataset_id)
    items = db.query(DecisionDatasetItem).filter(DecisionDatasetItem.dataset_id == ds.id).order_by(DecisionDatasetItem.id).all()
    payload = json.dumps(export_payload(ds, items), ensure_ascii=False, indent=1)
    filename = (ds.slug or f"decision_dataset_{ds.id}") + ".json"
    return Response(payload, media_type="application/json", headers={"Content-Disposition": f'attachment; filename="{filename}"'})


# ══════════════════════════════════════════════════════════════════════
#  Models
# ══════════════════════════════════════════════════════════════════════


@router.get("/models")
def list_comparable_models(db: Session = Depends(get_db)):
    """Every decision model, text classifier and LLM from active providers,
    with the price that will be used for cost unless the user overrides it,
    plus the default LLM prompt templates (for per-model overrides)."""
    decision_models, classifier_models, llm_models = [], [], []
    for p in db.query(Provider).filter(Provider.is_active.is_(True)).order_by(Provider.id).all():
        if p.supports_decision and p.provider_type in (DECISION_PROVIDER_TYPES | CLASSIFIER_PROVIDER_TYPES):
            kind = "classifier" if p.provider_type in CLASSIFIER_PROVIDER_TYPES else "decision"
            for model in p.decision_models or []:
                in_price, out_price, source = engine.default_prices(kind, p, model)
                (classifier_models if kind == "classifier" else decision_models).append({
                    "kind": kind, "provider_id": p.id, "provider_name": p.name,
                    "provider_type": p.provider_type, "model": model,
                    "is_default": model == p.default_decision_model,
                    "input_price_per_million": in_price, "output_price_per_million": out_price,
                    "pricing_source": source,
                })
        if p.supports_llm:
            for model in p.llm_models or []:
                in_price, out_price, source = engine.default_prices("llm", p, model)
                llm_models.append({
                    "kind": "llm", "provider_id": p.id, "provider_name": p.name,
                    "provider_type": p.provider_type, "model": model,
                    "is_default": model == p.default_llm_model,
                    "input_price_per_million": in_price, "output_price_per_million": out_price,
                    "pricing_source": source,
                })
    return {
        "decision_models": decision_models,
        "classifier_models": classifier_models,
        "llm_models": llm_models,
        "default_prompts": {"system": SYSTEM_PROMPT, "user": USER_PROMPT},
    }


# ══════════════════════════════════════════════════════════════════════
#  Comparisons
# ══════════════════════════════════════════════════════════════════════


@router.post("/comparisons/estimate")
def estimate_comparison(body: EstimateRequest, request: Request, db: Session = Depends(get_db)):
    """Projected tokens and cost per model before running anything."""
    ds = _get_dataset(request, db, body.dataset_id)
    ids = _sample_ids(db, ds.id, body.sample_size, body.sampling, body.seed)
    texts = [t for (t,) in db.query(DecisionDatasetItem.text).filter(DecisionDatasetItem.id.in_(ids))]
    label_names = [l["name"] for l in ds.labels or []]
    estimates = []
    for spec, provider, in_price, out_price in _resolve_specs(db, body.models, label_names):
        config = spec.snapshot()
        task, labels = engine.effective_policy(ds.task, ds.labels or [], config)
        in_tok, out_tok = engine.estimate_tokens(spec.kind, task, labels, texts, config)
        estimates.append({
            "kind": spec.kind,
            "provider_id": provider.id if provider else None,
            "model": spec.model,
            "variant": spec.variant,
            "display_name": spec.display_name or _default_display_name(spec, provider),
            "items": len(ids),
            "input_tokens": in_tok,
            "output_tokens": out_tok,
            "input_price_per_million": in_price,
            "output_price_per_million": out_price,
            "estimated_cost": engine.cost_of(in_tok, out_tok, in_price, out_price),
            "infra_cost_per_hour": spec.infra_cost_per_hour,
        })
    priced = [e["estimated_cost"] for e in estimates if e["estimated_cost"] is not None]
    return {
        "items": len(ids),
        "requests": len(ids) * len(estimates),
        "estimated_total_cost": sum(priced) if priced else None,
        "models": estimates,
    }


def _default_display_name(spec: ModelSpec, provider: Optional[Provider]) -> str:
    source = provider.name if provider else "rules"
    name = f"{spec.model} ({source})"
    return f"{name} · {spec.variant}" if spec.variant else name


@router.post("/comparisons", status_code=201)
def create_comparison(body: ComparisonCreate, request: Request, bg: BackgroundTasks, db: Session = Depends(get_db)):
    ds = _get_dataset(request, db, body.dataset_id)
    label_names = [l["name"] for l in ds.labels or []]
    resolved = _resolve_specs(db, body.models, label_names)
    if body.analysis and body.analysis.positive_labels is not None:
        unknown = sorted(set(body.analysis.positive_labels) - set(label_names))
        if unknown:
            raise HTTPException(400, f"Positive labels not in the dataset: {', '.join(unknown)}")
    ids = _sample_ids(db, ds.id, body.sample_size, body.sampling, body.seed)
    if len(ids) > MAX_COMPARISON_ITEMS:
        raise HTTPException(400, f"Comparisons are limited to {MAX_COMPARISON_ITEMS:,} rows — set a sample size.")

    comp = DecisionComparison(
        user_id=current_user_id(request),
        name=(body.name or f"{ds.name} — {len(resolved)} models").strip()[:255],
        dataset_id=ds.id,
        dataset_name=ds.name,
        task=ds.task,
        labels=ds.labels or [],
        status="pending",
        sampling=body.sampling,
        sample_size=body.sample_size,
        seed=body.seed,
        item_ids=ids,
        config={
            "concurrency": 1 if body.latency_mode else body.concurrency,
            "temperature": body.temperature,
            "latency_mode": body.latency_mode,
            "warmup": body.warmup,
            **({"analysis": body.analysis.model_dump()} if body.analysis else {}),
        },
    )
    db.add(comp)
    db.flush()
    for position, (spec, provider, in_price, out_price) in enumerate(resolved):
        config = spec.snapshot()
        db.add(DecisionModelResult(
            comparison_id=comp.id,
            position=position,
            kind=spec.kind,
            provider_id=provider.id if provider else None,
            provider_name=provider.name if provider else "Rules",
            provider_type=provider.provider_type if provider else "rules",
            model_name=spec.model,
            display_name=spec.display_name or _default_display_name(spec, provider),
            input_price_per_million=in_price,
            output_price_per_million=out_price,
            infra_cost_per_hour=spec.infra_cost_per_hour,
            config=config,
            variant=spec.variant,
            policy_hash=engine.policy_hash(spec.kind, ds.task, ds.labels or [], config),
            total=len(ids),
        ))
    db.commit()
    db.refresh(comp)

    if body.autostart:
        comp.status = "running"
        db.commit()
        bg.add_task(engine.run_comparison_sync, comp.id)
    return _comparison_dict(comp)


@router.get("/comparisons")
def list_comparisons(request: Request, db: Session = Depends(get_db)):
    q = scope_query(request, db.query(DecisionComparison), DecisionComparison)
    return [_comparison_dict(c, include_details=False) for c in q.order_by(DecisionComparison.created_at.desc(), DecisionComparison.id.desc()).all()]


@router.get("/comparisons/{comparison_id}")
def get_comparison(comparison_id: int, request: Request, db: Session = Depends(get_db)):
    return _comparison_dict(_get_comparison(request, db, comparison_id))


@router.get("/comparisons/{comparison_id}/predictions")
def list_predictions(
    comparison_id: int,
    request: Request,
    model_result_id: Optional[int] = None,
    outcome: Optional[str] = Query(None, pattern="^(correct|incorrect|failed|errors)$"),
    expected_label: Optional[str] = None,
    predicted_label: Optional[str] = None,
    difficulty: Optional[str] = None,
    search: Optional[str] = None,
    offset: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=500),
    db: Session = Depends(get_db),
):
    comp = _get_comparison(request, db, comparison_id)
    q = (
        db.query(DecisionPrediction, DecisionDatasetItem.text, DecisionDatasetItem.difficulty)
        .join(DecisionDatasetItem, DecisionDatasetItem.id == DecisionPrediction.item_id)
        .filter(DecisionPrediction.comparison_id == comp.id)
    )
    if model_result_id:
        q = q.filter(DecisionPrediction.model_result_id == model_result_id)
    if outcome == "correct":
        q = q.filter(DecisionPrediction.is_correct.is_(True))
    elif outcome == "incorrect":
        q = q.filter(DecisionPrediction.is_correct.is_(False), DecisionPrediction.status == "ok")
    elif outcome == "failed":
        q = q.filter(DecisionPrediction.status != "ok")
    elif outcome == "errors":
        q = q.filter(DecisionPrediction.is_correct.is_(False))
    if expected_label:
        q = q.filter(DecisionPrediction.expected_label == expected_label)
    if predicted_label:
        q = q.filter(DecisionPrediction.predicted_label == predicted_label)
    if difficulty:
        q = q.filter(DecisionDatasetItem.difficulty == difficulty)
    if search:
        q = q.filter(DecisionDatasetItem.text.ilike(f"%{search}%"))
    total = q.count()
    rows = q.order_by(DecisionPrediction.item_id, DecisionPrediction.model_result_id).offset(offset).limit(limit).all()
    return {
        "total": total,
        "items": [
            {
                "id": p.id,
                "model_result_id": p.model_result_id,
                "item_id": p.item_id,
                "text": text,
                "difficulty": difficulty,
                "expected_label": p.expected_label,
                "predicted_label": p.predicted_label,
                "status": p.status,
                "is_correct": bool(p.is_correct),
                "confidence": p.confidence,
                "probabilities": p.probabilities,
                "latency_ms": p.latency_ms,
                "attempts": p.attempts,
                "input_tokens": p.input_tokens,
                "output_tokens": p.output_tokens,
                "cost": p.cost,
                "error": p.error,
                "raw_output": p.raw_output,
            }
            for p, text, difficulty in rows
        ],
    }


def _analysis(db: Session, comp: DecisionComparison) -> dict:
    label_names = [l["name"] for l in comp.labels or []]
    settings = stats.resolve_settings(label_names, (comp.config or {}).get("analysis"))
    rows = [
        stats.PredictionRow(
            model_result_id=r.model_result_id, item_id=r.item_id, expected_label=r.expected_label,
            predicted_label=r.predicted_label, status=r.status, is_correct=bool(r.is_correct),
            confidence=r.confidence, probabilities=r.probabilities, latency_ms=r.latency_ms,
        )
        for r in db.query(
            DecisionPrediction.model_result_id, DecisionPrediction.item_id, DecisionPrediction.expected_label,
            DecisionPrediction.predicted_label, DecisionPrediction.status, DecisionPrediction.is_correct,
            DecisionPrediction.confidence, DecisionPrediction.probabilities, DecisionPrediction.latency_ms,
        ).filter(DecisionPrediction.comparison_id == comp.id)
    ]
    difficulties = dict(
        db.query(DecisionDatasetItem.id, DecisionDatasetItem.difficulty)
        .filter(DecisionDatasetItem.id.in_(comp.item_ids or []))
        .all()
    )
    results = _comparison_dict(comp)["models"]
    return stats.analyze(results, rows, label_names, difficulties, settings)


@router.get("/comparisons/{comparison_id}/analysis")
def get_analysis(comparison_id: int, request: Request, db: Session = Depends(get_db)):
    """Derived statistics: guardrail (binary) view, confidence intervals,
    paired significance tests, ROC/PR, calibration, difficulty slices and
    policy sensitivity. Computed from stored predictions on every call."""
    return _analysis(db, _get_comparison(request, db, comparison_id))


@router.put("/comparisons/{comparison_id}/analysis-settings")
def update_analysis_settings(
    comparison_id: int, body: AnalysisSettings, request: Request, db: Session = Depends(get_db),
):
    """Save how the guardrail view reads this comparison; returns the new analysis."""
    comp = _get_comparison(request, db, comparison_id)
    label_names = {l["name"] for l in comp.labels or []}
    if body.positive_labels is not None:
        unknown = sorted(set(body.positive_labels) - label_names)
        if unknown:
            raise HTTPException(400, f"Positive labels not in the dataset: {', '.join(unknown)}")
    comp.config = {**(comp.config or {}), "analysis": body.model_dump()}
    db.commit()
    db.refresh(comp)
    return _analysis(db, comp)


@router.get("/comparisons/{comparison_id}/export")
def export_comparison(comparison_id: int, request: Request, db: Session = Depends(get_db)):
    """One CSV row per dataset item, one column group per model."""
    comp = _get_comparison(request, db, comparison_id)
    results = list(comp.model_results)
    texts = dict(
        db.query(DecisionDatasetItem.id, DecisionDatasetItem.text)
        .filter(DecisionDatasetItem.id.in_(comp.item_ids or []))
        .all()
    )
    by_item: dict[int, dict[int, DecisionPrediction]] = {}
    expected: dict[int, str] = {}
    for p in db.query(DecisionPrediction).filter(DecisionPrediction.comparison_id == comp.id):
        by_item.setdefault(p.item_id, {})[p.model_result_id] = p
        expected[p.item_id] = p.expected_label

    def generate():
        buf = io.StringIO()
        writer = csv.writer(buf)
        header = ["item_id", "text", "expected_label"]
        for r in results:
            name = r.display_name or r.model_name
            header += [f"{name} | predicted", f"{name} | correct", f"{name} | confidence", f"{name} | latency_ms",
                       f"{name} | attempts", f"{name} | cost_usd"]
        writer.writerow(header)
        for item_id in comp.item_ids or []:
            preds = by_item.get(item_id, {})
            row = [item_id, texts.get(item_id, ""), expected.get(item_id, "")]
            for r in results:
                p = preds.get(r.id)
                if p is None:
                    row += ["", "", "", "", "", ""]
                else:
                    row += [
                        p.predicted_label if p.status == "ok" else f"[{p.status}]",
                        "1" if p.is_correct else "0",
                        "" if p.confidence is None else f"{p.confidence:.4f}",
                        "" if p.latency_ms is None else f"{p.latency_ms:.1f}",
                        "" if p.attempts is None else str(p.attempts),
                        "" if p.cost is None else f"{p.cost:.8f}",
                    ]
            writer.writerow(row)
            yield buf.getvalue()
            buf.seek(0)
            buf.truncate(0)

    return StreamingResponse(
        generate(),
        media_type="text/csv",
        headers={"Content-Disposition": f'attachment; filename="comparison_{comp.id}.csv"'},
    )


@router.post("/comparisons/{comparison_id}/stop")
def stop_comparison(comparison_id: int, request: Request, db: Session = Depends(get_db)):
    comp = _get_comparison(request, db, comparison_id)
    if comp.status not in ("running", "pending"):
        raise HTTPException(400, f"Comparison is {comp.status}")
    engine.request_stop(comp.id)
    comp.status = "stopping" if comp.status == "running" else "stopped"
    db.commit()
    return {"status": comp.status}


@router.post("/comparisons/{comparison_id}/resume")
def resume_comparison(comparison_id: int, request: Request, bg: BackgroundTasks, db: Session = Depends(get_db)):
    """Continue a stopped/failed comparison. Rows that errored are retried;
    rows that already have an answer are kept."""
    comp = _get_comparison(request, db, comparison_id)
    if comp.status in ("running", "stopping"):
        raise HTTPException(400, "Comparison is already running")
    unfinished = [r.id for r in comp.model_results if r.status != "completed"]
    if not unfinished:
        raise HTTPException(400, "Every model already completed")
    db.query(DecisionPrediction).filter(
        DecisionPrediction.model_result_id.in_(unfinished),
        DecisionPrediction.status == "error",
    ).delete(synchronize_session=False)
    for r in comp.model_results:
        if r.id in unfinished:
            r.status = "pending"
            r.error_message = None
    comp.status = "running"
    comp.completed_at = None
    db.commit()
    bg.add_task(engine.run_comparison_sync, comp.id)
    return {"status": "running"}


def _delete_comparisons(db: Session, ids: list[int]) -> None:
    db.query(DecisionPrediction).filter(DecisionPrediction.comparison_id.in_(ids)).delete(synchronize_session=False)
    db.query(DecisionModelResult).filter(DecisionModelResult.comparison_id.in_(ids)).delete(synchronize_session=False)
    db.query(DecisionComparison).filter(DecisionComparison.id.in_(ids)).delete(synchronize_session=False)


@router.delete("/comparisons/{comparison_id}")
def delete_comparison(comparison_id: int, request: Request, db: Session = Depends(get_db)):
    comp = _get_comparison(request, db, comparison_id)
    if comp.status in ("running", "stopping"):
        raise HTTPException(409, "Stop the comparison before deleting it")
    _delete_comparisons(db, [comp.id])
    db.commit()
    return {"detail": "Comparison deleted"}
