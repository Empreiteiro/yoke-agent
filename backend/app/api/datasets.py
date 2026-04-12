"""Dataset management API routes with LLM generation and HITL support."""

import asyncio
import logging
import uuid
from pathlib import Path
from typing import Optional
from fastapi import APIRouter, Depends, HTTPException, Request, UploadFile, File, BackgroundTasks
from pydantic import BaseModel
from sqlalchemy.orm import Session
import json

from app.core.database import get_db, SessionLocal
from app.core.tenancy import assert_can_access, current_user_id, scope_query
from app.models.document import Document
from app.models.dataset import Dataset, DatasetItem
from app.schemas.dataset import (
    DatasetCreate,
    DatasetResponse,
    DatasetItemCreate,
    DatasetItemUpdate,
    DatasetGenerateOptions,
)
from app.services.document_loader import load_documents
from app.services.dataset_generator import generate_qa_pairs

logger = logging.getLogger(__name__)

router = APIRouter()

BENCHMARKS_DIR = Path(__file__).parent.parent.parent / "data" / "benchmarks"

BENCHMARK_DEFINITIONS = [
    {
        "name": "Reading Comprehension Benchmark",
        "description": "25 factual Q&A pairs testing reading comprehension across science, history, and technology topics.",
        "filename": "reading_comprehension.json",
    },
    {
        "name": "Multi-Hop Reasoning Benchmark",
        "description": "25 Q&A pairs requiring multi-hop reasoning — connecting information from multiple contexts to answer.",
        "filename": "multi_hop_reasoning.json",
    },
    {
        "name": "Real-World Questions Benchmark",
        "description": "25 natural language Q&A pairs resembling real user queries about everyday phenomena and science.",
        "filename": "real_world_questions.json",
    },
]


def seed_benchmarks(db: Session) -> int:
    """Seed built-in benchmark datasets if they don't already exist."""
    created = 0
    for bench in BENCHMARK_DEFINITIONS:
        exists = (
            db.query(Dataset)
            .filter(Dataset.name == bench["name"], Dataset.is_benchmark == 1)
            .first()
        )
        if exists:
            continue

        filepath = BENCHMARKS_DIR / bench["filename"]
        if not filepath.exists():
            logger.warning(f"Benchmark file not found: {filepath}")
            continue

        items_data = json.loads(filepath.read_text(encoding="utf-8"))

        dataset = Dataset(
            name=bench["name"],
            description=bench["description"],
            document_ids=[],
            status="approved",
            is_benchmark=1,
        )
        db.add(dataset)
        db.flush()

        for item_data in items_data:
            db.add(DatasetItem(
                dataset_id=dataset.id,
                question=item_data["question"],
                ground_truth=item_data["ground_truth"],
                context=item_data.get("context", ""),
                is_manual=0,
            ))

        created += 1
        logger.info(f"Seeded benchmark dataset: {bench['name']}")

    if created:
        db.commit()
    return created


def _generate_dataset_sync(dataset_id: int, options: Optional[dict] = None):
    """Synchronous wrapper for background dataset generation."""
    asyncio.run(_generate_dataset_task(dataset_id, options))


