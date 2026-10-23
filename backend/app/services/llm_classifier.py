"""Use a generative LLM as a single-label classifier.

The same task question and label definitions a decision model receives are
rendered into a prompt; the LLM must answer with a JSON object naming one
label. Parsing is tolerant (code fences, prose around the JSON, label
written with different casing/spacing) but never guesses: if the answer
doesn't resolve to exactly one known label the prediction is "invalid".
"""

from __future__ import annotations

import json
import re
from typing import Optional

SYSTEM_PROMPT = """You are a precise classification engine.

Task: {task}

Choose exactly ONE label from this list:
{label_lines}

Rules:
- Answer with the label name exactly as written above.
- Reply with JSON only, no explanation: {{"label": "<label name>", "confidence": <number between 0 and 1>}}"""

USER_PROMPT = 'Text to classify:\n"""\n{text}\n"""'

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)
_JSON_OBJ_RE = re.compile(r"\{[^{}]*\}", re.S)


def build_messages(task: str, labels: list[dict], text: str) -> tuple[str, str]:
    label_lines = "\n".join(
        f"- {l['name']}: {l['description']}" if l.get("description") else f"- {l['name']}"
        for l in labels
    )
    return SYSTEM_PROMPT.format(task=task, label_lines=label_lines), USER_PROMPT.format(text=text)


def normalize_label(value: str) -> str:
    return re.sub(r"[\s\-]+", "_", value.strip().strip("\"'`.").lower())


def match_label(value: Optional[str], labels: list[str]) -> Optional[str]:
    """Map a raw answer to a canonical label name, or None."""
    if not value:
        return None
    if value in labels:
        return value
    norm = normalize_label(value)
    for label in labels:
        if normalize_label(label) == norm:
            return label
    return None


def parse_answer(content: str, labels: list[str]) -> tuple[Optional[str], Optional[float]]:
    """Return ``(label, confidence)`` parsed from the model output."""
    text = (content or "").strip()
    fenced = _FENCE_RE.search(text)
    if fenced:
        text = fenced.group(1).strip()

    candidates = [text] + _JSON_OBJ_RE.findall(text)
    for candidate in candidates:
        try:
            data = json.loads(candidate)
        except (ValueError, TypeError):
            continue
        if isinstance(data, dict):
            raw = data.get("label") or data.get("category") or data.get("answer") or data.get("choice")
            label = match_label(raw if isinstance(raw, str) else None, labels)
            if label:
                conf = data.get("confidence")
                try:
                    conf = max(0.0, min(1.0, float(conf))) if conf is not None else None
                except (TypeError, ValueError):
                    conf = None
                return label, conf
        elif isinstance(data, str):
            label = match_label(data, labels)
            if label:
                return label, None

    # Bare answer ("billing") or prose mentioning exactly one label.
    label = match_label(text, labels)
    if label:
        return label, None
    lowered = text.lower()
    hits = {
        label for label in labels
        if re.search(rf"(?<![\w]){re.escape(label.lower())}(?![\w])", lowered)
    }
    if len(hits) == 1:
        return hits.pop(), None
    return None, None
