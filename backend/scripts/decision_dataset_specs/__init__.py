"""Spec modules for the built-in decision datasets.

Each module exposes ``SLUG``, ``NAME``, ``DESCRIPTION``, ``LANGUAGE``,
``TASK``, ``LABELS`` and ``generate(rng) -> list[dict]``. See
``scripts/generate_decision_datasets.py``.
"""

SPEC_MODULES = [
    "guardrails",
    "ticket_classification",
    "ticket_classification_ptbr",
    "intent_routing",
    "tool_routing",
    "sentiment_analysis",
    "spam_phishing",
]
