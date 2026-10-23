"""Built-in seeding and custom-upload parsing for decision datasets."""

from __future__ import annotations

import csv
import io
import json
import logging
from collections import Counter
from pathlib import Path
from typing import Any, Optional

from sqlalchemy import insert
from sqlalchemy.orm import Session

from app.models.decision import DecisionDataset, DecisionDatasetItem

logger = logging.getLogger(__name__)

BUILTIN_DIR = Path(__file__).resolve().parent.parent.parent / "data" / "decision_datasets"

MAX_UPLOAD_BYTES = 25 * 1024 * 1024
MAX_ROWS = 50_000
MAX_LABELS = 100
MIN_LABELS = 2
MAX_TEXT_CHARS = 20_000
MAX_LABEL_CHARS = 200

TEXT_COLUMN_CANDIDATES = [
    "text", "input", "message", "content", "query", "question", "prompt",
    "utterance", "sentence", "state", "body", "ticket", "review",
]
LABEL_COLUMN_CANDIDATES = [
    "label", "expected_label", "category", "class", "intent", "target",
    "expected", "answer", "gold", "y",
]
DEFAULT_TASK = "Which label best describes this text?"


class DatasetParseError(ValueError):
    """Raised when an uploaded file can't be turned into a dataset."""


# ── Built-in datasets ───────────────────────────────────────────────────


def insert_items(db: Session, dataset_id: int, rows: list[dict]) -> None:
    """Bulk-insert ``[{"text", "label", "difficulty"?}]`` rows."""
    if not rows:
        return
    db.execute(
        insert(DecisionDatasetItem),
        [
            {
                "dataset_id": dataset_id,
                "text": row["text"],
                "expected_label": row["label"],
                "difficulty": row.get("difficulty"),
            }
            for row in rows
        ],
    )


def seed_builtin_datasets(db: Session) -> int:
    """Load every ``data/decision_datasets/*.json`` file not yet in the DB."""
    if not BUILTIN_DIR.exists():
        return 0
    created = 0
    for path in sorted(BUILTIN_DIR.glob("*.json")):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError) as e:
            logger.warning("Skipping unreadable decision dataset %s: %s", path.name, e)
            continue
        slug = payload.get("slug") or path.stem
        exists = (
            db.query(DecisionDataset.id)
            .filter(DecisionDataset.slug == slug, DecisionDataset.is_builtin.is_(True))
            .first()
        )
        if exists:
            continue
        items = payload.get("items") or []
        dataset = DecisionDataset(
            slug=slug,
            name=payload.get("name") or slug,
            description=payload.get("description"),
            language=payload.get("language"),
            task=payload.get("task") or DEFAULT_TASK,
            labels=payload.get("labels") or [],
            is_builtin=True,
            source_filename=path.name,
            item_count=len(items),
        )
        db.add(dataset)
        db.flush()
        insert_items(db, dataset.id, items)
        db.commit()
        created += 1
        logger.info("Seeded decision dataset '%s' (%d rows)", dataset.name, len(items))
    return created


# ── Upload parsing ──────────────────────────────────────────────────────


