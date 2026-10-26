"""Use a generative LLM as a single-label classifier.

The same task question and label definitions a decision model receives are
rendered into a prompt; the LLM must answer with a JSON object naming one
label. Parsing is tolerant (code fences, prose around the JSON, label
written with different casing/spacing) but never guesses: if the answer
doesn't resolve to exactly one known label the prediction is "invalid".

Prompts can be replaced per model (e.g. a safety model's native template).
Templates use the placeholders ``{task}``, ``{labels}`` (one "- name:
description" line per label), ``{label_names}`` and ``{text}``; any other
braces are left alone, so JSON examples need no escaping. Label *aliases*
map answers such as "unsafe" to a dataset label.
"""

from __future__ import annotations

import json
import re
from typing import Optional

SYSTEM_PROMPT = """You are a precise classification engine.

Task: {task}

Choose exactly ONE label from this list:
{labels}

Rules:
- Answer with the label name exactly as written above.
- Reply with JSON only, no explanation: {"label": "<label name>", "confidence": <number between 0 and 1>}"""

USER_PROMPT = 'Text to classify:\n"""\n{text}\n"""'

_FENCE_RE = re.compile(r"```(?:json)?\s*(.*?)```", re.S | re.I)
_JSON_OBJ_RE = re.compile(r"\{[^{}]*\}", re.S)
_PLACEHOLDER_RE = re.compile(r"\{(task|labels|label_names|text)\}")


def render(template: str, values: dict[str, str]) -> str:
    """Fill ``{task}``-style placeholders in one pass (values are never re-scanned)."""
    return _PLACEHOLDER_RE.sub(lambda m: values[m.group(1)], template)


def build_messages(
    task: str,
    labels: list[dict],
    text: str,
    system_template: Optional[str] = None,
    user_template: Optional[str] = None,
) -> tuple[str, str]:
    values = {
        "task": task,
        "labels": "\n".join(
            f"- {l['name']}: {l['description']}" if l.get("description") else f"- {l['name']}"
            for l in labels
        ),
        "label_names": ", ".join(l["name"] for l in labels),
        "text": text,
    }
    return render(system_template or SYSTEM_PROMPT, values), render(user_template or USER_PROMPT, values)


def normalize_label(value: str) -> str:
    return re.sub(r"[\s\-]+", "_", value.strip().strip("\"'`.").lower())


def normalize_aliases(aliases: Optional[dict[str, str]], labels: list[str]) -> dict[str, str]:
    """``{alias: label}`` keyed by normalized alias, keeping known labels only."""
    return {normalize_label(k): v for k, v in (aliases or {}).items() if v in labels and k.strip()}


def match_label(value: Optional[str], labels: list[str], aliases: Optional[dict[str, str]] = None) -> Optional[str]:
    """Map a raw answer to a canonical label name, or None.

    ``aliases`` must already be normalized (see ``normalize_aliases``).
    """
    if not value:
        return None
    if value in labels:
        return value
    norm = normalize_label(value)
    for label in labels:
        if normalize_label(label) == norm:
            return label
    return (aliases or {}).get(norm)


def parse_answer(
    content: str, labels: list[str], aliases: Optional[dict[str, str]] = None,
) -> tuple[Optional[str], Optional[float]]:
    """Return ``(label, confidence)`` parsed from the model output.

    ``aliases`` maps extra answer strings to labels (``{"unsafe": "jailbreak"}``).
    """
    aliases = normalize_aliases(aliases, labels)
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
            label = match_label(raw if isinstance(raw, str) else None, labels, aliases)
            if label:
                conf = data.get("confidence")
                try:
                    conf = max(0.0, min(1.0, float(conf))) if conf is not None else None
                except (TypeError, ValueError):
                    conf = None
                return label, conf
        elif isinstance(data, str):
            label = match_label(data, labels, aliases)
            if label:
                return label, None

    # Bare answer ("billing") or prose mentioning exactly one label.
    label = match_label(text, labels, aliases)
    if label:
        return label, None
    lowered = text.lower()
    words = [(label, label) for label in labels]
    words += [(alias.replace("_", " "), label) for alias, label in aliases.items()]
    words += [(alias, label) for alias, label in aliases.items()]
    hits = {
        label for word, label in words
        if re.search(rf"(?<![\w]){re.escape(word.lower())}(?![\w])", lowered)
    }
    if len(hits) == 1:
        return hits.pop(), None
    return None, None