async def _generate_dataset_task(dataset_id: int, options: Optional[dict] = None):
    """Background task to generate dataset items using LLM."""
    options = options or {}
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if not dataset:
            return

        doc_models = db.query(Document).filter(
            Document.id.in_(dataset.document_ids or [])
        ).all()
        filepaths = [doc.filepath for doc in doc_models]
        documents = load_documents(filepaths)

        if not documents:
            dataset.status = "error"
            dataset.error_message = "No documents found to generate dataset from."
            db.commit()
            return

        pairs, sampled_pages_info = await generate_qa_pairs(
            documents,
            db=db,
            num_questions=options.get("num_questions"),
            reading_mode=options.get("reading_mode", "full"),
            max_pages=options.get("max_pages"),
            language=options.get("language", "auto"),
            provider_id=options.get("provider_id"),
            model=options.get("model"),
        )

        if sampled_pages_info:
            dataset.sampled_pages = sampled_pages_info

        for pair in pairs:
            item = DatasetItem(
                dataset_id=dataset_id,
                question=pair.get("question", ""),
                ground_truth=pair.get("ground_truth", ""),
                context=pair.get("context", ""),
                source_document=pair.get("source_document", ""),
                is_manual=0,
            )
            db.add(item)

        dataset.status = "generated"
        dataset.error_message = None
        db.commit()
    except Exception as e:
        import traceback
        logger.error(f"Dataset generation failed for dataset {dataset_id}: {e}\n{traceback.format_exc()}")
        dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
        if dataset:
            dataset.status = "error"
            dataset.error_message = str(e)
            db.commit()
    finally:
        db.close()


@router.post("/", response_model=DatasetResponse)
def create_dataset(data: DatasetCreate, request: Request, db: Session = Depends(get_db)):
    dataset = Dataset(
        name=data.name or f"dataset-{uuid.uuid4().hex[:8]}",
        description=data.description,
        document_ids=data.document_ids,
        status="draft",
        user_id=current_user_id(request),
    )
    db.add(dataset)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.get("/", response_model=list[DatasetResponse])
def list_datasets(request: Request, db: Session = Depends(get_db)):
    """List datasets visible to the caller. Benchmark datasets are shared
    with everyone; regular datasets are scoped to the owning user."""
    from sqlalchemy import or_
    from app.models.user import ROLE_ADMIN

    user_id = current_user_id(request)
    role = getattr(request.state, "user_role", None)
    q = db.query(Dataset)
    if user_id is not None and role != ROLE_ADMIN:
        q = q.filter(
            or_(
                Dataset.is_benchmark == 1,
                Dataset.user_id == user_id,
                Dataset.user_id.is_(None),
            )
        )
    return q.order_by(Dataset.created_at.desc()).all()