def _decode(content: bytes) -> str:
    for encoding in ("utf-8-sig", "utf-8", "cp1252", "latin-1"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    raise DatasetParseError("Could not decode the file — please save it as UTF-8.")


def _read_rows(filename: str, content: bytes) -> tuple[list[dict], dict]:
    """Return ``(rows, metadata)``. Metadata may carry name/task/labels."""
    name = (filename or "").lower()
    text = _decode(content)
    meta: dict = {}

    if name.endswith((".jsonl", ".ndjson")):
        rows = []
        for lineno, line in enumerate(text.splitlines(), start=1):
            line = line.strip()
            if not line:
                continue
            try:
                obj = json.loads(line)
            except ValueError as e:
                raise DatasetParseError(f"Line {lineno} is not valid JSON: {e}") from e
            if not isinstance(obj, dict):
                raise DatasetParseError(f"Line {lineno} must be a JSON object")
            rows.append(obj)
        return rows, meta

    if name.endswith(".json"):
        try:
            data = json.loads(text)
        except ValueError as e:
            raise DatasetParseError(f"Invalid JSON: {e}") from e
        if isinstance(data, dict):
            meta = {k: data.get(k) for k in ("name", "description", "task", "labels", "language") if data.get(k)}
            data = data.get("items") or data.get("rows") or data.get("data")
        if not isinstance(data, list) or not all(isinstance(r, dict) for r in data):
            raise DatasetParseError(
                "JSON must be an array of objects, or an object with an \"items\" array "
                "(the format used by Export)."
            )
        return data, meta

    if name.endswith((".csv", ".tsv", ".txt")):
        sample = text[:10_000]
        try:
            dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
        except csv.Error:
            dialect = csv.excel_tab if name.endswith(".tsv") else csv.excel
        reader = csv.DictReader(io.StringIO(text), dialect=dialect)
        if not reader.fieldnames or len(reader.fieldnames) < 2:
            # The sniffer occasionally picks a delimiter that only appears
            # inside quoted text; plain comma-separated is the safe fallback.
            reader = csv.DictReader(io.StringIO(text), dialect=csv.excel)
        if not reader.fieldnames:
            raise DatasetParseError("The CSV file has no header row.")
        return [row for row in reader], meta

    raise DatasetParseError("Unsupported file type — upload .csv, .tsv, .json or .jsonl.")


def _pick_column(columns: list[str], requested: Optional[str], candidates: list[str], kind: str) -> str:
    if requested:
        if requested not in columns:
            raise DatasetParseError(f"Column '{requested}' not found. Available: {', '.join(columns)}")
        return requested
    lowered = {c.lower().strip(): c for c in columns}
    for cand in candidates:
        if cand in lowered:
            return lowered[cand]
    raise DatasetParseError(
        f"Couldn't detect the {kind} column. Name it one of: {', '.join(candidates[:6])} "
        f"— or pick it explicitly. Available: {', '.join(columns)}"
    )


def _normalize_labels(raw: Any) -> list[dict]:
    """Accept ``["a", "b"]``, ``[{"name", "description"}]`` or ``{"a": "desc"}``."""
    if not raw:
        return []
    if isinstance(raw, dict):
        raw = [{"name": k, "description": v} for k, v in raw.items()]
    labels = []
    for entry in raw:
        if isinstance(entry, str):
            labels.append({"name": entry.strip(), "description": ""})
        elif isinstance(entry, dict) and entry.get("name"):
            labels.append({
                "name": str(entry["name"]).strip(),
                "description": str(entry.get("description") or "").strip(),
            })
    return labels


def parse_dataset(
    filename: str,
    content: bytes,
    *,
    text_column: Optional[str] = None,
    label_column: Optional[str] = None,
    label_descriptions: Optional[dict] = None,
    allow_unmapped: bool = False,
) -> dict:
    """Parse an upload into a normalized dataset payload (no DB writes).

    Returns columns, detected mapping, label definitions and counts, a row
    sample, warnings, and the cleaned ``items`` list. With
    ``allow_unmapped`` (used for previews), a file whose text/label columns
    can't be auto-detected returns ``needs_mapping=True`` plus the raw
    columns instead of failing, so the user can pick them.
    """
    if len(content) > MAX_UPLOAD_BYTES:
        raise DatasetParseError(f"File is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
    rows, meta = _read_rows(filename, content)
    if not rows:
        raise DatasetParseError("The file contains no rows.")
    if len(rows) > MAX_ROWS:
        raise DatasetParseError(f"Too many rows ({len(rows):,}); the limit is {MAX_ROWS:,}.")

    columns: list[str] = []
    for row in rows[:200]:
        for key in row.keys():
            if key is not None and key not in columns:
                columns.append(key)
    try:
        text_col = _pick_column(columns, text_column, TEXT_COLUMN_CANDIDATES, "text")
        label_col = _pick_column(columns, label_column, LABEL_COLUMN_CANDIDATES, "label")
    except DatasetParseError as e:
        if not allow_unmapped:
            raise
        return _unmapped_preview(rows, columns, meta, text_column, label_column, str(e))
    if text_col == label_col:
        raise DatasetParseError("The text and label columns must be different.")
    has_difficulty = "difficulty" in columns

    items: list[dict] = []
    skipped = 0
    truncated = 0
    seen: set[tuple[str, str]] = set()
    duplicates = 0
    for row in rows:
        text = row.get(text_col)
        label = row.get(label_col)
        text = "" if text is None else str(text).strip()
        label = "" if label is None else str(label).strip()
        if not text or not label:
            skipped += 1
            continue
        if len(label) > MAX_LABEL_CHARS:
            raise DatasetParseError(f"Label longer than {MAX_LABEL_CHARS} characters: {label[:60]}…")
        if len(text) > MAX_TEXT_CHARS:
            text = text[:MAX_TEXT_CHARS]
            truncated += 1
        key = (text.lower(), label)
        if key in seen:
            duplicates += 1
            continue
        seen.add(key)
        item = {"text": text, "label": label}
        if has_difficulty and row.get("difficulty"):
            item["difficulty"] = str(row["difficulty"])[:20]
        items.append(item)

    if not items:
        raise DatasetParseError(f"No usable rows — every row is missing '{text_col}' or '{label_col}'.")

    counts = Counter(item["label"] for item in items)
    declared = _normalize_labels(meta.get("labels"))
    if declared:
        declared_names = {l["name"] for l in declared}
        unknown = sorted(set(counts) - declared_names)
        if unknown:
            raise DatasetParseError(f"Rows use labels not declared in \"labels\": {', '.join(unknown[:10])}")
        labels = declared
    else:
        labels = [{"name": name, "description": ""} for name in sorted(counts)]

    if label_descriptions:
        for label in labels:
            desc = label_descriptions.get(label["name"])
            if desc is not None:
                label["description"] = str(desc).strip()

    if len(labels) < MIN_LABELS:
        raise DatasetParseError("A classification dataset needs at least 2 distinct labels.")
    if len(labels) > MAX_LABELS:
        raise DatasetParseError(f"Too many distinct labels ({len(labels)}); the limit is {MAX_LABELS}.")

    warnings = []
    if skipped:
        warnings.append(f"{skipped} row(s) skipped because the text or label was empty.")
    if duplicates:
        warnings.append(f"{duplicates} duplicate row(s) removed.")
    if truncated:
        warnings.append(f"{truncated} text(s) truncated to {MAX_TEXT_CHARS:,} characters.")
    rare = [name for name, n in counts.items() if n < 5]
    if rare:
        warnings.append(f"{len(rare)} label(s) have fewer than 5 rows — per-label metrics will be noisy.")
    if not any(l["description"] for l in labels):
        warnings.append(
            "No label descriptions yet. Decision models and LLMs are noticeably more accurate "
            "when each label has a one-line definition."
        )

    return {
        "columns": columns,
        "text_column": text_col,
        "label_column": label_col,
        "rows_total": len(rows),
        "rows_valid": len(items),
        "label_counts": dict(counts.most_common()),
        "labels": labels,
        "name": meta.get("name"),
        "description": meta.get("description"),
        "task": meta.get("task"),
        "language": meta.get("language"),
        "sample": items[:10],
        "warnings": warnings,
        "items": items,
    }


def _unmapped_preview(rows, columns, meta, text_column, label_column, reason: str) -> dict:
    def detect(requested, candidates):
        if requested in columns:
            return requested
        lowered = {c.lower().strip(): c for c in columns}
        return next((lowered[c] for c in candidates if c in lowered), None)

    return {
        "needs_mapping": True,
        "columns": columns,
        "text_column": detect(text_column, TEXT_COLUMN_CANDIDATES),
        "label_column": detect(label_column, LABEL_COLUMN_CANDIDATES),
        "rows_total": len(rows),
        "rows_valid": 0,
        "label_counts": {},
        "labels": [],
        "name": meta.get("name"),
        "description": meta.get("description"),
        "task": meta.get("task"),
        "language": meta.get("language"),
        "sample": [],
        "raw_sample": [{c: str(row.get(c, ""))[:200] for c in columns} for row in rows[:5]],
        "warnings": [reason],
        "items": [],
    }


def export_payload(dataset: DecisionDataset, items: list[DecisionDatasetItem]) -> dict:
    """Serialize a dataset in the same format the upload accepts."""
    return {
        "name": dataset.name,
        "description": dataset.description,
        "language": dataset.language,
        "task": dataset.task,
        "labels": dataset.labels,
        "items": [
            {"text": i.text, "label": i.expected_label, **({"difficulty": i.difficulty} if i.difficulty else {})}
            for i in items
        ],
    }


TEMPLATE_CSV = """text,label
"I was charged twice for my subscription this month.",billing
"The app crashes every time I open the reports page.",technical_issue
"How do I reset my password? The link never arrives.",account_access
"""
