"""Generate the built-in decision datasets used by the Model Comparison feature.

Usage (from ``backend/``)::

    python scripts/generate_decision_datasets.py            # write all datasets
    python scripts/generate_decision_datasets.py --check    # validate, write nothing

Each module in ``scripts/decision_dataset_specs`` describes one dataset
(labels, task question, templates). This script runs every generator with
a fixed seed, validates the result (label coverage, minimum size, no
duplicate or conflicting rows) and writes one JSON file per dataset to
``data/decision_datasets/``. The backend seeds those files into the
database on startup.
"""

from __future__ import annotations

import argparse
import importlib
import json
import random
import sys
from collections import Counter
from pathlib import Path

BACKEND_DIR = Path(__file__).resolve().parent.parent
OUTPUT_DIR = BACKEND_DIR / "data" / "decision_datasets"
MIN_ROWS = 1000
SEED = 20261023

sys.path.insert(0, str(Path(__file__).resolve().parent))

from decision_dataset_specs import SPEC_MODULES  # noqa: E402


def build(module_name: str) -> dict:
    spec = importlib.import_module(f"decision_dataset_specs.{module_name}")
    # Seed per dataset so adding a new spec never reshuffles existing ones.
    rng = random.Random(f"{SEED}:{spec.SLUG}")
    items = spec.generate(rng)

    label_names = [label["name"] for label in spec.LABELS]
    if len(set(label_names)) != len(label_names):
        raise ValueError(f"{spec.SLUG}: duplicate label names")

    unknown = {item["label"] for item in items} - set(label_names)
    if unknown:
        raise ValueError(f"{spec.SLUG}: rows use undeclared labels {sorted(unknown)}")

    counts = Counter(item["label"] for item in items)
    missing = [name for name in label_names if counts[name] == 0]
    if missing:
        raise ValueError(f"{spec.SLUG}: labels without rows {missing}")

    by_text: dict[str, str] = {}
    unique_items = []
    for item in items:
        key = item["text"].strip().lower()
        if key in by_text:
            if by_text[key] != item["label"]:
                raise ValueError(
                    f"{spec.SLUG}: text appears under two labels "
                    f"({by_text[key]!r} and {item['label']!r}): {item['text']!r}"
                )
            continue
        by_text[key] = item["label"]
        unique_items.append(item)

    if len(unique_items) < MIN_ROWS:
        raise ValueError(f"{spec.SLUG}: only {len(unique_items)} unique rows (minimum {MIN_ROWS})")

    rng.shuffle(unique_items)
    return {
        "slug": spec.SLUG,
        "name": spec.NAME,
        "description": spec.DESCRIPTION,
        "language": spec.LANGUAGE,
        "task": spec.TASK,
        "labels": spec.LABELS,
        "items": unique_items,
    }


def dump(dataset: dict) -> str:
    """Pretty header, one row per line — compact yet diff-friendly."""
    header = {k: v for k, v in dataset.items() if k != "items"}
    head_json = json.dumps(header, ensure_ascii=False, indent=2)
    rows = ",\n".join("    " + json.dumps(item, ensure_ascii=False) for item in dataset["items"])
    return head_json[:-2] + ',\n  "items": [\n' + rows + "\n  ]\n}\n"


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--check", action="store_true", help="validate only, do not write files")
    args = parser.parse_args()

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    for module_name in SPEC_MODULES:
        dataset = build(module_name)
        counts = Counter(item["label"] for item in dataset["items"])
        hard = sum(1 for item in dataset["items"] if item.get("difficulty") == "hard")
        summary = ", ".join(f"{k}={v}" for k, v in counts.items())
        print(f"{dataset['slug']}: {len(dataset['items'])} rows ({hard} hard) — {summary}")
        if not args.check:
            (OUTPUT_DIR / f"{dataset['slug']}.json").write_text(dump(dataset), encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