@router.get("/{dataset_id}", response_model=DatasetResponse)
def get_dataset(dataset_id: int, request: Request, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if not dataset.is_benchmark:
        assert_can_access(request, dataset)
    return dataset


@router.delete("/{dataset_id}")
def delete_dataset(dataset_id: int, request: Request, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    if dataset.is_benchmark:
        raise HTTPException(status_code=403, detail="Benchmark datasets cannot be deleted")
    assert_can_access(request, dataset)
    db.delete(dataset)
    db.commit()
    return {"detail": "Dataset deleted", "dataset_id": dataset_id}


class _DatasetBulkDeleteRequest(BaseModel):
    ids: list[int]


@router.post("/bulk-delete")
def bulk_delete_datasets(
    payload: _DatasetBulkDeleteRequest, db: Session = Depends(get_db)
):
    """Delete multiple datasets at once (issue #115). Benchmarks are skipped."""
    if not payload.ids:
        return {"deleted": [], "skipped": [], "not_found": []}

    datasets = db.query(Dataset).filter(Dataset.id.in_(payload.ids)).all()
    existing_ids = {d.id for d in datasets}
    not_found = [i for i in payload.ids if i not in existing_ids]

    deleted: list[int] = []
    skipped: list[dict] = []
    for ds in datasets:
        if ds.is_benchmark:
            skipped.append({"id": ds.id, "reason": "benchmark"})
            continue
        db.delete(ds)
        deleted.append(ds.id)
    db.commit()
    return {"deleted": deleted, "skipped": skipped, "not_found": not_found}


@router.post("/seed-benchmarks")
def seed_benchmarks_endpoint(db: Session = Depends(get_db)):
    count = seed_benchmarks(db)
    return {"detail": f"Seeded {count} benchmark dataset(s)"}


@router.post("/{dataset_id}/generate")
async def generate_dataset(
    dataset_id: int,
    background_tasks: BackgroundTasks,
    options: Optional[DatasetGenerateOptions] = None,
    db: Session = Depends(get_db),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    dataset.status = "generating"
    db.commit()

    opts_dict = options.model_dump() if options else {}
    background_tasks.add_task(_generate_dataset_sync, dataset_id, opts_dict)
    return {"detail": "Dataset generation started", "dataset_id": dataset_id}


@router.post("/{dataset_id}/items", response_model=DatasetResponse)
def add_dataset_item(dataset_id: int, item: DatasetItemCreate, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    db_item = DatasetItem(
        dataset_id=dataset_id,
        question=item.question,
        ground_truth=item.ground_truth,
        context=item.context,
        source_document=item.source_document,
        is_manual=1,
    )
    db.add(db_item)
    db.commit()
    db.refresh(dataset)
    return dataset


@router.put("/{dataset_id}/items/{item_id}")
def update_dataset_item(
    dataset_id: int, item_id: int, item: DatasetItemUpdate, db: Session = Depends(get_db)
):
    db_item = (
        db.query(DatasetItem)
        .filter(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail="Dataset item not found")

    if item.question is not None:
        db_item.question = item.question
    if item.ground_truth is not None:
        db_item.ground_truth = item.ground_truth
    if item.context is not None:
        db_item.context = item.context

    db.commit()
    return {"detail": "Item updated"}


@router.delete("/{dataset_id}/items/{item_id}")
def delete_dataset_item(dataset_id: int, item_id: int, db: Session = Depends(get_db)):
    db_item = (
        db.query(DatasetItem)
        .filter(DatasetItem.id == item_id, DatasetItem.dataset_id == dataset_id)
        .first()
    )
    if not db_item:
        raise HTTPException(status_code=404, detail="Dataset item not found")
    db.delete(db_item)
    db.commit()
    return {"detail": "Item deleted"}


@router.post("/{dataset_id}/import")
async def import_dataset_items(
    dataset_id: int,
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")

    content = await file.read()
    try:
        items = json.loads(content)
    except json.JSONDecodeError:
        raise HTTPException(status_code=400, detail="Invalid JSON file")

    if not isinstance(items, list):
        raise HTTPException(status_code=400, detail="JSON must be an array of items")

    for item_data in items:
        db_item = DatasetItem(
            dataset_id=dataset_id,
            question=item_data.get("question", ""),
            ground_truth=item_data.get("ground_truth", ""),
            context=item_data.get("context"),
            source_document=item_data.get("source_document"),
            is_manual=1,
        )
        db.add(db_item)

    db.commit()
    db.refresh(dataset)
    return {"detail": f"Imported {len(items)} items", "dataset_id": dataset_id}


@router.post("/{dataset_id}/duplicate", response_model=DatasetResponse)
def duplicate_dataset(dataset_id: int, db: Session = Depends(get_db)):
    """Create a copy of an existing dataset with all its items."""
    source = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not source:
        raise HTTPException(status_code=404, detail="Dataset not found")

    new_dataset = Dataset(
        name=f"{source.name} (Copy)",
        description=source.description,
        document_ids=source.document_ids,
        status=source.status if source.status in ("generated", "approved") else "generated",
    )
    db.add(new_dataset)
    db.flush()  # Get the new dataset ID

    for item in source.items:
        db.add(DatasetItem(
            dataset_id=new_dataset.id,
            question=item.question,
            ground_truth=item.ground_truth,
            context=item.context,
            source_document=item.source_document,
            is_manual=item.is_manual,
        ))

    db.commit()
    db.refresh(new_dataset)
    return new_dataset


@router.post("/{dataset_id}/approve")
def approve_dataset(dataset_id: int, db: Session = Depends(get_db)):
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if not dataset:
        raise HTTPException(status_code=404, detail="Dataset not found")
    dataset.status = "approved"
    db.commit()
    return {"detail": "Dataset approved", "dataset_id": dataset_id}
